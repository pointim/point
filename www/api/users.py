from point.app import users, tags
from point.util.env import env
from point.util.www import check_referer
from geweb.http import Response
from geweb.exceptions import Forbidden, NotFound
from geweb.template import render
from point.core.user import User, SubscribeError, check_auth, \
                            AlreadySubscribed, AlreadyRequested, \
                            UserNotFound, NotAuthorized
from geweb.util import csrf
import json

from api import api, write_api


@api
def info(login):
    try:
        user = User('login', login)
    except UserNotFound:
        raise NotFound

    try:
        data = users.info(user)
    except SubscribeError:
        raise Forbidden
    data['id'] = user.id
    data['login'] = user.login
    try:
        data['created'] = data['created']
    except (KeyError, AttributeError):
        pass
    try:
        data['birthdate'] = data['birthdate']
    except (KeyError, AttributeError):
        pass
    if env.user.id:
        data['subscribed'] = user.check_subscriber(env.user)
        data['rec_sub'] = user.check_rec_subscriber(env.user)
        if not data['subscribed']:
            data['bl'] = env.user.check_blacklist(user)
            if not data['bl']:
                data['wl'] = env.user.check_blacklist(user)
    return data


@api
def user_info_byid(uid):
    """Return user info by given user id"""
    if uid and uid.isdigit():
        try:
            user = User(int(uid))
        except (UserNotFound, ValueError):
            raise NotFound
        else:
            data = info(user.login)
            return json.loads(data.body)
    raise NotFound


# get user info via settings.domain/api/me
@api
def my_info():
    login = env.user.login
    if not login:
        raise NotAuthorized
    return users.info(login)

@write_api
def subscribe(login):
    return users.subscribe(login)

@write_api
def unsubscribe(login):
    users.unsubscribe(login)

@write_api
def subscribe_rec(login):
    users.subscribe_rec(login)

@write_api
def unsubscribe_rec(login):
    users.unsubscribe_rec(login)

@write_api
def add_to_whitelist(login):
    users.add_to_whitelist(login)

@write_api
def del_from_whitelist(login):
    users.del_from_whitelist(login)

@write_api
def add_to_blacklist(login):
    users.add_to_blacklist(login)

@write_api
def del_from_blacklist(login):
    users.del_from_blacklist(login)

@csrf
@check_auth
@check_referer
def tag_subscribe():
    tag = env.request.args('tag', '').strip()
    if not tag:
        raise Forbidden
    try:
        tags.subscribe(tag, env.owner.login)
    except SubscribeError:
        raise Forbidden

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def tag_unsubscribe():
    tag = env.request.args('tag', '').strip()
    if not tag:
        raise Forbidden
    tags.unsubscribe(tag, env.owner.login)
    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def tag_add_to_blacklist():
    tag = env.request.args('tag', '').strip()
    if not tag:
        raise Forbidden
    try:
        tags.add_to_blacklist(tag, env.owner.login)
    except SubscribeError:
        raise Forbidden
    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def tag_del_from_blacklist():
    tag = env.request.args('tag', '').strip()
    if not tag:
        raise Forbidden
    tags.del_from_blacklist(tag, env.owner.login)
    return Response(redirect=env.request.referer)

@api
def subscriptions(login):
    env.owner = User("login", login)
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.subscriptions()

@api
def subscriptions_byid(uid):
    """Return user's subscriptions by given user id"""
    uid = int(uid)
    env.owner = User(int(uid))
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.subscriptions()

@api
def subscribers(login):
    env.owner = User("login", login)
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.subscribers()

@api
def subscribers_byid(uid):
    """Return user's subscribers by given user id"""
    uid = int(uid)
    env.owner = User(int(uid))
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.subscribers()

@api
def unread_counters():
    if not env.user or not env.user.id:
        raise NotAuthorized
    return {
        'posts': env.user.unread_posts_count('post'),
        'comments': env.user.unread_comments_count('post'),
        'private_posts': env.user.unread_posts_count('private'),
        'private_comments': env.user.unread_comments_count('private')
    }

@api
@check_auth
def blacklist():
    env.owner = env.user
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.blacklist()

@api
@check_auth
def whitelist():
    env.owner = env.user
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.whitelist()

@api
@check_auth
def blacklisters():
    env.owner = env.user
    if not env.owner or not env.owner.id:
        raise NotFound
    return env.owner.blacklisters()

