# -*- coding: UTF-8 -*-

from geweb import log
import geweb.db.pgsql as db
from point.util.env import env
from point.core.user import User, AlreadySubscribed, SubscribeError, check_auth
from point.core.post import Post, PostAuthorError, PostTextError, \
                            PostUpdateError, PostDiffError, PostNotFound
from point.core.post import Comment, CommentAuthorError, CommentNotFound, \
                            CommentEditingForbiddenError
from point.core.post import RecommendationError, RecommendationNotFound, \
                            RecommendationExists, PostLimitError, \
                            PostReadonlyError
from point.core.post import BookmarkExists
from point.util.redispool import RedisPool, publish
from point.util import uniqify, b26, unb26, diff_ratio, timestamp
from point.util import cache_get, cache_store, cache_del
from point.util.imgproc import make_thumbnail
from datetime import datetime, timedelta
from psycopg2 import IntegrityError

import settings

try:
    import re2 as re
except ImportError:
    import re

_user_re = re.compile(r'(?<!\w)@([-a-z]+)', re.I)

def check_last_action(fn):
    def _fn(*args, **kwargs):
        author = None
        if 'author' in kwargs and kwargs['author']:
            if isinstance(kwargs['author'], (str, unicode)):
                author = User('login')
            elif isinstance(kwargs['author'], User):
                author = kwargs['author']
        if not author:
            author = env.user

        d = cache_get('last_action:%s' % author.id)
        if d:
            d = datetime.fromtimestamp(int(d))
            if datetime.now() < d+timedelta(seconds=settings.actions_interval):
                raise PostLimitError
        d = timestamp(datetime.now())
        cache_store('last_action:%s' % author.id, d)
        return fn(*args, **kwargs)
    return _fn

def _get_last():
    key = 'last:%s' % env.user.id
    try:
        post_id = filter(lambda s: '/' not in s, cache_get(key))[-1]
    except (IndexError, TypeError):
        return None
    return post_id

def _store_last(inst):
    if isinstance(inst, Post):
        item = inst.id
    elif isinstance(inst, Comment):
        item = '%s/%s' % (inst.post.id, inst.id)

    key = 'last:%s' % inst.author.id

    items = cache_get(key)
    if not items:
        items = []
    elif not isinstance(items, (list, tuple)):
        items = [items]

    items.append(item)

    cache_store(key, items[-10:])

def _thumbnails(text):
    urls = re.finditer(ur'(?P<url>(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[^\s\?\u0002\u0003]*)*)(?P<qs>\?[^#\s\u0002\u0003]*)?(?:#(?P<hash>\S+))?)',
                      text)

    for m in urls:
        url = m.group('url')

        imgm = re.search(r'\.(?P<ext>jpe?g|png|gif)(:large)?$', m.group('path'), re.I)
        if (imgm \
            or re.search("^http://ompldr.org/v[A-Z][a-zA-Z0-9]+$", url, re.I) \
            or url.startswith("http://img.leprosorium.com") \
            or url.startswith("http://pics.livejournal.com/")) \
            and not re.search(r'https?://(www\.)?dropbox.com', url, re.I):

            make_thumbnail(url)
            return

        if re.search(r'https?://(www\.)?dropbox.com', url, re.I):
            make_thumbnail('%s://dl.dropboxusercontent.com%s' % \
                           (m.group('proto'), m.group('path')))

#@check_auth
def show_post(post_id):
    """
    Return Post instance
    """
    if isinstance(post_id, Post):
        post = post_id
        post_id = post.id
    else:
        tz = env.user.get_profile('tz') if env.user.id else settings.timezone
        post = Post(post_id, tz=tz)

    if post.private and not env.user.id:
        raise SubscribeError

    if post.private and env.user != post.author:
        res = db.fetchone("SELECT 1 FROM posts.recipients "
                         "WHERE post_id=%s AND user_id=%s;",
                         [unb26(post_id), env.user.id])
        if not res:
            raise SubscribeError

    if post.author.id != env.user.id and post.author.get_profile('private'):
        if post.author.check_whitelist(env.user):
            return post

        res = db.fetchone("SELECT 1 FROM posts.recipients "
                         "WHERE post_id=%s AND user_id=%s;",
                         [unb26(post_id), env.user.id])
        if not res:
            raise SubscribeError

    if post.author.get_profile('deny_anonymous') and not env.user.is_authorized():
        raise PostAuthorError

    return post

@check_last_action
@check_auth
def add_post(post, title=None, link=None, tags=None, author=None, to=None,
        private=False, type='post', auto_subscribe=True, files=None):
    """
    Add a new post
    """
    if isinstance(post, Post):
        if post.id:
            raise PostUpdateError
    elif isinstance(post, (str, unicode)):
        if not author:
            author = env.user
        text = post.strip()

        post = Post(None, author=author, title=title, link=link, tags=tags,
                    private=private, text=text.strip(), type=type)

    post.tune = author.get_tune()

    if len(post.text) < 3 and not files:
        raise PostTextError

    m = re.search(r'^\s*(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)(?P<text>.*)', post.text)
    if m and len(m.group('text').strip()) < 3:
        raise PostTextError

    if post.tags:
        post.tags = filter(None, post.tags)

    to_users = []
    subscribers = []

    if to:
        for login in uniqify(to):
            user = User('login', login)
            if user.check_blacklist(author):
                raise SubscribeError(login)
            to_users.append(user)

        subscribers = [ u.id for u in to_users ]

    if not post.private:
        hl = map(lambda l: l.lower(), re.findall(_user_re, post.text))
        if hl:
            hl_sql = ("UNION "
                      "SELECT u.id FROM users.logins u "
                      "JOIN users.profile_im p ON u.id=p.id "
                      "WHERE lower(u.login)=ANY(public.array_lowercase(%(hl)s)) "
                      "AND p.highlight=TRUE ")
        else:
            hl_sql = ""

        if post.author.get_profile('private'):
            if post.tags:
                #if isinstance(post.tags[0], unicode):
                #    post.tags = map(lambda t: t.encode('utf-8'), post.tags)
                #tags = [ t[:64] for t in tags[:10] ]
                res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                                  "to_user_id=%(id)s "
                                  "EXCEPT "
                                  "SELECT user_id FROM posts.tags_blacklist "
                                  "WHERE tag = ANY(%(tags)s) "
                                  "AND (to_user_id IS NULL "
                                       "OR to_user_id=%(id)s);",
                                  {'id': post.author.id, 'tags': post.tags})
            else:
                res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                                  "to_user_id=%s;", [post.author.id])

        else:
            if post.tags:
                #if isinstance(post.tags[0], unicode):
                #    post.tags = map(lambda t: t.encode('utf-8'), post.tags)
                #tags = [ t[:64] for t in tags[:10] ]
                res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                                  "to_user_id=%%(id)s "
                                  "UNION "
                                  "SELECT t.user_id FROM subs.tags t "
                                  #"JOIN users.whitelist w ON w.user_id=%%(id)s "
                                  #     "AND t.user_id=w.to_user_id "
                                  "WHERE lower(t.tag) = ANY(array_lowercase(%%(tags)s)) "
                                  "AND (t.to_user_id IS NULL "
                                       "OR t.to_user_id=%%(id)s) "
                                  "%s"
                                  "EXCEPT "
                                  "SELECT user_id FROM users.blacklist WHERE "
                                  "to_user_id=%%(id)s "
                                  "EXCEPT "
                                  "SELECT user_id FROM posts.tags_blacklist "
                                  "WHERE lower(tag) = ANY(array_lowercase(%%(tags)s)) "
                                  "AND (to_user_id IS NULL "
                                       "OR to_user_id=%%(id)s);" % hl_sql,
                                  {'id': post.author.id, 'tags': post.tags,
                                   'hl': hl})
            else:
                res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                                  "to_user_id=%%(id)s "
                                  "%s"
                                  "EXCEPT "
                                  "SELECT user_id FROM users.blacklist WHERE "
                                  "to_user_id=%%(id)s;" % hl_sql,
                                  {'id':post.author.id, 'hl':hl})

        subscribers.extend(
                filter(lambda u: u!=post.author.id and u not in subscribers,
                       map(lambda u: u[0], res)))

    if isinstance(files, (list, tuple)):
        post.files = files

    post_id = post.save()

    for u in to_users:
        try:
            db.perform("INSERT INTO posts.recipients (post_id, user_id) "
                       "VALUES (%s, %s);", [unb26(post_id), u.id])
        except IntegrityError:
            pass

    publish('msg.self', {
        'to': [env.user.id],
        'a': 'post',
        'post_id': post_id,
        'type': post.type,
        'author': post.author.login,
        'author_id': post.author.id,
        'author_name': post.author.get_info('name'),
        'tags': post.tags,
        'private': post.private,
        'title': post.title,
        'text': post.text,
        'link': post.link,
        'to_users': [u.login for u in to_users],
        'files': files,
        'cut': True
    })

    if subscribers:
        publish('msg', {
            'to': subscribers,
            'a': 'post',
            'post_id': post_id,
            'type': post.type,
            'author': post.author.login,
            'author_id': post.author.id,
            'author_name': post.author.get_info('name'),
            'tags': post.tags,
            'private': post.private,
            'title': post.title,
            'text': post.text,
            'link': post.link,
            'to_users': [u.login for u in to_users],
            'files': files,
            'cut': True
        })

        if post.private:
            ptype = 'private'
        else:
            ptype = post.type

        try:
            db.batch("INSERT INTO posts.unread_posts "
                     "(user_id, post_id, type) VALUES (%s, %s, %s)",
                     [(u, unb26(post_id), ptype) for u in subscribers])
        except IntegrityError:
            pass

        try:
            db.batch("INSERT INTO posts.recommendations_recv "
                     "(post_id, comment_id, user_id) VALUES (%s, %s, %s);",
                     [(unb26(post_id), 0, u) for u in subscribers])
        except IntegrityError:
            pass

        if post.private:
            add_private_unread([env.user.id] + subscribers, unb26(post_id))

    if auto_subscribe:
        try:
            post.author.subscribe(post)
        except AlreadySubscribed:
            pass

    _store_last(post)

    _thumbnails(post.text)

    return post_id

@check_auth
def delete_post(post_id):
    """
    Delete post
    """
    post = Post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    post.delete()

    # TODO: publish

@check_auth
def edit_post(post_id, text=None, tags=None, private=None, files=None):
    if isinstance(post_id, Post):
        post = post_id
        post_id = post.id
    else:
        post = show_post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    if post.edited:
        raise PostUpdateError
    #if post.comments_count() > 0:
    #    raise PostCommentedError

    if datetime.now() - timedelta(seconds=settings.edit_expire) \
            > post.created:
        raise PostUpdateError

    if not text and tags is None and private is None:
        return

    if text and post.text != text:
        m = re.search(r'^\s*(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)(?P<text>.*)', text)
        if m and len(m.group('text').strip()) < 3:
            raise PostTextError
        if not diff_ratio(post.text, text):
            raise PostDiffError

        post.edited = True
        post.text = text.decode('utf-8') if isinstance(text, str) else text

    if tags is not None:
        update_tags(post, tags, False)

    if files is not None and isinstance(files, (list, tuple)):
        post.files = files

    post.save()

    if text and not post.private:
        hl = map(lambda l: l.lower(),re.findall(_user_re, text))
        if hl:
            hl_sql = ("UNION "
                      "SELECT u.id FROM users.logins u "
                      "JOIN users.profile_im p ON u.id=p.id "
                      "WHERE lower(u.login)=ANY(%(hl)s) AND p.highlight=TRUE ")
        else:
            hl_sql = ""

        res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                          "to_user_id=%%(id)s "
                          "%s"
                          "UNION "
                          "SELECT user_id FROM posts.recipients "
                          "WHERE post_id=%%(post_id)s "
                          "EXCEPT "
                          "SELECT user_id FROM posts.tags_blacklist "
                          "WHERE tag = ANY(%%(tags)s) "
                          "AND (to_user_id IS NULL "
                               "OR to_user_id=%%(id)s)"
                          "EXCEPT "
                          "SELECT user_id FROM users.blacklist WHERE "
                          "to_user_id=%%(id)s;" % hl_sql,
                          {'id':env.user.id, 'post_id':unb26(post.id),
                            'hl':hl, 'tags': tags})
        subscribers = filter(lambda u: u!=env.user.id, map(lambda u: u[0], res))

    else:
        subscribers = [ u.id for u in post.recipients() ]

    if subscribers:
        publish('msg', {
            'to': subscribers,
            'a': 'post_edited',
            'post_id': post.id,
            'author': env.user.login,
            'author_id': env.user.id,
            'tags': tags,
            'text': text,
            'private': post.private,
            'files': files,
            'cut': True
        })

    _thumbnails(text)
    cache_del('md:%s' % post.id)
    cache_del('mdx:%s' % post.id)

@check_auth
def update_post(post_id, text):
    """
    Update an existing post
    """
    text = text.strip()
    if len(text) < 3 or len(text) > 1048576:
        raise PostTextError

    post = show_post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    post.update(text)

    if not post.private:
        hl = map(lambda l: l.lower(),re.findall(_user_re, text))
        if hl:
            hl_sql = ("UNION "
                      "SELECT u.id FROM users.logins u "
                      "JOIN users.profile_im p ON u.id=p.id "
                      "WHERE lower(u.login)=ANY(%(hl)s) AND p.highlight=TRUE ")
        else:
            hl_sql = ""

        res = db.fetchall("SELECT user_id FROM subs.users WHERE "
                          "to_user_id=%%(id)s "
                          "%s"
                          "UNION "
                          "SELECT user_id FROM posts.recipients "
                          "WHERE post_id=%%(post_id)s "
                          "EXCEPT "
                          "SELECT user_id FROM users.blacklist WHERE "
                          "to_user_id=%%(id)s;" % hl_sql,
                          {'id':env.user.id, 'post_id':unb26(post.id),
                           'hl':hl})
        subscribers = filter(lambda u: u!=env.user.id, map(lambda u: u[0], res))

    else:
        subscribers = [ u.id for u in post.recipients() ]

    if subscribers:
        publish('msg', {
            'to': subscribers,
            'a': 'post_upd',
            'id': post_id,
            'author': env.user.login,
            'author_id': env.user.id,
            'text': text
        })

@check_auth
def update_tags(post_id, taglist, save=True):
    """
    Update tags
    """
    if isinstance(post_id, Post):
        post = post_id
    else:
        post = Post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    post.tags = taglist
    if save:
        post.save()

def select_posts(author=None, author_private=None, deny_anonymous=None, private=None, tags=None,
                 blacklist=False, limit=10, offset=0, asc=False, before=None):
    if author and isinstance(author, (int, long)):
        author = User(author)

    requesting_key = 'requesting:%s' % (env.user.id)
    if cache_get(requesting_key):
        raise PostNotFound
    cache_store(requesting_key, '1', 5)

    if author and author.id != env.user.id:
        if author.get_profile('private') and not author.check_whitelist(env.user):
            raise PostAuthorError

        if author.get_profile('deny_anonymous') and not env.user.is_authorized():
            raise PostAuthorError

    if before and isinstance(before, (int, long)):
        offset = before - 157321
        offset_cond = " OFFSET %d" % offset
    elif offset:
        offset_cond = " OFFSET %d" % int(offset)
    else:
        offset = 0
        offset_cond = ""

    joins = []
    if tags:
        joins.append("JOIN posts.tags t ON p.id=t.post_id")
    if tags or author_private is not None:
        joins.append("JOIN users.profile up ON up.id=u.id")

    if env.user.id:
        query = ("SELECT DISTINCT p.id, NULL AS comment_id, "
                 "p.author, u.login, i.name, i.avatar, "
                 "u.type AS user_type, "
                 "p.private, p.created at time zone '%(tz)s' as created, p.resource, "
                 "p.type, p.title, p.link, p.tags, p.text, "
                 "(p.edited=false AND p.created+interval '1800 second' >= now()) AS editable, "
                 "p.archive, p.files, "
                 "sp.post_id AS subscribed, "
                 "rp.post_id AS recommended, "
                 "rb.post_id AS bookmarked "
                 "FROM posts.posts p JOIN users.logins u ON p.author=u.id "
                 " %(joins)s "
                 "JOIN users.info i ON p.author=i.id "
                 "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                    "AND sp.user_id=%(user_id)s "
                 "LEFT OUTER JOIN posts.recommendations rp "
                    "ON %(user_id)s=rp.user_id AND "
                    "p.id=rp.post_id  AND rp.comment_id=0 "
                "LEFT OUTER JOIN posts.bookmarks rb "
                    "ON p.id=rb.post_id AND %(user_id)s=rb.user_id AND "
                    "rb.comment_id=0 " % \
                 {'joins': ' '.join(joins), 'user_id': env.user.id, 'tz': env.user.get_profile('tz')})
    else:
        query = ("SELECT DISTINCT p.id, NULL AS comment_id, "
                 "p.author, u.login, i.name, i.avatar,"
                 "p.private, p.created at time zone '%(tz)s' as created, p.resource, "
                 "p.type, p.title, p.link, p.tags, p.text, "
                 "p.archive, p.files, "
                 "false AS editable, "
                 "false AS subscribed, "
                 "false AS recommended, "
                 "false AS bookmarked "
                 "FROM posts.posts p JOIN users.logins u ON p.author=u.id "
                 " %(joins)s "
                 "JOIN users.info i ON p.author=i.id " % \
                 {'joins': ' '.join(joins), 'tz': settings.timezone})
    cond = []
    params = []
    if author:
        cond.append("p.author=%s")
        params.append(author.id)

    if private is not None:
        cond.append("p.private=%s")
        params.append(private)

    if tags:
        cond.append("LOWER(t.tag)=ANY(public.array_lowercase(%s))")
        params.append(tags)

    if author_private is not None:
        cond.append("up.private=%s")
        params.append(author_private)

    if deny_anonymous is not None:
        cond.append('up.deny_anonymous=%s')
        params.append(deny_anonymous)

    if env.user.id and blacklist:
        cond.append("p.author NOT IN (SELECT to_user_id FROM users.blacklist "
                         "WHERE user_id=%s)")
        params.append(env.user.id)

    if cond:
        query += " WHERE " + " AND ".join(cond)

    order = 'ASC' if asc else 'DESC'
    #offset = ' OFFSET %d' % offset if offset else ''
    limit = ' LIMIT %d' % limit if limit else ''

    query += (" ORDER BY created %s %s %s;" % (order, offset_cond, limit))

    res = db.fetchall(query, params)

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 157321 + offset + i + 1
        plist.append(r)

    cache_del(requesting_key)

    return _plist(plist)

@check_auth
def recent_posts(limit=10, offset=0, asc=False, type=None, unread=False, before=None):
    """
    Get recent incoming posts/recommendations
    """
    requesting_key = 'requesting:%s' % (env.user.id)
    if cache_get(requesting_key):
        raise PostNotFound
    cache_store(requesting_key, '1', 5)

    order = 'ASC' if asc else 'DESC'

    type_cond = " AND p.type='%s'" % type if type else ''

    if before and isinstance(before, (int, long)):
        before_cond = " AND r.id < %d" % before
        offset = ""
    elif offset:
        before_cond = ""
        offset = " OFFSET %d" % int(offset)
    else:
        before_cond = ""
        offset = ""

    if unread:
        log.info('============== res unread --')
        res = db.fetchall(
            "SELECT "
            "r.user_id, r.post_id AS id,"
            "p.author,"
            "up.login,"
            "ip.name,"
            "ip.avatar,"
            "up.type,"
            "p.text,"
            "p.archive, p.files, "
            "p.tags, p.title, p.link, "
            "p.created at time zone %%(tz)s AS created, "
            "p.edited, p.type, "
            "p.private, "
            "(p.edited=false AND p.created+interval '%%(edit_expire)s second' >= now())"
                "AS editable, "
            "sp.post_id AS subscribed, "
            "rp.post_id AS recommended, "
            "rb.post_id AS bookmarked "
            "FROM posts.unread_posts r "
            "LEFT JOIN users.logins ur ON r.user_id=ur.id "
            "LEFT JOIN posts.posts p ON r.post_id=p.id "
            "LEFT JOIN users.logins up ON p.author=up.id "
            "LEFT JOIN users.info ip ON p.author=ip.id "
            "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                "AND sp.user_id=%%(user_id)s "
            "LEFT OUTER JOIN posts.recommendations rp "
               "ON %%(user_id)s=rp.user_id AND "
               "r.post_id=rp.post_id  AND rp.comment_id=0 "
            "LEFT OUTER JOIN posts.bookmarks rb "
               "ON %%(user_id)s=rb.user_id AND "
               "r.post_id=rb.post_id  AND rb.comment_id=0 "
            "WHERE r.user_id=%%(user_id)s %s "
            "ORDER BY p.created %s "
            "%s LIMIT %%(limit)s;" % (type_cond, order, offset),
            {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
             'limit': limit, 'edit_expire': settings.edit_expire})
    else:
        recent = db.fetchall(
            "SELECT id FROM posts.recent WHERE user_id=%s LIMIT 1;",
            [env.user.id]
        )

        if not recent:
            return []

        res = db.fetchall(
            "SELECT "
            "r.id AS uid, "
            "r.user_id, r.is_rec, r.post_id AS id,r.comment_id, "
            "rc.text AS r_text, rc.rcid AS r_comment_id,"
            "CASE WHEN r.comment_id>0 THEN c.author ELSE p.author END "
               "AS author, "
            "CASE WHEN r.comment_id>0 THEN uc.login ELSE up.login END "
               "AS login, "
            "CASE WHEN r.comment_id>0 THEN ic.name ELSE ip.name END "
               "AS name, "
            "CASE WHEN r.comment_id>0 THEN ic.avatar ELSE ip.avatar END "
               "AS avatar, "
            "CASE WHEN r.comment_id>0 THEN uc.type ELSE up.type END "
               "AS user_type, "
            "CASE WHEN r.is_rec THEN ur.id ELSE NULL END "
               "AS r_author, "
            "CASE WHEN r.is_rec THEN ur.login ELSE NULL END "
               "AS r_login, "
            "CASE WHEN r.is_rec THEN ir.name ELSE NULL END "
               "AS r_name, "
            "CASE WHEN r.is_rec THEN ir.avatar ELSE NULL END "
               "AS r_avatar, "
            "p.private, "
            "CASE WHEN r.comment_id>0 THEN c.text ELSE p.text END "
               "AS text, "
            "p.archive, "
            "CASE WHEN r.comment_id>0 THEN c.files ELSE p.files END AS files, "
            "sp.post_id AS subscribed, "
            "rp.post_id AS recommended, "
            "rb.post_id AS bookmarked, "
            "p.tags, p.title, p.link, "
            "r.created at time zone %%(tz)s AS created, "
            "p.edited, p.type, "
            "(p.edited=false AND r.created+interval '%%(edit_expire)s second' >= now())"
                "AS editable "
            "FROM posts.recent r "
            "LEFT JOIN users.logins ur ON r.user_id=ur.id "
            "LEFT JOIN posts.posts p ON r.post_id=p.id "
            "LEFT JOIN users.logins up ON p.author=up.id "
            "LEFT JOIN users.info ip ON p.author=ip.id "
            "LEFT OUTER JOIN users.info ir ON r.user_id=ir.id "
            "LEFT OUTER JOIN posts.recommendations rc "
               "ON r.is_rec=true AND r.user_id=rc.user_id AND "
               "r.post_id=rc.post_id  AND "
               "COALESCE(r.comment_id, 0)=rc.comment_id "
            "LEFT OUTER JOIN posts.comments c "
               "ON r.post_id=c.post_id AND r.comment_id=c.comment_id "
            "LEFT OUTER JOIN users.logins uc ON c.author=uc.id "
            "LEFT OUTER JOIN users.info ic ON uc.id=ic.id "
            "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                "AND sp.user_id=%%(user_id)s "
            "LEFT OUTER JOIN posts.recommendations rp "
               "ON %%(user_id)s=rp.user_id AND "
               "r.post_id=rp.post_id  AND "
               "COALESCE(r.comment_id, 0)=rp.comment_id "
            "LEFT OUTER JOIN posts.bookmarks rb "
               "ON %%(user_id)s=rb.user_id AND "
               "r.post_id=rb.post_id  AND "
               "COALESCE(r.comment_id, 0)=rb.comment_id "
            "WHERE r.rcpt_id=%%(user_id)s %s %s "
            "ORDER BY r.created %s "
            "%s LIMIT %%(limit)s;" % (type_cond, before_cond, order, offset),
            {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
             'limit': limit, 'edit_expire': settings.edit_expire})

    cache_del(requesting_key)
    return _plist(res)

def recent_blog_posts(author=None, limit=10, offset=0, asc=False, before=None):
    """
    Get user's recent posts/recommendations
    """
    if author and isinstance(author, (int, long)):
        author = User(author)

    if author and author.id != env.user.id:
        if author.get_profile('private') and not author.check_whitelist(env.user):
            raise PostAuthorError

    if author.get_profile('deny_anonymous') and not env.user.is_authorized():
        raise PostAuthorError

    order = 'ASC' if asc else 'DESC'

    if before and isinstance(before, (int, long)):
        before_cond = " AND r.id < %d" % before
        offset = ""
    elif offset:
        before_cond = ""
        offset = " OFFSET %d" % int(offset)
    else:
        before_cond = ""
        offset = ""

    res = db.fetchall(
        "SELECT "
        "r.id AS uid,"
        "r.user_id, r.is_rec, r.post_id AS id,r.comment_id, "
        "rc.text AS r_text, rc.rcid AS r_comment_id,"
        "CASE WHEN r.comment_id>0 THEN c.author ELSE p.author END "
           "AS author, "
        "CASE WHEN r.comment_id>0 THEN uc.login ELSE up.login END "
           "AS login, "
        "CASE WHEN r.comment_id>0 THEN ic.name ELSE ip.name END "
           "AS name, "
        "CASE WHEN r.comment_id>0 THEN ic.avatar ELSE ip.avatar END "
           "AS avatar, "
        "CASE WHEN r.comment_id>0 THEN uc.type ELSE up.type END "
           "AS user_type, "
        "CASE WHEN r.is_rec THEN ur.id ELSE NULL END "
           "AS r_author, "
        "CASE WHEN r.is_rec THEN ur.login ELSE NULL END "
           "AS r_login, "
        "CASE WHEN r.is_rec THEN ir.name ELSE NULL END "
           "AS r_name, "
        "CASE WHEN r.is_rec THEN ir.avatar ELSE NULL END "
           "AS r_avatar, "
        "p.private, "
        "CASE WHEN r.comment_id>0 THEN c.text ELSE p.text END "
           "AS text, "
        "CASE WHEN r.comment_id>0 THEN c.files ELSE p.files END AS files, "
        "p.archive, p.pinned AS pinned, "
        "(CASE WHEN p.author != %%(author_id)s THEN FALSE "
            "ELSE p.pinned END) AS pinned_sort, "
        "sp.post_id AS subscribed, "
        "rp.post_id AS recommended, "
        "rb.post_id AS bookmarked, "
        "p.tags, p.title, p.link, "
        "r.created at time zone %%(tz)s AS created, "
        "p.edited, p.type, "
        "(p.edited=false AND r.created+interval '%%(edit_expire)s second' >= now())"
            "AS editable "
        "FROM posts.recent_blog r "
        "LEFT JOIN users.logins ur ON r.user_id=ur.id "
        "LEFT OUTER JOIN users.info ir ON r.user_id=ir.id "
        "LEFT OUTER JOIN posts.recommendations rc "
           "ON r.is_rec=true AND r.user_id=rc.user_id AND "
           "r.post_id=rc.post_id  AND r.comment_id=rc.comment_id "
        "LEFT JOIN posts.posts p ON r.post_id=p.id "
        "LEFT JOIN users.logins up ON p.author=up.id "
        "LEFT OUTER JOIN users.info ip ON p.author=ip.id "
        "LEFT OUTER JOIN users.profile pp ON p.author=pp.id "
        "LEFT OUTER JOIN users.whitelist w "
            "ON w.user_id=p.author AND w.to_user_id=%%(user_id)s "
        "LEFT OUTER JOIN posts.comments c "
           "ON r.post_id=c.post_id AND r.comment_id=c.comment_id "
        "LEFT OUTER JOIN users.logins uc ON c.author=uc.id "
        "LEFT OUTER JOIN users.info ic ON uc.id=ic.id "
        "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
            "AND sp.user_id=%%(user_id)s "
        "LEFT OUTER JOIN posts.recommendations rp "
           "ON r.is_rec=true AND %%(user_id)s=rp.user_id AND "
           "r.post_id=rp.post_id  AND "
           "COALESCE(r.comment_id, 0)=rp.comment_id "
        "LEFT OUTER JOIN posts.bookmarks rb "
           "ON %%(user_id)s=rb.user_id AND "
           "r.post_id=rb.post_id  AND "
           "COALESCE(r.comment_id, 0)=rb.comment_id "
        "WHERE r.user_id=%%(author_id)s AND "
            "(w.user_id IS NOT NULL OR pp.private=false "
             "OR r.user_id=%%(user_id)s) %s "
        "ORDER BY pinned_sort DESC, r.created %s "
        "%s LIMIT %%(limit)s;"% (before_cond, order, offset),
        {'user_id': env.user.id, 'author_id': author.id,
         'tz': env.user.get_profile('tz'),
         'limit': limit,
         'edit_expire': settings.edit_expire})

    return _plist(res)

def add_private_unread(users, post_id):
    if not isinstance(users, (list, tuple)):
        users = [users]
    redis = RedisPool(settings.storage_socket)
    for u in users:
        key = 'private_unread:%s' % u
        ids = redis.get(key)
        if ids:
            ids = [post_id] + filter(lambda id: int(id)!=post_id, ids.split(','))
        else:
            ids = [post_id]

        redis.set(key, ','.join(map(lambda id: str(id), ids[:100])))

def del_private_unread(users, post_id):
    if not isinstance(users, (list, tuple)):
        users = [users]
    redis = RedisPool(settings.storage_socket)
    for u in users:
        key = 'private_unread:%s' % u
        ids = redis.get(key)
        if ids:
            ids = filter(lambda id: int(id)!=post_id, ids.split(','))
            redis.set(key, ','.join(map(lambda id: str(id), ids[:100])))

@check_auth
def private_unread(limit=10, offset=0, asc=False, before=None):
    """
    Get recently updated private posts
    """
    if before and isinstance(before, (int, long)):
        offset = before - 157321

    redis = RedisPool(settings.storage_socket)
    ids = redis.get('private_unread:%s' % env.user.id)
    if not ids:
        return []

    ids = map(lambda id: int(id), ids.split(','))[offset:offset+limit]

    res = db.fetchall(
        "SELECT "
        "p.id, p.author, u.login, i.name, i.avatar, p.private, "
        "p.created at time zone %(tz)s AS created,"
        "p.resource, "
        "p.type, p.title, p.link, p.tags, p.text, "
        "p.edited,"
        "(p.edited=false AND p.created+interval '%(edit_expire)s second' >= now())"
            "AS editable, "
        "p.archive, p.files, "
        "sp.post_id AS subscribed, "
        "rp.post_id AS recommended, "
        "rb.post_id AS bookmarked "
        "FROM unnest(%(ids)s) "
        "JOIN posts.posts p ON p.id=unnest "
        "JOIN users.logins u ON u.id=p.author "
        "LEFT OUTER JOIN users.info i ON i.id=p.author "
        "LEFT OUTER JOIN posts.recipients rcp ON rcp.post_id=p.id "
        "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                    "AND sp.user_id=%(user_id)s "
        "LEFT OUTER JOIN posts.recommendations rp "
                    "ON %(user_id)s=rp.user_id AND "
                    "p.id=rp.post_id  AND rp.comment_id=0 "
        "LEFT OUTER JOIN posts.bookmarks rb "
            "ON p.id=rb.post_id AND %(user_id)s=rb.user_id AND "
            "rb.comment_id=0 "
        "WHERE p.private=true;",
        {'ids': ids, 'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
         'limit': limit, 'edit_expire': settings.edit_expire})

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 157321 + offset + i + 1
        plist.append(r)
    return _plist(plist)

@check_auth
def private_outgoing(limit=10, offset=None, asc=False, before=None):
    """
    Get outgoing private posts
    """
    order = 'ASC' if asc else 'DESC'

    if before and isinstance(before, (int, long)):
        offset = before - 157321
        offset_cond = " OFFSET %d" % offset
    elif offset:
        offset_cond = " OFFSET %d" % int(offset)
    else:
        offset = 0
        offset_cond = ""

    res = db.fetchall(
        "SELECT "
        "p.id, p.author, u.login, i.name, i.avatar, p.private, "
        "p.created at time zone %%(tz)s AS created,"
        "p.resource, "
        "p.type, p.title, p.link, p.tags, p.text, "
        "p.edited,"
        "(p.edited=false AND p.created+interval '%%(edit_expire)s second' >= now())"
            "AS editable, "
        "p.archive, p.files, "
        "sp.post_id AS subscribed, "
        "rp.post_id AS recommended, "
        "rb.post_id AS bookmarked "
        "FROM posts.posts p "
        "JOIN users.logins u ON u.id=p.author "
        "LEFT OUTER JOIN users.info i ON i.id=p.author "
        "LEFT OUTER JOIN posts.recipients rcp ON rcp.post_id=p.id "
        "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                    "AND sp.user_id=%%(user_id)s "
        "LEFT OUTER JOIN posts.recommendations rp "
                    "ON %%(user_id)s=rp.user_id AND "
                    "p.id=rp.post_id  AND rp.comment_id=0 "
        "LEFT OUTER JOIN posts.bookmarks rb "
            "ON p.id=rb.post_id AND %%(user_id)s=rb.user_id AND "
            "rb.comment_id=0 "
        "WHERE p.author=%%(user_id)s AND p.private=true "
        "GROUP BY p.id, u.login, i.name, i.avatar, sp.post_id, rp.post_id, rb.post_id "
        "ORDER BY p.created %s "
        "%s LIMIT %%(limit)s;"% (order, offset_cond),
        {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
         'offset': offset, 'limit': limit,
         'edit_expire': settings.edit_expire})

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 157321 + offset + i + 1
        plist.append(r)
    return _plist(plist)

@check_auth
def private_incoming(limit=10, offset=None, asc=False, before=None):
    """
    Get incoming private posts
    """
    order = 'ASC' if asc else 'DESC'

    if before and isinstance(before, (int, long)):
        offset = before - 157321
        offset_cond = " OFFSET %d" % offset
    elif offset:
        offset_cond = " OFFSET %d" % int(offset)
    else:
        offset = 0
        offset_cond = ""

    res = db.fetchall(
        "SELECT "
        "p.id, p.author, u.login, i.name, i.avatar, p.private, "
        "p.created at time zone %%(tz)s AS created,"
        "p.resource, "
        "p.type, p.title, p.link, p.tags, p.text, "
        "p.edited,"
        "(p.edited=false AND p.created+interval '%%(edit_expire)s second' >= now())"
            "AS editable, "
        "p.archive, p.files, "
        "sp.post_id AS subscribed, "
        "rp.post_id AS recommended, "
        "rb.post_id AS bookmarked "
        "FROM posts.posts p "
        "JOIN users.logins u ON u.id=p.author "
        "LEFT OUTER JOIN users.info i ON i.id=p.author "
        "LEFT OUTER JOIN posts.recipients rcp ON rcp.post_id=p.id "
        "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                    "AND sp.user_id=%%(user_id)s "
        "LEFT OUTER JOIN posts.recommendations rp "
                    "ON %%(user_id)s=rp.user_id AND "
                    "p.id=rp.post_id  AND rp.comment_id=0 "
        "LEFT OUTER JOIN posts.bookmarks rb "
            "ON p.id=rb.post_id AND %%(user_id)s=rb.user_id AND "
            "rb.comment_id=0 "
        "WHERE rcp.user_id=%%(user_id)s AND p.private=true "
        "ORDER BY p.created %s "
        "%s LIMIT %%(limit)s;"% (order, offset_cond),
        {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
         'limit': limit, 'edit_expire': settings.edit_expire})

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 157321 + offset + i + 1
        plist.append(r)
    return _plist(plist)

@check_auth
def recent_commented_posts(limit=10, offset=None, asc=False, unread=False, before=None):
    order = 'ASC' if asc else 'DESC'

    if before and isinstance(before, (int, long)):
        offset = before - 131072
        offset_cond = " OFFSET %d" % offset
    elif offset:
        offset_cond = " OFFSET %d" % int(offset)
    else:
        offset = 0
        offset_cond = ""

    if unread:
        res = db.fetchall(
            "SELECT "
            "p.id, p.type, p.author, u.login, i.name, i.avatar, p.private, "
            "p.title, p.text, p.tags, p.link, "
            "p.created at time zone %%(tz)s AS created, "
            "p.edited, "
            "(p.edited=false AND p.created+interval '1800 second' >= now()) AS editable, "
            "max(unc.comment_id) AS lc_id, "
            "p.archive, p.files, "
            "sp.post_id AS subscribed, "
            "rp.post_id AS recommended, "
            "rb.post_id AS bookmarked "
            "FROM posts.unread_comments unc "
            "JOIN posts.posts p ON p.id=unc.post_id "
            "JOIN users.logins u ON p.author=u.id "
            "LEFT OUTER JOIN users.info i ON p.author=i.id "
            "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
                "AND sp.user_id=%%(user_id)s "
            "LEFT OUTER JOIN posts.recommendations rp "
               "ON p.id=rp.post_id AND %%(user_id)s=rp.user_id AND "
               "rp.comment_id=0 "
            "LEFT OUTER JOIN posts.bookmarks rb "
               "ON p.id=rb.post_id AND %%(user_id)s=rb.user_id AND "
               "rb.comment_id=0 "
            "WHERE unc.user_id=%%(user_id)s AND p.private=false "
            "GROUP BY unc.post_id, p.id, u.login, i.name, i.avatar, "
                "sp.post_id, rp.post_id, rb.post_id "
            "ORDER BY max(unc.created) DESC "
            "%s LIMIT %%(limit)s;" % (offset_cond),
            {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
             'limit': limit, 'edit_expire': settings.edit_expire})
    else:
        res = db.fetchall(
            "SELECT "
            "p.id, p.type, p.author, u.login, i.name, i.avatar, p.private, "
            "p.title, p.text, p.tags, p.link, "
            "p.created at time zone %%(tz)s AS created, "
            "p.edited, "
            "(p.edited=false AND p.created+interval '1800 second' >= now()) AS editable, "
            "max(c.comment_id) AS lc_id, "
            "p.archive, p.files, "
            "true AS subscribed, "
            "rp.post_id AS recommended, "
            "rb.post_id AS bookmarked "
            "FROM subs.posts s "
            "JOIN posts.posts p ON p.id=s.post_id "
            "JOIN posts.comments c ON p.id=c.post_id "
            "LEFT JOIN users.logins u ON p.author=u.id "
            "LEFT OUTER JOIN users.info i ON p.author=i.id "
            "LEFT OUTER JOIN posts.recommendations rp "
               "ON p.id=rp.post_id AND %%(user_id)s=rp.user_id AND "
               "rp.comment_id=0 "
            "LEFT OUTER JOIN posts.bookmarks rb "
               "ON p.id=rb.post_id AND %%(user_id)s=rb.user_id AND "
               "rb.comment_id=0 "
            "WHERE s.user_id=%%(user_id)s AND p.private=false "
            "GROUP BY p.id, u.login, i.name, i.avatar, rp.post_id, rb.post_id "
            "ORDER BY max(c.created) %s "
            "%s LIMIT %%(limit)s;"% (order, offset_cond),
            {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
             'limit': limit, 'edit_expire': settings.edit_expire})

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 131072 + offset + i + 1
        plist.append(r)
    return _plist(plist)

@check_last_action
@check_auth
def add_comment(post_id, to_comment_id, text, files=None,
                dont_subscribe=False, force=False):
    """
    Add a comment
    """
    text = text.strip()
    if isinstance(text, str):
        text = text.decode('utf-8', 'ignore')
    if len(text) > 4096:
        text = text[:4096]

    if not text and not files:
        raise PostTextError

    m = re.search(r'^\s*(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)(?P<text>.*)', text)
    if m and not m.group('text').strip() and not files:
        raise PostTextError

    post = show_post(post_id)

    if post.tags and u'readonly' in post.tags and post.author.id != env.user.id:
        raise PostReadonlyError

    if post.archive:
        raise SubscribeError

    if post.author.check_blacklist(env.user):
        raise PostAuthorError

    if to_comment_id:
        to_comment = Comment(post, to_comment_id)
        to_text = to_comment.text
    else:
        to_comment = None
        to_text = post.text

    comment = Comment.from_data(post, None, author=env.user,
                                to_comment_id=to_comment_id, text=text,
                                files=files)
    comment_id = comment.save()

    if not post.private:
        hl = map(lambda l: l.lower(), re.findall(_user_re, text))
        res = db.fetchall("SELECT u.id FROM users.logins u "
                          "JOIN users.profile_im p ON u.id=p.id "
                          "WHERE lower(u.login)=ANY(%(hl)s) "
                            "AND p.highlight=TRUE "
                          "EXCEPT "
                          "SELECT user_id FROM users.blacklist WHERE "
                          "to_user_id=%(id)s;", {'id':env.user.id, 'hl':hl})
        hls = [r[0] for r in res]
    else:
        hls = []

    subscribers = filter(lambda u: u!=env.user.id,
                         uniqify(hls+post.get_subscribers(bluser=env.user)))

    publish('msg.self', {
        'to':[env.user.id],
        'a':'comment',
        'author':env.user.login,
        'author_id':env.user.id,
        'post_id':post_id,
        'comment_id':comment_id,
        'text':text,
        'to_comment_id':to_comment_id,
        'to_text':to_text,
        'files':files
    })

    publish('msg', {
        'to': subscribers,
        'a': 'comment',
        'author': env.user.login,
        'author_id': env.user.id,
        'post_id': post_id,
        'comment_id': comment_id,
        'text': text,
        'to_comment_id': to_comment_id,
        'to_text': to_text,
        'files': files
    })

    if post.private:
        ptype = 'private'
    else:
        ptype = post.type

    try:
        db.batch("INSERT INTO posts.unread_comments "
                 "(user_id, post_id, comment_id, type) VALUES (%s, %s, %s, %s)",
                 [(u, unb26(post_id), comment_id, ptype) for u in subscribers])
    except IntegrityError:
        pass

    if post.private:
        add_private_unread([env.user.id] + subscribers, unb26(post_id))

    if not dont_subscribe:
        try:
            env.user.subscribe(post)
        except AlreadySubscribed:
            pass

    #if force:
    #    cache_store('last:%s' % env.user.id,
    #                {'post':post.id, 'comment':comment_id},
    #                expire=600)

    if post.comments_count():
        comment_ids = map(lambda c: c[0],
                   db.fetchall("SELECT comment_id FROM "
                               "posts.unread_comments "
                               "WHERE user_id = %(id)s AND "
                               " post_id = %(pid)s;", 
                               {'id':env.user.id, 'pid':unb26(post_id)}))
        clear_unread_comments(post_id, comment_ids)

    _store_last(comment)

    _thumbnails(text)

    return comment_id

@check_auth
def edit_comment(post_id, comment_id, text, editor=None):
    comment = Comment(post_id, comment_id)

    if datetime.now() - timedelta(seconds=settings.edit_comment_expire) \
        > comment.created:
        raise CommentEditingForbiddenError(post_id, comment_id)

    if not editor:
        editor = env.user

    if comment.author == editor:
        text = text.strip()
        if isinstance(text, str):
            text = text.decode('utf-8', 'ignore')
        if len(text) > 4096:
            text = text[:4096]

        comment.text = text
        comment.save(update=True)

        _thumbnails(comment.text)

    else:
        raise PostAuthorError(post_id, comment_id)

    res = db.fetchall("SELECT user_id FROM subs.posts WHERE post_id=%(post_id)s "
                        "AND user_id!=%(user_id)s"
                      "EXCEPT "
                      "SELECT user_id FROM users.blacklist WHERE "
                      "to_user_id=%(user_id)s;",
                      {'post_id': unb26(post_id), 'user_id': editor.id})

    subscribers = map(lambda u: u[0], res)

    if subscribers:
        publish('msg', {
            'to': subscribers,
            'a': 'comment_edited',
            'post_id': post_id,
            'comment_id': comment_id,
            'author': env.user.login,
            'author_id': env.user.id,
            'text': text,
            'cut': True
        })

    cache_del('md:%s.%s' % (post_id, comment_id))
    cache_del('mdx:%s.%s' % (post_id, comment_id))


@check_auth
def show_comment(post_id, comment_id):
    """
    Get Comment instance
    """
    post = show_post(post_id)
    comment = Comment(post, comment_id)

    clear_unread_comments(post_id, comment_id)

    return comment

@check_auth
def delete_comment(post_id, comment_id):
    """
    Delete comment
    """
    post = Post(post_id)
    comment = Comment(post, comment_id)

    if env.user != post.author and env.user != comment.author:
        raise CommentAuthorError(post.id, comment.id)

    comment.delete()

    return post

@check_auth
def clear_unread_posts(posts=None):
    def _unb(id):
        if not isinstance(id, (int, long)):
            id = unb26(id)
        return id

    if posts:
        if not isinstance(posts, (list, tuple)):
            posts = [posts]
        db.perform("DELETE FROM posts.unread_posts "
                   "WHERE user_id=%s AND post_id=ANY(%s);",
                   [env.user.id, map(_unb, posts)])
    else:
        db.perform("DELETE FROM posts.unread_posts "
                   "WHERE user_id=%s;",
                   [env.user.id])

@check_auth
def clear_unread_comments(post_id=None, comments=None):
    if post_id:
        if not isinstance(post_id, (int, long)):
            post_id=unb26(post_id)

        if comments:
            if isinstance(comments, (list, tuple)):
              db.perform("DELETE FROM posts.unread_comments "
                         "WHERE user_id=%s AND post_id=%s AND comment_id=ANY(%s);",
                         [env.user.id, post_id, map(lambda c: int(c), comments)])
            else:
              db.perform("DELETE FROM posts.unread_comments "
                         "WHERE user_id=%s AND post_id=%s AND comment_id<=%s;",
                         [env.user.id, post_id, int(comments)])
        else:
            db.perform("DELETE FROM posts.unread_comments "
                       "WHERE user_id=%s AND post_id=%s;",
                       [env.user.id, post_id])
    else:
        db.perform("DELETE FROM posts.unread_comments "
                   "WHERE user_id=%s;", [env.user.id])

@check_auth
def delete_last():
    key = 'last:%s' % env.user.id
    items = cache_get(key)

    if not items:
        return None

    while True:
        try:
            item = items.pop()
            if not item:
                return
            try:
                post_id, comment_id = item.split('/')
                post = Post(post_id)
                comment = Comment(post_id, int(comment_id))
                break
            except ValueError:
                post = Post(item)
                comment = None
                break
        except (PostNotFound, CommentNotFound):
            continue
        except IndexError:
            return
        finally:
            pass

    cache_store(key, items)

    if comment:
        if env.user.id != post.author.id and env.user.id != comment.author.id:
            raise CommentAuthorError(post.id, comment.id)
        comment.delete()
        return comment
    else:
        if post.author.id != env.user.id:
            raise PostAuthorError(post.id)
        post.delete()
        return post

@check_auth
def subscribe(post_id):
    """
    Subscribe to post
    """
    post = show_post(post_id)
    env.user.subscribe(post)

    return post

@check_auth
def check_subscribe_to(post_id):
    """Check for user subscription to post
    """
    subscribed = env.user.check_post_subscribed(post_id)
    return subscribed

@check_auth
def unsubscribe(post_id):
    """
    Unsubscribe from post
    """
    post = show_post(post_id)
    env.user.unsubscribe(post)

    db.perform("DELETE FROM posts.unread_comments "
               "WHERE user_id=%s AND post_id=%s;",
               [env.user.id, unb26(post_id)])

    return post

@check_last_action
@check_auth
def recommend(post_id, comment_id, text=None):
    """
    Recommend post/comment
    """
    post = show_post(post_id)
    if post.archive:
        raise SubscribeError

    if text and post.author.check_blacklist(env.user):
        raise RecommendationError

    if text and isinstance(text, str):
        text = text.decode('utf-8', 'ignore')

    try:
        post.add_subscriber(env.user)
    except AlreadySubscribed:
        pass

    if post.private:
        raise RecommendationError

    if not comment_id and post.tags and u'norec' in post.tags:
        raise RecommendationError

    if text is not None and post.tags and u'readonly' in post.tags:
        raise PostReadonlyError


    if comment_id:
        comment = Comment(post, comment_id)
        if comment.author == env.user:
            raise RecommendationError
        post_author = comment.author
        post_text = comment.text
        tags = []
        title = ''
        link = ''
        files = comment.files

    elif post.author == env.user:
        raise RecommendationError

    else:
        post_author = post.author
        post_text = post.text
        tags = post.tags
        title = post.title
        link = post.link
        files = post.files

    ccnt = post.comments_count()

    res = db.fetchone("SELECT post_id FROM posts.recommendations "
                     "WHERE post_id=%s "
                     "AND comment_id=COALESCE(%s, 0) "
                     "AND user_id=%s;",
                     [unb26(post_id), comment_id, env.user.id])
    if res:
        raise RecommendationExists

    try:
        env.user.subscribe(post)
    except AlreadySubscribed:
        pass

    rcid = None
    if text:
        text = text[:512]

        c = Comment.from_data(post, None, author=env.user, text=text,
                              to_comment_id=comment_id)
        rcid = c.save()

    try:
        db.perform("INSERT INTO posts.recommendations "
                   "(post_id, comment_id, user_id, text, rcid) "
                   "VALUES (%s, COALESCE(%s, 0), %s, %s, %s);",
                   [unb26(post_id), comment_id, env.user.id, text, rcid])
    except IntegrityError:
        raise RecommendationExists

    if post.author.get_profile('private'):
        wq = ("INTERSECT SELECT to_user_id AS user_id FROM users.whitelist "
              "WHERE user_id=%s") % post.author.id
    else:
        wq = ''

    if post.tags:
        tq = ("EXCEPT "
              "SELECT user_id FROM posts.tags_blacklist "
              "WHERE tag = ANY(%(tags)s) "
              "AND (to_user_id IS NULL "
                   "OR to_user_id=%(author_id)s)")
    else:
        tq = ''


    res = db.fetchall("(((SELECT user_id FROM subs.recommendations "
                      "WHERE to_user_id=%%(user_id)s "
                      "UNION "
                      "SELECT user_id FROM subs.posts "
                      "WHERE post_id=%%(post_id)s and user_id!=%%(user_id)s) "
                      "EXCEPT "
                      "SELECT user_id FROM posts.recommendations_recv "
                      "WHERE post_id=%%(post_id)s "
                      "AND comment_id=COALESCE(%%(comment_id)s, 0) "
                      "EXCEPT "
                      "SELECT user_id FROM users.blacklist WHERE "
                      "to_user_id=%%(author_id)s "
                      "EXCEPT SELECT %s "
                      ") "
                      "%s ) %s;" % (post_author.id, tq, wq),
                      {'user_id': env.user.id,
                       'post_id': unb26(post_id),
                       'comment_id': comment_id,
                       'author_id': post.author.id,
                       'tags': post.tags})
    subscribers = [r[0] for r in res]

    publish('rec', {
        'to': post_author.id,
        'a': 'ok',
        'post_id': post_id,
        'comment_id': comment_id,
        'author': env.user.login,
        'author_id': env.user.id,
        'text': text,
        'rcid': rcid,
        'files': files
    })

    publish('msg', {
        'to': subscribers,
        'a': 'rec',
        'author': env.user.login,
        'author_id': env.user.id,
        'text': text,
        'post_id': post_id,
        'comment_id': comment_id,
        'post_author': post_author.login,
        'post_author_id': post_author.id,
        'post_text': post_text,
        'title': title,
        'link': link,
        'files': files,
        'tags': tags,
        'rcid': rcid,
        'comments': ccnt
    })

    try:
        db.batch("INSERT INTO posts.recommendations_recv "
                 "(post_id, comment_id, user_id) VALUES "
                 "(%s, COALESCE(%s, 0), %s);",
                 [(unb26(post_id), comment_id, u) for u in subscribers])
    except IntegrityError:
        pass

    try:
        #if comment_id:
        #    db.batch("INSERT INTO posts.unread_comments "
        #             "(user_id, post_id, comment_id, type) VALUES (%s, %s, %s, %s)",
        #             [(u, unb26(post_id), comment_id, post.type) for u in subscribers])
        #else:
            db.batch("INSERT INTO posts.unread_posts "
                     "(user_id, post_id, type) VALUES (%s, %s, %s)",
                     [(u, unb26(post_id), post.type) for u in subscribers])
    except IntegrityError:
        pass

    return rcid

@check_auth
def unrecommend(post_id, comment_id):
    """
    Unrecommend post/comment
    """
    post = show_post(post_id)
    if comment_id:
        comment = Comment(post, comment_id)

    res = db.fetchone("DELETE FROM posts.recommendations "
                     "WHERE post_id=%s AND comment_id=COALESCE(%s, 0) "
                     "AND user_id=%s "
                     "RETURNING post_id, rcid;",
                     [unb26(post_id), comment_id, env.user.id])
    if not res:
        raise RecommendationNotFound

    if res['rcid']:
        c = Comment(post, res['rcid'])
        c.delete()

@check_auth
def bookmarks(limit=10, offset=0, asc=False, before=None):
    """
    List user's bookmarks
    """
    if before and isinstance(before, (int, long)):
        offset = before - 157321
        offset_cond = " OFFSET %d" % offset
    elif offset:
        offset_cond = " OFFSET %d" % int(offset)
    else:
        offset = 0
        offset_cond = ""

    order = 'ASC' if asc else 'DESC'

    res = db.fetchall(
        "SELECT "
        "b.user_id, b.post_id AS id, b.comment_id, b.btext, "
        "true AS is_bookmark, "
        "CASE WHEN b.comment_id>0 THEN c.author ELSE p.author END "
           "AS author, "
        "CASE WHEN b.comment_id>0 THEN uc.login ELSE up.login END "
           "AS login, "
        "CASE WHEN b.comment_id>0 THEN ic.name ELSE ip.name END "
           "AS name, "
        "CASE WHEN b.comment_id>0 THEN ic.avatar ELSE ip.avatar END "
           "AS avatar, "
        "p.private, "
        "CASE WHEN b.comment_id>0 THEN 'post' ELSE p.type END "
           "AS type, "
        "CASE WHEN b.comment_id>0 THEN '' ELSE p.title END "
           "AS title, "
        "CASE WHEN b.comment_id>0 THEN '' ELSE p.link END "
           "AS link, "
        "CASE WHEN b.comment_id>0 THEN c.text ELSE p.text END "
           "AS text, "
        "p.archive, p.files, "
        "sp.post_id AS subscribed, "
        "rp.post_id AS recommended, "
        "true as bookmarked, "
        "p.tags, "
        "b.created at time zone %%(tz)s AS created, "
        "false AS edited,"
        "false AS editable, "
        "array_agg(distinct rcu.login) AS rcpt_logins "
        "FROM posts.bookmarks b "
        "LEFT JOIN posts.posts p ON b.post_id=p.id "
        "LEFT JOIN users.logins up ON p.author=up.id "
        "LEFT JOIN users.info ip ON p.author=ip.id "
        "LEFT OUTER JOIN posts.comments c "
           "ON b.post_id=c.post_id AND b.comment_id=c.comment_id "
        "LEFT OUTER JOIN users.logins uc ON c.author=uc.id "
        "LEFT OUTER JOIN users.info ic ON uc.id=ic.id "
        "LEFT OUTER JOIN subs.posts sp ON sp.post_id=p.id "
            "AND sp.user_id=%%(user_id)s "
        "LEFT OUTER JOIN posts.recommendations rp "
           "ON %%(user_id)s=rp.user_id AND "
           "b.post_id=rp.post_id  AND "
           "COALESCE(b.comment_id, 0)=rp.comment_id "
        "LEFT OUTER JOIN posts.recipients rcp ON rcp.post_id=b.post_id "
        "LEFT OUTER JOIN users.logins rcu ON rcu.id=rcp.user_id "
        "WHERE b.user_id=%%(user_id)s "
        "GROUP BY b.user_id, b.post_id, b.comment_id, "
            "c.author, p.author, uc.login, up.login, "
            "ic.name, ip.name, ic.avatar, ip.avatar, "
            "p.private, c.text, p.text, sp.post_id, rp.post_id, "
            "p.type, p.title, p.link, "
            "p.tags, b.created, p.edited, p.archive, p.files "
        "ORDER BY b.created %s "
        "%s LIMIT %%(limit)s;"% (order, offset_cond),
        {'user_id': env.user.id, 'tz': env.user.get_profile('tz'),
         'limit': limit, 'edit_expire': settings.edit_expire})

    plist = []
    for i, r in enumerate(res):
        r = dict(r)
        r['uid'] = 157321 + offset + i + 1
        plist.append(r)
    return _plist(plist)

@check_auth
def bookmark(post_id, comment_id, text):
    """
    Add post/comment to bookmarks
    """
    item = show_post(post_id)
    if comment_id:
        comment = Comment(item, comment_id)
    else:
        comment_id = 0

    try:
        db.perform("INSERT INTO posts.bookmarks "
                   "(post_id, comment_id, user_id, btext) "
                   "VALUES (%s, %s, %s, %s);",
                   [unb26(post_id), comment_id, env.user.id, text])
    except IntegrityError:
        raise BookmarkExists

@check_auth
def unbookmark(post_id, comment_id):
    """
    Remove post/comment from bookmarks
    """
    item = show_post(post_id)
    if comment_id:
        comment = Comment(item, comment_id)
    else:
        comment_id = 0

    db.perform("DELETE FROM posts.bookmarks WHERE post_id=%s AND comment_id=%s "
               "AND user_id=%s;",
               [unb26(post_id), comment_id, env.user.id])

@check_auth
def add_recipients(post_id, to):
    """
    Add a recipient to the private post
    """
    post = Post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    to_users = []
    subscribers = []
    new_users = []
    for login in to:
        u = User('login', login)
        if u.check_blacklist(env.user):
            raise SubscribeError(login)
        to_users.append(u)

    for u in to_users:
        try:
            db.perform("INSERT INTO posts.recipients (post_id, user_id) "
                       "VALUES (%s, %s);", [unb26(post_id), u.id])
            subscribers.append(u.id)
            new_users.append(u.login)
        except IntegrityError:
            pass

    res = db.fetchall("SELECT u.login FROM posts.recipients r "
                      "JOIN users.logins u ON u.id=r.user_id "
                      "WHERE post_id=%s;",
                      [unb26(post_id)])
    to_users = [ u['login'] for u in res ]

    if subscribers:
        publish('msg', {
            'to': subscribers,
            'a': 'post',
            'id': post_id,
            'author': post.author.login,
            'author_id': post.author.id,
            'tags': post.tags,
            'private': post.private,
            'text': post.text,
            'to_users': to_users
        })
    return new_users

@check_auth
def del_recipients(post_id, to):
    """
    Delete recipient from the private post
    """
    post = Post(post_id)

    if env.user != post.author:
        raise PostAuthorError

    to_users = []
    for login in to:
        user = User('login', login)
        if user.check_blacklist(env.user):
            raise SubscribeError(login)
        to_users.append(user)

    db.fetchall("DELETE FROM posts.recipients WHERE "
                "post_id=%s AND user_id=ANY(%s) "
                "RETURNING user_id;",
                [unb26(post_id), [u.id for u in to_users]])

def _plist(res):
    if not res:
        return []

    unread = {}

    if env.user and env.user.id:
        ids = [ r['id'] for r in res ]
        for r in db.fetchall("SELECT post_id, count(post_id) AS cnt "
                             "FROM posts.unread_comments "
                             "WHERE user_id=%s AND post_id=ANY(%s)"
                             "GROUP BY post_id ",
                             [env.user.id, ids]):
            unread[r['post_id']] = r['cnt']

        clear_unread_posts(ids[0:settings.page_limit])

    plist  = []
    for r in res:
        item = {
            'bookmarked': bool(r['bookmarked']),
            'recommended': bool(r['recommended']),
            'editable': r['editable'],
        }

        if 'uid' in r:
            #print r['uid']
            item['uid'] = r['uid']

        item['subscribed'] = bool('subscribed' in r and r['subscribed'])

        author = User.from_data(r['author'], r['login'],
                            info={'name': r['name'], 'avatar': r['avatar']})
        tags = r['tags'] if 'tags' in r and r['tags'] else []
        pinned = r['pinned'] if 'pinned' in r else False

        post = Post.from_data(b26(r['id']), author=author, private=r['private'],
                              tags=tags, title=r['title'], text=r['text'],
                              link=r['link'], created=r['created'],
                              type=r['type'], archive=r['archive'],
                              files=r['files'], pinned=pinned)
        item['post'] = post

        if 'is_rec' in r and r['is_rec']:
            item['rec'] = {
                'author': User.from_data(r['r_author'], r['r_login'],
                          info={'name': r['r_name'], 'avatar': r['r_avatar']}),
                'text': r['r_text'],
                'comment_id': r['r_comment_id']
            }

        if post.comments_count():
            item['editable'] = False

        if 'comment_id' in r and r['comment_id']:
            item['comment_id'] = r['comment_id']

        if 'btext' in r and r['btext']:
            item['btext'] = r['btext']

        try:
            item['unread'] = unread[r['id']]
        except KeyError:
            pass

        plist.append(item)
    return plist


def post_unread(post_id, user_id):
    """Returns 'True' or 'False' for 'read' or 'unread' respectively, 
    if user is logged in, otherwise it returns 'None'.
    """
    res = db.fetchone("SELECT 1 FROM posts.unread_posts "
                 "WHERE post_id=%s AND user_id=%s;",
                 [unb26(post_id), user_id])
    return True if res else False

