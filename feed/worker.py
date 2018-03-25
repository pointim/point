import os
import gevent
from gevent import monkey; monkey.patch_all()
from point.core.feed import Feed
from point.core.feed.exc import FeedNotFound, FeedFetchError, InvalidFeedType
from point.util.redispool import RedisPool
from point.util.queue import Queue
from point.util import proctitle
from point.app.posts import add_post
from geweb import log
from datetime import datetime, timedelta

import settings

class FeedWorker(object):
    def __init__(self):
        proctitle('feed-worker')
        log.info('FeedWorker started with PID=%d' % os.getpid())

        self.fqueue = Queue('fqueue', settings.feed_queue_socket)

        while True:
            data = self.fqueue.pop()
            if not data or 'id' not in data or not data['id']:
                continue

            try:
                gevent.spawn(self.update_feed, int(data['id']))
            except ValueError:
                continue

    def update_feed(self, id):
        try:
            feed = Feed(id)
        except FeedNotFound:
            log.error('Feed #%s does not exist. Skipped.' % id)
            return

        redis = RedisPool(settings.storage_socket)

        try:
            feed.fetch()

            redis.delete('feed:retries:%s' % feed.id)

            for p in feed.posts():
                if not p.id:
                    if p.tags:
                        p.tags.insert(0, 'news')
                    else:
                        p.tags = ['news']
                    add_post(p)

            log.info('Feed #%s: %s new entries saved' % \
                     (feed.id, len(feed.posts())))

            feed.update_task()

        except FeedFetchError:
            retries = redis.incr('feed:retries:%s' % feed.id)
            log.error('Feed #%s: %s retries failed' % (feed.id, retries))
            if retries > settings.feed_retries:
                redis.delete('feed:retries:%s' % feed.id)
                return
            timeout = settings.feed_retry_timeout * retries
            feed.update_at(datetime.now() + timedelta(seconds=timeout))

        except InvalidFeedType:
            redis.delete('feed:retries:%s' % feed.id)
            feed.update_at(datetime.now() + \
                           timedelta(seconds=settings.feed_max_update_timeout))

