""" XMPP bot views: users """

from geweb import log
from point.util.env import env
from point.core.user import User, ACCOUNT_TYPES
from point.core.user import UserError, UserNotFound, \
                            SubscribeError, AlreadySubscribed, \
                            AlreadyRequested, UserExists
from point.core.user import check_auth
from point.app import users, posts
from point.util.template import xmpp_template
from point.util.redispool import RedisPool
from point.util import validate_nickname
from random import randint
from hashlib import sha1
from datetime import datetime

try:
    import re2 as re
except ImportError:
    import re

import settings

def register(login, password=None):
    """Register a new user
    """

    return 'Registration is temporarily available on the web site only. Please follow: https://point.im.register .'

    if env.user.id:
        return xmpp_template('reg_already', login=env.user.login)

    if not validate_nickname(login):
        return xmpp_template('reg_invalid')

    sess = env.user.session()
    if not sess.data():
        return reg_steps(login, password)

def reg_steps(login=None, password=None):
    sess = env.user.session()
    if not sess.data():
        env.user.session(reg_steps, login=login, password=password, val='123')
        return 'Type 123'

    text = login
    if text.strip() == sess['val']:
        env.user.session_destroy()
        users.register(sess['login'], password=sess['password'],
                       accounts=[('xmpp', env.jid)])
        return xmpp_template('reg_ok', login=sess['login'])
    else:
        env.user.session_destroy()
        return {'body': 'fail'}

def info(login, show=False, offset=None, limit=None):
    """Get user info
    """
    try:
        user = User('login', login)
        data = users.info(user)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)
    except SubscribeError:
        return xmpp_template('user_denied', login=login)

    data['realname'] = data['name']
    del data['name']

    #_posts = None
    if show:
        if offset:
            offset = int(offset)
        if limit:
            limit = int(limit)
        else:
            limit = 10
        if env.user and env.user.id and env.user.id == user.id:
            private = None
        else:
            private = False
        #plist = posts.select_posts(author=user, private=private,
        #                           offset=offset, limit=limit)
        plist = posts.recent_blog_posts(author=user, offset=offset, limit=limit)
        plist.reverse()
        data['posts'] = plist

    else:
        data['posts_count'] = user.posts_count()

    return xmpp_template('user_info', login=login, **data)

fields = {
    'account': ['xmpp', 'icq', 'email'],
    'info': ['name', 'xmpp', 'icq', 'skype', 'about', 'birthdate',
             'location', 'homepage']
}

@check_auth
def whoami():
    return info(env.user.login)

@check_auth
def get_param(param):
    """Set profile/info parameter, add/remove account
    """
    if param in ('passwd', 'password'):
        return xmpp_template('password')

    if param in ACCOUNT_TYPES:
        active = env.user.get_active_account(param)
        accounts = env.user.get_accounts(param)
        unconfirmed = env.user.get_unconfirmed_accounts(param)
        return xmpp_template('accounts', type=param,
                             accounts=accounts, unconfirmed=unconfirmed,
                             active=active)

    try:
        if re.search(r'[^a-z0-9_\.]', param, re.I):
            raise KeyError
        return {'body': '%s = %s' % (param, env.user.get_profile(param))}
    except KeyError:
        return xmpp_template('profile_param_err', param=param)

@check_auth
def set_param(param, value):
    """Set profile/info parameter, add/remove account
    """
    value = value.strip()
    try:
        if re.search(r'[^a-z0-9_\.]', param, re.I):
            raise KeyError

        #if param in ('passwd', 'password'):
        #    env.user.set_password(value)

        elif param.startswith('info.') and param[5:] in fields['info']:
            env.user.set_info(param[5:], value)

        elif param in fields['account']:
            if value.startswith('-'):
                return del_account(param, value[1:].strip())
            if value.startswith('+'):
                value = value[1:]
            return add_account(param, value.strip())

        else:
            env.user.set_profile(param, value)

        env.user.save()

    except ValueError, e:
        v = e.message if e.message else value
        return xmpp_template('profile_value_err', value=v)
    except KeyError:
        return xmpp_template('profile_param_err', param=param)

    return xmpp_template('profile_ok')

def add_account(type, address):
    code = users.add_account(type, address)
    if not code:
        return xmpp_template('account_add_fail')
    return xmpp_template('account_add')

def confirm_account(code):
    if users.confirm_account(code):
        return xmpp_template('account_confirmed')
    return xmpp_template('account_confirm_fail')

def del_account(type, address):
    users.del_account(type, address)
    return xmpp_template('account_del')

@check_auth
def set_password():
    return passwd_steps()

def passwd_steps(value=None):
    sess = env.user.session()
    if not value or not sess.data():
        env.user.session(passwd_steps, step='passwd')
        return xmpp_template('passwd_enter_new')

    password = None

    if sess['step'] == 'passwd':
        #if env.user.check_password_set():
        #    env.user.session(passwd_steps, step='check', passwd=value)
        #    return xmpp_template('passwd_enter_current')
        password = value
        env.user.session_destroy()

    #if sess['step'] == 'check':
    #    if env.user.check_password_set() and not env.user.check_password(value):
    #        env.user.session_destroy()
    #        return xmpp_template('passwd_wrong')
    #    password = sess['passwd']

    env.user.session_destroy()
    if password:
        env.user.set_password(password)
        env.user.save()
        return xmpp_template('passwd_changed')
    else:
        return 'Unknown error'

@check_auth
def im_online():
    env.user.set_profile('im.off', False)
    env.user.save()
    return xmpp_template('im_online')

@check_auth
def im_offline():
    env.user.set_profile('im.off', True)
    env.user.save()
    return xmpp_template('im_offline')

@check_auth
def subscriptions():
    fn = lambda u: u.login.lower()
    subs = sorted(env.user.subscriptions(), key=fn)
    subscribers = sorted(env.user.subscribers(), key=fn)
    in_req = sorted(env.user.incoming_subscription_requests(), key=fn)
    out_req = sorted(env.user.outgoing_subscription_requests(), key=fn)
    tags = sorted(env.user.tag_subscriptions(), key=lambda t: t['login'].lower())
    return xmpp_template('subscriptions',
                         subscriptions=subs, subscribers=subscribers,
                         in_req=in_req, out_req=out_req,
                         tags=tags)

@check_auth
def subscribe(login, rec):
    """Subscribe to user
    """
    if rec:
        fn = users.subscribe_rec
    else:
        fn = users.subscribe
    try:
        if not fn(login):
            return xmpp_template('sub_req_sent', login=login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)
    except AlreadySubscribed:
        if rec:
            return xmpp_template('sub_rec_already', login=login)
        else:
            return xmpp_template('sub_already', login=login)
    except AlreadyRequested:
        return xmpp_template('sub_req_already', login=login)
    except SubscribeError:
        return xmpp_template('sub_denied', login=login)

    if rec:
        return xmpp_template('sub_rec_ok', login=login)
    else:
        return xmpp_template('sub_ok', login=login)

@check_auth
def unsubscribe(login, rec):
    """Unsubscribe from user
    """
    try:
        if login == env.user.login:
            raise SubscribeError
        if rec:
            if users.check_subscribe_to_user_rec(login):
                fn = users.unsubscribe_rec
            else:
                return xmpp_template('sub_rec_not', login=login)
        else:
            if users.check_subscribe_to_user(login):
                fn = users.unsubscribe
            else:
                return xmpp_template('sub_not', login=login) 

        if not fn(login):
            if rec:
                return xmpp_template('sub_unsub_rec_ok', login=login)
            else:
                return xmpp_template('sub_unsub_ok', login=login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)
    except SubscribeError:
        if rec:
            return xmpp_template('sub_unsub_rec_error', login=login)
        else:
            return xmpp_template('sub_unsub_error', login=login)

@check_auth
def whitelist():
    whitelist = sorted(env.user.whitelist(), key=lambda u: u.login.lower())
    return xmpp_template('whitelist', whitelist=whitelist)

@check_auth
def add_to_whitelist(logins):
    logins = re.split(r'[\s@,]+', logins.strip(' \t@'))

    added = []
    already = []
    denied = []
    not_found = []
    for login in logins:
        try:
            if users.add_to_whitelist(login):
                added.append(login)
            else:
                already.append(login)
        except SubscribeError:
            denied.append(login)
        except UserNotFound:
            not_found.append(login)
        except AlreadySubscribed:
            already.append(login)

    return xmpp_template('wl_updated', added=added, already=already,
                                       denied=denied, not_found=not_found)

@check_auth
def del_from_whitelist(logins):
    logins = re.split(r'[\s@,]+', logins.strip(' \t@'))

    deleted = []
    not_deleted = []
    not_found = []

    for login in logins:
        try:
            if users.del_from_whitelist(login):
                deleted.append(login)
            else:
                not_deleted.append(login)
        except UserNotFound:
            not_found.append(login)

    return xmpp_template('wl_updated', deleted=deleted,
                                       not_deleted=not_deleted,
                                       not_found=not_found)

@check_auth
def blacklist():
    blacklist = sorted(env.user.blacklist(), key=lambda u: u.login.lower())
    tags = sorted(env.user.tag_blacklist(), key=lambda t: t['login'].lower())
    return xmpp_template('blacklist', blacklist=blacklist, tags=tags)

@check_auth
def add_to_blacklist(logins):
    logins = re.split(r'[\s@,]+', logins.strip(' \t@'))

    added = []
    already = []
    not_found = []

    for login in logins:
        try:
            if users.add_to_blacklist(login):
                added.append(login)
            else:
                already.append(login)
        except SubscribeError:
            pass
        except UserNotFound:
            not_found.append(login)

    return xmpp_template('bl_updated', added=added, already=already,
                                       not_found=not_found)

@check_auth
def del_from_blacklist(logins):
    logins = re.split(r'[\s@,]+', logins.strip(' \t@'))

    deleted = []
    not_deleted = []
    not_found = []

    for login in logins:
        try:
            if users.del_from_blacklist(login):
                deleted.append(login)
            else:
                not_deleted.append(login)
        except UserNotFound:
            not_found.append(login)

    return xmpp_template('bl_updated', deleted=deleted,
                                       not_deleted=not_deleted,
                                       not_found=not_found)

@check_auth
def login():
    key = sha1('%s%s' % (randint(1000000, 9999999),
                         datetime.now().isoformat())).hexdigest()
    redis = RedisPool(settings.storage_socket)
    redis.set('login:%s'%key, env.user.id)
    redis.expire('login:%s'%key, settings.login_key_expire)

    return 'https://%s/login/%s' % (settings.domain, key)

@check_auth
def gen_invite():
    redis = RedisPool(settings.storage_socket)
    icnt = redis.decr('icnt:%s' % env.user.id)
    if icnt < 0:
        return 'Invitation limit exceeded'

    key = sha1('%s%s' % (randint(1000000, 9999999),
                         datetime.now().isoformat())).hexdigest()

    redis.set('invite:%s' % key, 1)
    redis.expire('invite:%s' % key, 3600*48)

    return key

def reg_invite(key):
    redis = RedisPool(settings.storage_socket)
    if not redis.get('invite:%s' % key):
        return 'Invalid key'

    return reg_invite_set_login(key)

def reg_invite_set_login(value):
    sess = env.user.session()
    if not sess.data():
        env.user.session(reg_invite_set_login, key=value)
        return 'Please enter your nickname'

    if not sess['key']:
        env.user.session_destroy()
        return 'Fail'


    env.user.session_destroy()

    if value.startswith('@'):
        value = value[1:]
    if not validate_nickname(value):
        return xmpp_template('reg_invalid')

    try:
        users.register(login=value, accounts=[('xmpp', env.jid)])
        redis = RedisPool(settings.storage_socket)
        redis.delete('invite:%s' % sess['key'])
        return xmpp_template('reg_ok', login=value)
    except UserExists:
        return 'User @%s already exists.' % value

    except UserError, e:
        log.error('%s: %s' % (e.__class__.__name__, e.message))
        return e.message

def alias_list():
    aliases = env.user.alias_list()
    return xmpp_template('alias_list', aliases=aliases)

def get_alias(alias):
    aliases = env.user.get_alias(alias)
    return xmpp_template('alias_list', aliases=aliases)

@check_auth
def set_alias(alias, command):
    env.user.set_alias(alias, command)
    return xmpp_template('alias_set', alias=alias, command=command)

@check_auth
def unalias(alias):
    if env.user.delete_alias(alias):
        return xmpp_template('alias_del', alias=alias)
    else:
        return xmpp_template('alias_del_fail', alias=alias)

