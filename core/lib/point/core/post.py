from geweb import log
import geweb.db.pgsql as db
from point.core.user import User, AnonymousUser
from point.core.user import AlreadySubscribed
from point.core import PointError
from point.util import b26, unb26
from point.util.redispool import RedisPool
from datetime import datetime, timedelta
from psycopg2 import IntegrityError
from psycopg2.extras import Json
from point.util.imgproc import remove_attach
#import elasticsearch

import settings

class PostError(PointError):
    def __init__(self, post_id=None, *args, **kwargs):
        self.post_id = post_id
        PointError.__init__(self, *args, **kwargs)

class PostNotFound(PostError):
    pass

class PostAuthorError(PostError):
    pass

class PostTextError(PostError):
    pass

class PostUpdateError(PostError):
    pass

class PostDiffError(PostError):
    pass

class PostCommentedError(PostError):
    pass

class PostReadonlyError(PostError):
    pass

class PostLimitError(PostError):
    pass

class PostAlreadyPinnedError(PostError):
    pass

class PostNotPinnedError(PostError):
    pass


class Post(object):
    def __init__(self, post_id, author=None, type=None, tags=None,
                 private=None, created=None, title=None, link=None, text=None,
                 edited=None, tz=settings.timezone, archive=None, files=None,
                 pinned=None, tune=None):
        self._comments_count = None

        if post_id:
            if isinstance(post_id, (int, long)):
                if post_id == 0:
                    raise PostNotFound(post_id)
                self.id = b26(post_id)
            else:
                self.id = post_id.lower()
            res = db.fetchone("SELECT p.author, u.login, p.type, p.private, "
                             "p.created at time zone %s AS created, "
                             "p.tags, p.title, p.link, p.text, p.files, "
                             "p.edited, p.archive, p.pinned, p.tune "
                             "FROM posts.posts p "
                             "JOIN users.logins u ON p.author=u.id "
                             "WHERE p.id=%s;",
                             [tz, unb26(self.id)])

            if not res:
                raise PostNotFound(post_id)

            self.author = User.from_data(res[0], res[1])
            self.created = res['created']

            if type is not None:
                self.type = type
            else:
                self.type = res['type']

            if private is not None:
                self.private = private
            else:
                self.private = res['private']

            if tags is not None:
                self.tags = [ t.decode('utf8').strip() if isinstance(t, str) else t for t in tags ]
            else:
                self.tags = res['tags']

            if title is not None:
                if isinstance(title, str):
                    self.title = title.decode('utf8').strip()[:128]
                elif isinstance(title, unicode):
                    self.title = title.strip()[:128]
            else:
                self.title = res['title']

            if link is not None:
                self.link = link
            else:
                self.link = res['link']

            if text is not None:
                if isinstance(text, str):
                    self.text = text.decode('utf8').strip()[:1048576]
                elif isinstance(text, unicode):
                    self.text = text.strip()[:1048576]
                if len(self.text) < 3:
                    raise PostTextError
            else:
                self.text = res['text']

            if edited is not None:
                self.edited = edited
            else:
                self.edited = res['edited']

            self.editable = not self.edited and \
                            self.created + \
                            timedelta(seconds=settings.edit_expire) >= \
                            datetime.now() # and \
                            #self.comments_count() == 0

            if archive is not None:
                self.archive = archive
            else:
                self.archive = res['archive']

            if pinned is not None:
                self.pinned = pinned
            else:
                self.pinned = res['pinned']

            if tune is not None:
                self.tune = tune
            else:
                self.tune = res['tune']

            if isinstance(files, (list, tuple)):
                self.files = files
            else:
                self.files = res['files']

        #elif not author:
        #    raise PostAuthorError
        #elif not text:
        #    raise PostTextError

        else:
            self.id = None
            self.author = author
            self.type = type
            self.tags = tags
            self.private = private

            if isinstance(title, str):
                self.title = title.decode('utf-8').strip()[:128]
            elif isinstance(title, unicode):
                self.title = title.strip()[:128]
            else:
                self.title = title

            self.link = link

            if isinstance(text, str):
                try:
                    self.text = text.decode('utf-8').strip()[:1048576]
                except UnicodeDecodeError:
                    raise PostTextError
            elif isinstance(text, unicode):
                self.text = text.strip()[:1048576]
            else:
                self.text = text

            self.created = created
            self.edited = False
            self.editable = True
            self.archive = False if archive is None else archive
            self.pinned = False if pinned is None else pinned
            self.tune = tune

        self.tz = tz

    def __repr__(self):
        return '<Post #%s>' % str(self.id)

    @classmethod
    def from_data(cls, post_id, author=None, type=None, tags=None,
                  private=None, created=None, title=None, link=None, text=None,
                  edited=None, tz=settings.timezone, archive=False, files=None,
                  pinned=False, tune=None):
        self = cls(None)
        if post_id:
            self.id = post_id.lower()

        if author is not None:
            self.author = author

        if type is not None:
            self.type = type

        if tags is not None:
            self.tags = tags
        else:
            self.tags = []

        if private is not None:
            self.private = private

        if created is not None:
            self.created = created

        if title is not None:
            self.title = title

        if link is not None:
            self.link = link

        if text is not None:
            self.text = text

        if edited is not None:
            self.edited = edited

        if tz is not None:
            self.tz = tz

        self.archive = archive
        self.pinned = pinned
        self.tune = tune

        if isinstance(files, (list, tuple)):
            self.files = files
        else:
            self.files = None

        return self

    def save(self):
        if self.tags:
            self.tags = [ t[:64] for t in filter(None, self.tags)[:10] ]

        try:
            if not isinstance(self.files, (list, tuple)):
                self.files = None
        except AttributeError:
            self.files = None

        if self.id:
            db.perform("DELETE FROM posts.tags WHERE post_id=%s;",
                       [unb26(self.id)])
            if self.tags:
                for t in self.tags:
                    if isinstance(t, str):
                        t = t.decode('utf-8')
                    db.perform("INSERT INTO posts.tags "
                               "(post_id, user_id, tag) VALUES (%s, %s, %s);",
                               [unb26(self.id), self.author.id, t])

            db.perform("UPDATE posts.posts SET tags=%s, private=%s,"
                       "text=%s, edited=%s, archive=%s, pinned=%s, files=%s "
                       "WHERE id=%s;",
                       [self.tags, bool(self.private), self.text,
                        self.edited, self.archive, self.pinned, self.files,
                        unb26(self.id)])

        else:
            if not self.created:
                self.created = datetime.now()

            res = db.fetchone("INSERT INTO posts.posts "
                             "(author, type, private, tags, title, link, text, "
                             "created, edited, archive, pinned, tune, files) "
                             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                             "RETURNING id;",
                             [self.author.id, self.type, bool(self.private),
                              self.tags, self.title, self.link, self.text,
                              self.created, self.edited, self.archive, self.pinned, Json(self.tune), self.files])
            if not res:
                raise PostError

            self.id = b26(res[0])

            if self.tags:
                for t in self.tags:
                    try:
                        db.perform("INSERT INTO posts.tags "
                                   "(post_id, user_id, tag) "
                                   "VALUES (%s, %s, %s);",
                                   [unb26(self.id), self.author.id, t])
                    except IntegrityError:
                        pass

        #try:
        #    es = elasticsearch.Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)
        #    es.index(index='point-posts', id=self.id, doc_type='post', body={
        #        'post_id': self.id,
        #        'post_type': self.type,
        #        'created': self.created,
        #        'private': self.private,
        #        'user_id': self.author.id,
        #        'login': self.author.login,
        #        'title': self.title,
        #        'tags':  self.tags,
        #        'text': self.text,
        #    })
        #except elasticsearch.ConnectionError, e:
        #    log.error('Elasticsearch: %s' % e)

        return self.id

    def delete(self):
        files = []
        for ff in db.fetchall("SELECT files FROM posts.comments "
                              "WHERE post_id=%s;", [unb26(self.id)]):
            if ff and ff['files']:
                files.extend(ff['files'])
        for ff in db.fetchone("DELETE FROM posts.posts WHERE id=%s "
                              "RETURNING files;", [unb26(self.id)]):
            if ff:
                files.extend(ff)

        redis = RedisPool(settings.storage_socket)
        redis.delete('cmnt_cnt.%s' % unb26(self.id))

        for f in files:
            remove_attach(f)

        #es = elasticsearch.Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)
        #try:
        #    es.delete(index='point-posts', doc_type='post', id=self.id)
        #except elasticsearch.exceptions.NotFoundError:
        #    pass

    def update(self, text):
        if not self.id:
            raise PostNotFound(None)

        cnt = self.updates_count()

        if cnt >= 3:
            raise PostUpdateError

        db.perform("INSERT INTO posts.updates (post_id, text) "
                   "VALUES (%s, %s);", [unb26(self.id), text])

    def add_subscriber(self, user):
        try:
            db.perform("INSERT INTO subs.posts VALUES (%s, %s);",
                       [user.id, unb26(self.id)])
        except IntegrityError:
            raise AlreadySubscribed

    def del_subscriber(self, user):
        res = db.fetchone("DELETE FROM subs.posts "
                         "WHERE post_id=%s AND user_id=%s "
                         "RETURNING post_id;",
                         [unb26(self.id), user.id])
        return bool(res)

    def get_subscribers(self, bluser=None):
        if bluser is not None:
            res = db.fetchall("SELECT user_id FROM subs.posts "
                              "WHERE post_id=%s "
                              "EXCEPT "
                              "SELECT user_id "
                              "FROM users.blacklist "
                              "WHERE to_user_id=%s;",
                              [unb26(self.id), bluser.id])
        else:
            res = db.fetchall("SELECT user_id FROM subs.posts "
                          "WHERE post_id=%s;", [unb26(self.id)])

        return [ r[0] for r in res ]

    def check_subscriber(self, user):
        if not self.id or not user.id:
            return False
        res = db.fetchone("SELECT user_id FROM subs.posts "
                          "WHERE user_id=%s AND post_id=%s;",
                          [user.id, unb26(self.id)])
        return bool(res)

    def check_recommended(self, user):
        if not self.id or not user.id:
            return False
        res = db.fetchone("SELECT user_id FROM posts.recommendations "
                          "WHERE user_id=%s AND post_id=%s AND comment_id=0;",
                          [user.id, unb26(self.id)])
        return bool(res)

    def check_bookmarked(self, user):
        if not self.id or not user.id:
            return False
        res = db.fetchone("SELECT user_id FROM posts.bookmarks "
                          "WHERE user_id=%s AND post_id=%s AND comment_id=0;",
                          [user.id, unb26(self.id)])
        return bool(res)

    def set_pinned(self, value=True):
        self.pinned = value
        self.save()

    def comments(self, last=False, all=False, offset=None, limit=None,
                 cuser=None):
        if last:
            lim = " LIMIT %d" % limit if limit else ''
            offset = 0
            order = ' DESC'
        elif all:
            lim = ''
            offset = 0
            order = ' ASC'
        else:
            if not offset:
                offset = 0
            lim = " LIMIT %d" % limit if limit else ''
            order = ' ASC'

        if isinstance(cuser, User) and cuser.id:
            res = db.fetchall("SELECT c.comment_id, c.to_comment_id,"
                              "c.author AS user_id, "
                              "CASE WHEN c.anon_login IS NOT NULL "
                                "THEN c.anon_login ELSE u1.login END AS login,"
                              "c.created at time zone %%s AS created, "
                              "c.text, c.files, "
                              "c.updated at time zone %%s AS updated, "
                              "CASE WHEN rc.comment_id IS NOT NULL "
                                "THEN true ELSE false END AS is_rec, "
                              "ur.user_id AS recommended, "
                              "ub.user_id AS bookmarked, "
                              "ui1.name, ui1.avatar "
                              "FROM posts.comments c "
                              "JOIN users.logins u1 ON c.author=u1.id "
                              "LEFT OUTER JOIN users.info ui1 "
                                "ON ui1.id=c.author "
                              "LEFT OUTER JOIN posts.recommendations rc "
                                "ON rc.post_id=c.post_id "
                                "AND rc.rcid=c.comment_id "
                              "LEFT OUTER JOIN posts.recommendations ur "
                                "ON ur.user_id=%%s "
                                "AND ur.post_id=c.post_id "
                                "AND ur.comment_id=c.comment_id "
                              "LEFT OUTER JOIN posts.bookmarks ub "
                                "ON ub.user_id=%%s "
                                "AND ub.post_id=c.post_id "
                                "AND ub.comment_id=c.comment_id "
                              "WHERE c.post_id=%%s AND c.comment_id>=%%s "
                              "ORDER BY c.created%s%s;" % (order, lim),
                              [self.tz, self.tz, cuser.id, cuser.id, unb26(self.id),
                               offset])
        else:
            res = db.fetchall("SELECT c.comment_id, c.to_comment_id,"
                              "c.author AS user_id, ui1.name,"
                              "CASE WHEN c.anon_login IS NOT NULL "
                                "THEN c.anon_login ELSE u1.login END AS login,"
                              "c.created at time zone %%s AS created, "
                              "c.text, c.files, "
                              "c.updated at time zone %%s AS updated, "
                              "CASE WHEN rc.comment_id IS NOT NULL "
                                "THEN true ELSE false END AS is_rec, "
                              "false AS recommended, "
                              "false AS bookmarked, "
                              "ui1.avatar "
                              "FROM posts.comments c "
                              "JOIN users.logins u1 ON c.author=u1.id "
                              "LEFT OUTER JOIN users.info ui1 "
                                "ON ui1.id=c.author "
                              "LEFT OUTER JOIN posts.recommendations rc "
                                "ON rc.post_id=c.post_id "
                                "AND rc.rcid=c.comment_id "
                              "WHERE c.post_id=%%s AND c.comment_id>=%%s "
                              "ORDER BY c.created%s%s;" % (order, lim),
                              [self.tz, self.tz, unb26(self.id), offset])
        if last:
            res.reverse()

        if cuser:
            unr = db.fetchall("SELECT comment_id FROM posts.unread_comments "
                              "WHERE user_id=%s AND post_id=%s;",
                              [cuser.id, unb26(self.id)])
            unread = { r['comment_id']: 1 for r in unr }
        else:
            unread = {}

        comments = []
        for c in res:
            author = User.from_data(c['user_id'], c['login'],
                     info={'name': c['name'], 'avatar': c['avatar']})

            unr = True if c['comment_id'] in unread else False
            comment = Comment.from_data(self, id=c['comment_id'],
                                              to_comment_id=c['to_comment_id'],
                                              author=author,
                                              created=c['created'],
                                              text=c['text'],
                                              recommended=c['recommended'],
                                              bookmarked=c['bookmarked'],
                                              is_rec=c['is_rec'],
                                              files=c['files'],
                                              updated=c['updated'],
                                              unread=unr)
            comments.append(comment)

        if not limit and not offset:
            redis = RedisPool(settings.storage_socket)
            redis.set('cmnt_cnt.%s' % unb26(self.id), len(comments))

        return comments

    def comments_count(self):
        if self._comments_count is not None:
            return self._comments_count

        if not self.id:
            raise PostNotFound(None)
        redis = RedisPool(settings.storage_socket)

        cnt = redis.get('cmnt_cnt.%s' % unb26(self.id))
        if cnt is not None:
            try:
                self._comments_count = int(cnt)
            except (TypeError, ValueError):
                self._comments_count = 0
            return self._comments_count
        try:
            cnt = db.fetchone("SELECT count(comment_id)::int "
                              "FROM posts.comments "
                              "WHERE post_id=%s;",
                              [unb26(self.id)])[0]
        except IndexError:
            cnt = 0

        redis.set('cmnt_cnt.%s' % unb26(self.id), int(cnt))

        try:
            self._comments_count = int(cnt)
        except (TypeError, ValueError):
            self._comments_count = 0

        return self._comments_count

    def updates(self):
        return db.fetchall("SELECT created, text FROM posts.updates "
                           "WHERE post_id=%s;", [unb26(self.id)])

    def updates_count(self):
        try:
            return db.fetchone("SELECT count(post_id) FROM posts.updates "
                              "WHERE post_id=%s;", [unb26(self.id)])[0]
        except IndexError:
            return 0

    def recipients(self):
        res = db.fetchall("SELECT u.id, u.login FROM posts.recipients r "
                          "JOIN users.logins u ON u.id=r.user_id "
                          "WHERE r.post_id=%s;", [unb26(self.id)])
        return [ User.from_data(r[0], r[1]) for r in res ]

    def recommended_users(self):
        res = db.fetchall("SELECT u.id, u.login FROM posts.recommendations r "
                          "JOIN users.logins u ON u.id=r.user_id "
                          "WHERE post_id=%s AND comment_id=0;",
                          [unb26(self.id)])
        return [ User.from_data(r[0], r[1]) for r in res ]

    def todict(self):
        img_url = lambda i: 'http'+settings.media_root+'/'+i
        post_dict = {
            "id": self.id,
            "pinned": True if self.pinned else False,
            "author": self.author.todict(),
            "private": self.private,
            "type": self.type,
            "created": self.created,
            "tags": self.tags,
            "text": self.text,
            "comments_count": self.comments_count()
        }
        if self.files:
            post_dict["files"] = [img_url(i) for i in self.files]
        return post_dict

class CommentError(PointError):
    def __init__(self, post_id=None, comment_id=None, *args, **kwargs):
        self.post_id = post_id
        self.comment_id = comment_id
        PointError.__init__(self, *args, **kwargs)

class CommentNotFound(CommentError):
    pass

class CommentAuthorError(CommentError):
    pass

class CommentEditingForbiddenError(CommentError):
    pass

class Comment(object):
    def __init__(self, post, id, to_comment_id=None, author=None,
                                 created=None, text=None, archive=False,
                                 files=None):
        if post and id:
            if isinstance(post, Post):
                self.post = post
            elif isinstance(post, (int, long)):
                self.post = Post.from_data(b26(post))
            else:
                self.post = Post.from_data(post)
            self.id = int(id)

            res = db.fetchone("SELECT c.author, u.login, i.name, i.avatar, "
                             "c.to_comment_id, "
                             "c.anon_login, "
                             "c.created at time zone %s AS created, "
                             "c.text, c.files, c.updated "
                             "FROM posts.comments c "
                             "JOIN users.logins u ON u.id=c.author "
                             "JOIN users.info i ON u.id=i.id "
                             "WHERE post_id=%s AND comment_id=%s;",
                             [self.post.tz, unb26(self.post.id), self.id])

            if not res:
                raise CommentNotFound(self.post.id, id)

            if author:
                self.author = author
            else:
                login = res['anon_login'] or res['login']
                self.author = User.from_data(res['author'], login,
                              info={'name': res['name'] or login,
                                    'avatar': res['avatar']})

            self.to_comment_id = to_comment_id or res['to_comment_id']
            self.created = created or res['created']
            self.text = text or res['text']

            self.recommendations = 0
            self.recommended = False
            self.files = res['files']
            self.updated = res['updated']
        self.comments = []
        self.archive = archive

        if isinstance(files, (list, tuple)):
            self.files = files

    def __repr__(self):
        return '<Comment #%s/%s>' % (str(self.post.id), self.id)

    @classmethod
    def from_data(cls, post, id, to_comment_id=None, author=None,
                                 created=None, text=None,
                                 recommended=False, bookmarked=False,
                                 is_rec=False, archive=False, files=None,
                                 updated=None, unread=False):
        self = cls(None, None)
        self.post = post
        if id:
            self.id = int(id)
        else:
            self.id = None
        self.to_comment_id = to_comment_id
        self.author = author
        self.created = created
        self.text = text
        self.recommended = recommended
        self.bookmarked = bookmarked
        self.is_rec = is_rec
        self.archive = archive
        if isinstance(files, (list, tuple)):
            self.files = files
        else:
            self.files = None
        self.updated = updated
        self.unread = unread
        return self

    def save(self, update=False):
        if not self.post.id:
            raise PostNotFound
        if isinstance(self.author, AnonymousUser):
            anon_login = self.author.login
        else:
            anon_login = None

        if not self.created:
            self.created = datetime.now()

        if isinstance(self.text, str):
            self.text = self.text.decode('utf-8', 'ignore')

        if update:
            res = db.perform("""
                UPDATE posts.comments SET (text, updated) = (%s, now())
                WHERE post_id = %s AND comment_id = %s;
                """, [self.text,
                    unb26(self.post.id) if isinstance(self.post.id, basestring) else self.post.id,
                    self.id])
            comment_id = self.id
        else:
            if self.archive and self.id:
                comment_id = self.id
                res = db.fetchone("INSERT INTO posts.comments "
                                  "(post_id, comment_id, author, created,"
                                  "to_comment_id, anon_login, text, files) "
                                  "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                                  "RETURNING comment_id;",
                                  [unb26(self.post.id), self.id, self.author.id,
                                   self.created,
                                   self.to_comment_id, anon_login, self.text,
                                   self.files])
            else:
                redis = RedisPool(settings.storage_socket)
                for n in xrange(1000):
                    try:
                        comment_id = redis.incr('cmnt.%s' % self.post.id)
                        res = db.fetchone("INSERT INTO posts.comments "
                                         "(post_id, comment_id, author, created,"
                                         "to_comment_id, anon_login, text, files) "
                                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                                         "RETURNING comment_id;",
                                         [unb26(self.post.id), comment_id,
                                          self.author.id, self.created,
                                          self.to_comment_id,
                                          anon_login, self.text, self.files])
                        break
                    except IntegrityError:
                        nres = db.fetchone("SELECT max(comment_id) FROM posts.comments "
                                          "WHERE post_id=%s;", [unb26(self.post.id)])
                        if nres:
                            num = nres[0]
                        else:
                            num = 0
                        comment_id = redis.set('cmnt.%s' % self.post.id, num)

                if res:
                    redis.incr('cmnt_cnt.%s' % unb26(self.post.id))

        #try:
        #    es = elasticsearch.Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)
        #    es.index(index='point-comments',
        #             id='%s-%s' % (self.post.id, self.id),
        #             doc_type='post', body={
        #        'post_id': self.post.id,
        #        'comment_id': self.id,
        #        'post_type': self.post.type,
        #        'created': self.created,
        #        'private': self.post.private,
        #        'user_id': self.author.id,
        #        'login': self.author.login,
        #        'text': self.text,
        #    })
        #except elasticsearch.ConnectionError, e:
        #    log.error('Elasticsearch: %s' % e)

        self.id = comment_id

        return comment_id

    def delete(self):
        res = db.fetchone("DELETE FROM posts.comments "
                         "WHERE post_id=%s AND comment_id=%s "
                         "RETURNING files;",
                         [unb26(self.post.id), self.id])
        if res and res['files']:
            for f in res['files']:
                remove_attach(f)
            redis = RedisPool(settings.storage_socket)
            redis.decr('cmnt_cnt.%s' % unb26(self.post.id))

        #try:
        #    es = elasticsearch.Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)
        #    try:
        #        es.delete(index='point-comments', doc_type='post',
        #                  id='%s-%s' % (self.post.id, self.id))
        #    except elasticsearch.exceptions.NotFoundError:
        #        pass
        #except elasticsearch.ConnectionError, e:
        #    log.error('Elasticsearch: %s' % e)

    def todict(self):
        return {
            "post_id": self.post.id,
            "id": self.id,
            "author": self.author.todict(),
            "created": self.created,
            "to_comment_id": self.to_comment_id,
            "text": self.text,
            "is_rec": self.is_rec
        }

    def is_editable(self):
        return datetime.now() - timedelta(seconds=settings.edit_comment_expire) \
        <= self.created

class RecommendationError(PointError):
    pass

class RecommendationNotFound(PointError):
    pass

class RecommendationExists(PointError):
    pass

class BookmarkExists(PointError):
    pass

