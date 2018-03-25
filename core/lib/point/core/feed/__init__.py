from point.core.user import User, UserNotFound
from point.core.post import Post
from geweb import log
import geweb.db.pgsql as db
from point.util.redispool import RedisPool
from point.util.queue import Queue
from point.util import timestamp, cache_get, cache_store, \
                       parse_url

from point.util.feedproc import process
from datetime import datetime, timedelta
import dateutil.parser
from unidecode import unidecode
from pytz import timezone

from point.core.feed.exc import InvalidFeedUrl, FeedNotFound, FeedFetchError

try:
    import re2 as re
except ImportError:
    import re

import settings

class Feed(User):
    type = 'feed'

    def __init__(self, field, value=None):
        self._url = None

        if field == 'url':
            self._url = value
        elif isinstance(field, (str, unicode)):
            if field.startswith('http://') or field.startswith('https://'):
                self._url = field
            elif not value:
                raise InvalidFeedUrl

        if self._url:
            if not parse_url(self._url, exact=True):
                raise InvalidFeedUrl

            key = 'url_feed_id:%s' % self._url

            id = cache_get(key)
            if not id:
                res = db.fetchone("SELECT id FROM users.feeds WHERE url=%s;",
                                  [self._url])
                if res:
                    id = res['id']
                    cache_store(key, id)

            if not id:
                raise FeedNotFound

            try:
                User.__init__(self, long(id))
            except UserNotFound:
                raise FeedNotFound
        else:
            try:
                User.__init__(self, field, value)
            except UserNotFound:
                raise FeedNotFound

        self._posts = []

    @classmethod
    def from_data(cls, id, login, url, fetch=False, **kwargs):
        self = cls(None, None)
        self.id = id
        self.login = login

        if url and not parse_url(url):
            raise InvalidFeedUrl
        self._url = url

        if 'info' in kwargs:
            self.info = kwargs['info']

        #if not self.id and self._url:
        #    key = "feed_info:%s" % self._url
        #    try:
        #        raise TypeError
        #        info, entries = cache_get(key)
        #
        #        for i in info:
        #            self.set_info(i, info[i])
        #
        #        self._entries = entries
        #
        #    except TypeError:
        if fetch:
            self.fetch()

        return self

    def save(self):
        is_new = not self.id

        if is_new and not self._url:
            raise InvalidFeedUrl("Cannot save feed without URL")

        if not self.login:
            self.login = self._generate_login()

        User.save(self)

        if is_new:
            db.perform("INSERT INTO users.feeds (id, url) VALUES (%s, %s);",
                       [self.id, self._url])

            self.fetch()

            for p in self.posts():
                p.save()
            self.update_task()

    def get_url(self):
        if self._url:
            return self._url

        if self.id:
            key = "feed_url:%s" % self.id
            self._url = cache_get(key)

        if not self._url:
            res = db.fetchone("SELECT url FROM users.feeds WHERE id=%s;",
                              [self.id])
            if not res:
                raise FeedNotFound

            self._url = res[0]
            if self.id:
                cache_store(key, self._url, 3600)

        return self._url

    def set_url(self, url):
        self._url = url

        if not self.id:
            return

        key = "feed_url:%s" % self.id
        cache_store(key, self._url, 3600)

        db.perform("UPDATE users.feeds SET url=%s WHERE id=%s;",
                   [self._url, self.id])

    def get_info(self, param=None):
        if self.id or self.info or self.info_upd:
            return User.get_info(self, param)

        if param:
            return None

        return {}

    def posts(self, limit=None):
        posts = []
        lp = self.last_published()

        for p in self._posts:
            try:
                if self.id and lp and p.created <= lp:
                    continue
            except TypeError:
                log.error('-- created "%s" <> lp "%s"' % (p.created, lp))
                raise FeedFetchError

            posts.append(p)

        posts.sort(lambda a, b: int(timestamp(a.created) - timestamp(b.created)))

        if limit is not None:
            return posts[-abs(int(limit)):]
        return posts

    def fetch(self):
        if self._posts:
            return

        if not self.get_url():
            raise InvalidFeedUrl

        log.info('Feed #%s fetch from %s' % (self.id, self.get_url()))

        proc = process(self.get_url())

        if proc.get_error():
            log.error("Feed #%s fetch error: %s %s" % \
                      (self.id, self.get_url(), proc.get_error()))
            if not proc.entries():
                #if 'status' in d and d['status'] < 400:
                #    raise InvalidFeedType
                #else:
                raise FeedFetchError

        info = proc.get_info()

        for param in ['name', 'about', 'homepage']:
            if info[param] and info[param] != self.get_info(param):
                self.set_info(param, info[param])

        if self.id and self.info_changed():
            self.save()

        self._posts = [Post(None, self, **p) for p in proc.entries()]

        log.info("Feed #%s: %s entries fetched from %s" % \
                 (self.id, len(self._posts), self.get_url()))

    def last_published(self, ts=None):
        if not self.id:
            return None

        redis = RedisPool(settings.storage_socket)
        key = "feed:last_published:%s" % self.id
        if ts is None:
            if not self.id:
                if not self._posts:
                    return None

                ts = max([ p.created for p in self._posts ])
                redis.set(key, ts.isoformat())

                return ts

            ts = redis.get(key)
            if ts:
                return dateutil.parser.parse(ts)
            res = db.fetchone("SELECT max(created) FROM posts.posts "
                              "WHERE author=%s;", [self.id])
            if not res or not res[0]:
                return None

            redis.set(key, res[0].isoformat())
            return res[0]

        redis.set(key, ts.isoformat())

    def update_task(self):
        if not self.id:
            return

        res = db.fetchall("SELECT created FROM posts.posts WHERE author=%s "
                          "ORDER BY created DESC LIMIT 10;", [self.id])

        now = datetime.now()

        timestamps = []
        for p in res:
            timestamps.append(timestamp(p['created']))

        if len(timestamps) < 2:
            self.update_at(now + timedelta(seconds=settings.feed_max_update_timeout))
            return

        lp = self.last_published()

        tz = timezone(settings.timezone)
        newlp = tz.localize(datetime.fromtimestamp(int(max(timestamps))))

        if newlp > lp:
            self.last_published(newlp)

        timestamps.append(timestamp(now))
        timestamps.sort()
        deltas = []
        for i in xrange(1, len(timestamps)):
            deltas.append(timestamps[i] - timestamps[i-1])
        delta = reduce(lambda mem, t: mem+t, deltas, 0) / len(deltas) + 60
        if delta < settings.feed_min_update_timeout:
            delta = settings.feed_min_update_timeout
        if delta > settings.feed_max_update_timeout:
            delta = settings.feed_max_update_timeout
        update_at = now + timedelta(seconds=delta)

        self.update_at(update_at)

        del timestamps

    def update_at(self, dt):
        if not self.id:
            return

        log.info('Feed #%s update_at %s' % (self.id, dt))
        qname = 'fqueue:%02d%02d' % (dt.hour, dt.minute)
        fqueue = Queue(qname, settings.feed_queue_socket, channels=False)
        fqueue.push({'id': self.id})
        cache_store('feed:next_update:%s' % self.id, dt.isoformat())

    def next_update(self):
        if not self.id:
            return None

        dt = cache_get('feed:next_update:%s' % self.id)
        if not dt:
            return None
        return dateutil.parser.parse(dt)

    def _generate_login(self):
        name = unidecode(self.get_info('name')).lower()
        if not name:
            name = re.sub(r'^\w+:/+', '', self._url.lower())

        name = re.sub('^\W+|\W+$', '', name)

        words = re.split(r'\W+', name)
        name = ''
        br = False
        for w in words[:]:
            if not name:
                _name = w
            else:
                _name = "%s-%s" % (name, w)
            if len(_name) <= 16:
                name = _name
            else:
                name = _name[:16]
                br = True
                break

        if br:
            try:
                ri = name.rindex('-')
            except ValueError:
                ri = 16
            if ri > 6:
                name = name[:ri]

        i = 0

        while True:
            login = '%s%s-feed' % (name, i or '')
            try:
                User('login', login)
            except UserNotFound:
                return login
            i += 1


