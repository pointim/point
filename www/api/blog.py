# -*- coding: UTF-8 -*-

from point.app import posts
from point.util import timestamp, parse_logins
from point.util.env import env
from point.util.www import check_referer
from geweb.http import Response
from geweb.exceptions import Forbidden
from point.core.post import Post, PostAuthorError, PostTextError, \
                            RecommendationNotFound, RecommendationError, \
                            RecommendationExists, BookmarkExists, \
                            PostUpdateError, PostDiffError, PostCommentedError,\
                            AlreadySubscribed, PostAlreadyPinnedError, \
                            PostNotPinnedError 
from point.core.user import User, SubscribeError, UserNotFound, check_auth

from api import api, write_api

try:
    import re2 as re
except ImportError:
    import re

import settings

def sanitize_plist(plist):
    for p in plist:
        if "author" in p: del p["author"]
        if "user_id" in p: del p["user_id"]
        keys = p.keys()
        for key in keys:
            if not p[key]: del p[key]
        if "subscribed" in p: p["subscribed"] = True
    return plist

@api
def blog(login=None):
    if login:
        env.owner = User("login", login)
    elif env.user.is_authorized():
        env.owner = env.user

    if not env.owner:
        raise UserNotFound

    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except (TypeError, ValueError):
            before = None

    try:
        plist = posts.recent_blog_posts(env.owner, settings.page_limit+1,
                                        before=before)
        if len(plist) > settings.page_limit:
            plist = plist[:settings.page_limit]
            has_next = True
        else:
            has_next = False
    except PostAuthorError:
        raise Forbidden

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
def blog_by_id(uid=None):
    """Obtain user blog contents by given user id
    parameters:
    uid - user id
    """
    if uid:
        env.owner = User(int(uid))
    elif env.user.is_authorized():
        env.owner = env.user

    if not env.owner:
        raise UserNotFound

    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    try:
        plist = posts.recent_blog_posts(env.owner, settings.page_limit+1,
                                        before=before)
        if len(plist) > settings.page_limit:
            plist = plist[:settings.page_limit]
            has_next = True
        else:
            has_next = False
    except PostAuthorError:
        raise Forbidden

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
@check_auth
def recent_all():
    env.owner = env.user

    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.recent_posts(limit=settings.page_limit+1, before=before)
    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }


@write_api
def post_pin(id):
    post = posts.show_post(id)
    try:
        if post.pinned:
            raise PostAlreadyPinnedError
    except PostAlreadyPinnedError:
        return {
            "code": "405",
            "message": "Post already pinned."
        }
    else:
        post.set_pinned()


@write_api
def post_unpin(id):
    post = posts.show_post(id)
    try:
        if not post.pinned:
            raise PostNotPinnedError
    except PostNotPinnedError:
        return {
            "code": "405",
            "message": "Post not pinned."
        }
    else:
        post.set_pinned(False)


@api
@check_auth
def recent_posts(page=1):
    env.owner = env.user

    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.recent_posts(type='post',
                               limit=settings.page_limit+1, before=before)
    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
@check_auth
def all_posts(page=1):
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.select_posts(private=False, author_private=False,
                               blacklist=True,
                               limit=settings.page_limit+1, offset=offset,
                               before=before)
    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
@check_auth
def messages_incoming():
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.private_incoming(limit=settings.page_limit+1, before=before)

    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
@check_auth
def messages_outgoing(page=1):
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.private_outgoing(limit=settings.page_limit+1, before=before)

    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
@check_auth
def comments():
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.recent_commented_posts(limit=settings.page_limit+1,
                                         before=before)
    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

def tags(login=None):
    _tags = env.request.args("tag")
    if _tags:
        return tag_posts(login)

    return taglist(login)

@api
def taglist(login):
    """Получение спика тегов пользователя по его user id или логину. Параметр 
    login, переданный в URL может быть как числом, и тогда интерпретируется 
    как id пользователя, так и строкой -- в этом случае он интерпретируется 
    как login пользователя
    """
    if login and login.isdigit():
        env.owner = User(int(login))
    else:
        env.owner = User("login", login)
    if not env.owner or not env.owner.id:
        raise UserNotFound

    return map(lambda t: {"tag": t["tag"], "count": t["cnt"]},
               env.owner.tags(sort_by_name=True))

@api
def tag_posts(login=None):
    """Выборка постов по тегам пользователя. Пользователь может быть 
    идентифицирован по его user id или логину. 
    Параметр login, переданный в URL может быть числом, и тогда 
    интерпретируется как id пользователя, или строкой -- в этом случае он 
    интерпретируется как login пользователя
    """
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    if login:
        if login and login.isdigit():
            author = User(int(login))
        else:            
            author = User("login", login)
    else:
        author = None

    if author and author == env.user:
        private = None
    else:
        private = False

    tags = env.request.args("tag")
    if not isinstance(tags, (list, tuple)):
        tags = [tags]
    tags = [t.decode('utf-8').replace(u"\xa0", " ") for t in tags]

    plist = posts.select_posts(author=author, private=private, tags=tags,
                               limit=settings.page_limit+1, before=before)
    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@api
def show_post(id):
    post = posts.show_post(id)
    post_dict = posts.show_post(id).todict()
    post_dict['unread'] = posts.post_unread(id, env.user.id) if env.user.id \
        else None
    return {
        "post": post_dict,
        "comments": post.comments(cuser=env.user),
    }

@write_api
def edit_post(id):
    post = posts.show_post(id)

    text = env.request.args('text', '').strip()
    #private = bool(env.request.args('private'))
    tags = env.request.args('tag', '') or env.request.args('tag[]', '')
    if not tags:
        tags = []
    elif not isinstance(tags, (list, tuple)):
        tags = [tags]

    def _t(tag):
        if isinstance(tag, str):
            tag = tag.decode('utf-8')
        return tag.replace(u"\xa0", " ")

    tags = map(_t, tags)

    posts.edit_post(post, text=text, tags=tags)

@write_api
def add_post():
    text = env.request.args('text', '').strip()

    tags = env.request.args('tag', '') or env.request.args('tag[]', '')
    if not tags:
        tags = []
    elif not isinstance(tags, (list, tuple)):
        tags = [tags]

    def _t(tag):
        if isinstance(tag, str):
            tag = tag.decode('utf-8')
        return tag.replace(u"\xa0", " ")

    tags = map(_t, tags)

    private = bool(env.request.args('private'))

    m = re.search(r'^\s*(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)', text)
    to = parse_logins(m.group('to')) if m else []

    id = posts.add_post(text, tags=tags, to=to, private=private)

    return {"id": id}

@write_api
def delete_post(id):
    try:
        posts.delete_post(id)

    except PostAuthorError:
        raise SubscribeError

@write_api
def add_comment(id):
    to_comment_id = env.request.args('comment_id')
    text = env.request.args('text', '').strip()

    comment_id = posts.add_comment(id, to_comment_id, text)

    return {"id": id, "comment_id": comment_id}

@write_api
def edit_comment(id, comment_id):
    text = env.request.args('text', '').strip()

    posts.edit_comment(id, comment_id, text, env.user)

    return {"id": id, "comment_id": comment_id}


@write_api
def delete_comment(id, comment_id):
    try:
        posts.delete_comment(id, comment_id)

    except PostAuthorError:
        raise SubscribeError

@write_api
def recommend_post(id):
    text = env.request.args('text')

    rcid = posts.recommend(id, None, text)

    if rcid:
        return {"comment_id": rcid}

@write_api
def unrecommend_post(id):
    posts.unrecommend(id, None)

@write_api
def recommend_comment(id, comment_id):
    text = env.request.args('text')

    rcid = posts.recommend(id, comment_id, text)

    if rcid:
        return {"comment_id": rcid}

@write_api
def unrecommend_comment(id, comment_id):
    posts.unrecommend(id, comment_id)

@write_api
def subscribe(id):
    posts.subscribe(id)

@write_api
def unsubscribe(id):
    posts.unsubscribe(id)

@api
@check_auth
def bookmarks():
    before = env.request.args("before")
    if before:
        try:
            before = long(before)
        except ValueError:
            before = None

    plist = posts.bookmarks(limit=settings.page_limit+1, before=before)

    if len(plist) > settings.page_limit:
        plist = plist[:settings.page_limit]
        has_next = True
    else:
        has_next = False

    return {
        "posts": plist,
        "has_next": has_next
    }

@write_api
def bookmark_post(id):
    text = env.request.args('text')
    posts.bookmark(id, None, text)

@write_api
def unbookmark_post(id):
    posts.unbookmark(id, None)

@write_api
def bookmark_comment(id, comment_id):
    text = env.request.args('text')
    posts.bookmark(id, comment_id, text)

@write_api
def unbookmark_comment(id, comment_id):
    posts.unbookmark(id, comment_id)

