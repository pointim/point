from geweb import log
from point.util.env import env
from point.core.user import User, check_auth
from point.core.user import AlreadyAuthorized, UserExists, UserNotFound, \
                            SubscribeError, AddressNotFound
from point.util.redispool import publish
from point.app.posts import add_post
from point.util.redispool import RedisPool
from point.util.sessions import set_sessions_param
from hashlib import sha256
from datetime import datetime
from random import randint

import settings

def register(login, **kwargs):
    """Register a new user
    """
    if env.user.is_authorized():
        raise AlreadyAuthorized(env.user.login)

    try:
        if User('login', login):
            raise UserExists(login)
    except UserNotFound:
        pass

    env.user = env.user.__class__.from_data(None, login, **kwargs)
    env.user.save()

    add_post('User @%s is registered' % login,
             author=User('login', 'welcome'), auto_subscribe=False)

#@check_auth
def info(user):
    """Get user info
    """
    if isinstance(user, (str, unicode)):
        user = User('login', user)

    if env.user.id != user.id and user.get_profile('private') \
            and not user.check_whitelist(env.user):
        raise SubscribeError

    return user.get_info()

@check_auth
def add_account(type, address):
    code = env.user.add_account(type, address)
    if not code:
        return False

    env.user.save()

    publish('confirm', {'type': type, 'address': address,
                        'user': env.user.login, 'code': code})

    return code

@check_auth
def confirm_account(code):
    return env.user.confirm_account(code)

@check_auth
def del_account(type, address):
    env.user.del_account(type, address)
    env.user.save()

@check_auth
def subscribe(login):
    """Subscribe to user
       returns True if subscribed, and False if subscription request is sent
    """
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        raise SubscribeError

    if user.add_subscription_request(env.user):
        publish('sub', {'to':user.id, 'a':'sub', 'from':env.user.login})
        log.info('sub %d %s' % (user.id, env.user.login))
        return True

    else:
        publish('sub', {'to':user.id, 'a':'req', 'from':env.user.login})
        log.info('sub request %d %s' % (user.id, env.user.login))
        return False

@check_auth
def check_subscribe_to_user(login):
    return env.user.check_subscribe_to_user(login)

@check_auth
def check_subscribe_to_user_rec(login):
    return env.user.check_subscribe_to_user_rec(login)

@check_auth
def unsubscribe(login):
    """Unsubscribe from user
    """
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        raise SubscribeError

    retval = env.user.unsubscribe(user)
    if not retval:
        return False

    # TODO: send to pubsub
    return True

@check_auth
def subscribe_rec(login):
    """Subscribe to user's recommendations
       returns True if subscribed, and False if subscription request is sent
    """
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        raise SubscribeError

    if not user.check_subscriber(env.user):
        return subscribe(user)

    user.add_rec_subscriber(env.user)
    return True

@check_auth
def unsubscribe_rec(login):
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if not user.check_subscriber(env.user):
        return False

    user.del_rec_subscriber(env.user)

@check_auth
def add_to_whitelist(login):
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        raise SubscribeError

    res = env.user.add_to_whitelist(user)

    if res:
        publish('sub', {'to':user.id, 'a':'wl', 'from':env.user.login})

    return res

@check_auth
def del_from_whitelist(login):
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        return

    return env.user.del_from_whitelist(user)

@check_auth
def add_to_blacklist(login):
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        raise SubscribeError

    res = env.user.add_to_blacklist(user)

    # TODO: send to pubsub
    return res

@check_auth
def del_from_blacklist(login):
    if isinstance(login, User):
        user = login
    else:
        user = User('login', login)

    if env.user.id == user.id:
        return

    return env.user.del_from_blacklist(user)

def request_password(user):
    if not user.id:
        raise UserNotFound

    address = user.get_active_account('xmpp')

    if not address:
        raise AddressNotFound

    code = sha256('%s%s' % (datetime.now(), randint(1000000, 9999999))).hexdigest()
    key = 'reset-password:%s' % code
    redis = RedisPool(settings.storage_socket)
    redis.set(key, user.id)
    redis.expire(key, 60 * 60 * 24)
    publish('remember', {'type': 'xmpp', 'address': address, 'code': code})

def reset_password(code, password):
    redis = RedisPool(settings.storage_socket)
    key = 'reset-password:%s' % code
    print key
    id = redis.get(key)
    if not id:
        raise UserNotFound
    try:
        user = User(int(id))
    except ValueError:
        raise UserNotFound
    user.set_password(password)
    user.save()
    redis.delete(key)
    return user

@check_auth
def rename(login):
    old = env.user.login
    env.user.rename(login)

    set_sessions_param(env.user, 'login', login)

    subs = [ u.id for u in env.user.subscribers() ]
    publish('sub', {'to': subs, 'a': 'rename', 'old': old, 'new': login})

