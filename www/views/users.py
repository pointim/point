from point.app import users, tags
from point.util.env import env
from point.util.www import check_referer
from geweb.http import Response
from geweb.exceptions import Forbidden, NotFound
from geweb.template import render
from point.core.user import User, SubscribeError, check_auth, \
                            AlreadySubscribed, AlreadyRequested, \
                            UserNotFound
from geweb.util import csrf
from point.util import timestamp
import json

import settings

def info(login):
    try:
        user = User('login', login)
    except UserNotFound:
        raise NotFound

    try:
        data = users.info(user)
    except SubscribeError:
        raise Forbidden
    data['login'] = login
    try:
        data['created'] = timestamp(data['created'])
    except (KeyError, AttributeError):
        pass
    try:
        data['birthdate'] = timestamp(data['birthdate'])
    except (KeyError, AttributeError):
        pass
    if env.user.id:
        data['subscribed'] = user.check_subscriber(env.user)
        data['rec_sub'] = user.check_rec_subscriber(env.user)
        if not data['subscribed']:
            data['bl'] = env.user.check_blacklist(user)
            if not data['bl']:
                data['wl'] = env.user.check_blacklist(user)
    return Response(json.dumps(data), mimetype='application/json')

def avatar(login, size):
    """To avoid code duplication, parameter ``login`` can be interpreted 
    as a number if it is user id, and as a string if it is user login"""
    size = int(size) if size else 40
    try:
        if login and login.isdigit():
            user = User(int(login))
        else:
            user = User('login', login)
        avatar = user.get_info('avatar')
    except UserNotFound:
        avatar = None

    if avatar:
        path = '%s%s/%s/%s' % \
               (env.request.protocol, settings.avatars_root, size, avatar)
    else:
        path = '%s%s/av%s.png' % \
               (env.request.protocol, settings.avatars_root, size)

    return Response(redirect=path)

def usercss(login):
    try:
        u = User('login', login)
    except UserNotFound:
        raise NotFound
    css = u.get_profile('www.usercss')
    return Response(css, mimetype='text/css')

@csrf
@check_auth
@check_referer
def subscribe():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.subscribe(env.owner)
    except SubscribeError:
        raise Forbidden
    except (AlreadySubscribed, AlreadyRequested):
        res = False

    # TODO: notify user if subscription request is sent

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def unsubscribe():
    if not env.owner or not env.owner.id:
        raise NotFound

    users.unsubscribe(env.owner)

    if env.request.is_xhr:
        return Response(json.dumps({'ok': True}), mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def subscribe_rec():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.subscribe_rec(env.owner)
    except SubscribeError:
        raise Forbidden
    except (AlreadySubscribed, AlreadyRequested):
        res = False

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def unsubscribe_rec():
    if not env.owner or not env.owner.id:
        raise NotFound

    users.unsubscribe_rec(env.owner)

    if env.request.is_xhr:
        return Response(json.dumps({'ok': True}), mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def add_to_whitelist():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.add_to_whitelist(env.owner)
    except SubscribeError:
        raise Forbidden
    except AlreadySubscribed:
        raise Forbidden

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def del_from_whitelist():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.del_from_whitelist(env.owner)
    except SubscribeError:
        raise Forbidden

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def add_to_blacklist():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.add_to_blacklist(env.owner)
    except SubscribeError:
        raise Forbidden

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

@csrf
@check_auth
@check_referer
def del_from_blacklist():
    if not env.owner or not env.owner.id:
        raise NotFound

    try:
        res = users.del_from_blacklist(env.owner)
    except SubscribeError:
        raise Forbidden

    if env.request.is_xhr:
        return Response(json.dumps({'ok': bool(res)}),
                        mimetype='application/json')

    return Response(redirect=env.request.referer)

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

def subscriptions():
    if not env.owner:
        raise NotFound
    if not env.user.login and env.owner.get_profile('deny_anonymous'):
        raise Forbidden
    users = env.owner.subscriptions()
    return render('/subs.html', section='subscriptions', users=users)

def subscribers():
    if not env.owner:
        raise NotFound
    if not env.user.login and env.owner.get_profile('deny_anonymous'):
        raise Forbidden
    users = env.owner.subscribers()
    return render('/subs.html', section='subscribers', users=users)

