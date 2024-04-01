from point.core.user import User, UserNotFound, UserExists, \
                            NotAuthorized, AlreadyAuthorized, \
                            AddressNotFound
from point.app import users
from point.util.env import env
from point.util.www import check_referer
from point.util.redispool import RedisPool
from point.util.crypt import aes_decrypt
from geweb.http import Response
from geweb.session import Session
from geweb.exceptions import NotFound, Forbidden
from geweb.template import render
from geweb.util import csrf
from point.util import parse_date, validate_nickname
from point.util import cache_get, cache_store
from point.util import timestamp
from point.util.www import catch_errors, get_referer
from user import WebUser
from point.util.imgproc import make_avatar
from random import randint
import json
import urllib2
from datetime import datetime, timedelta
from geweb import log

try:
    import re2 as re
except ImportError:
    import re

import settings

ULOGIN_FIELDS = ['email', 'nickname', 'bdate', 'sex', 'city', 'country', 'photo_big']

#@csrf
def login():
    if env.user.id:
        return Response().redirect('%s://%s.%s/' % \
                                   (env.request.protocol,
                                    env.user.login, settings.domain))

    referer = get_referer()

    if env.request.method == 'GET':
        return render('/auth/login.html', referer=referer, fields=ULOGIN_FIELDS)

    try:
        login = env.request.args('login')
        password = env.request.args('password')
        if not login or not password:
            raise NotAuthorized
        env.user.authenticate(login, password)
        if env.request.is_xhr:
            return Response(json.dumps({'ok': True}),
                            mimetype='application/json')
        else:
            return Response(redirect=referer)
    except (KeyError, NotAuthorized):
        if env.request.is_xhr:
            return Response(json.dumps({'error': 'credentials'}),
                            mimetype='application/json')
        else:
            return render('/auth/login.html', errors=['credentials'],
                                         referer=referer, fields=ULOGIN_FIELDS)

    return Response(redirect=referer)

def login_key(key):
    if env.request.method != 'GET':
        raise Forbidden

    if env.user.id:
        env.user.logout()

    redis = RedisPool(settings.storage_socket)
    try:
        user_id = int(redis.get('login:%s' % key))
    except (TypeError, ValueError):
        raise NotFound
    redis.delete('login:%s' % key)

    env.user = WebUser(user_id)
    env.user.authenticate()

    return Response(redirect='%s://%s/' % \
                    (env.request.protocol, settings.domain))

@csrf
@check_referer
def logout():
    env.user.logout()
    return Response(redirect=env.request.referer)

def remember():
    if env.request.method != 'POST':
        if env.request.args('sent'):
            return render('/auth/remember-sent.html')
        if env.request.args('fail'):
            return render('/auth/remember-fail.html')
        return render('/auth/remember.html')

    errors = []

    if env.user.id:
        user = env.user
    else:
        login = env.request.args('login')
        if not login:
            errors.append('login')
        else:
            try:
                user = User('login', login)
            except UserNotFound:
                errors.append('login')

    if not errors:
        try:
            text = env.request.args('recaptcha_response_field')
            challenge = env.request.args('recaptcha_challenge_field')

            resp = captcha.submit(challenge, text,
                                  settings.recaptcha_private_key,
                                  env.request.remote_host)

            if resp.is_valid:
                users.request_password(user)
                return Response(redirect='%s://%s/remember?sent=1' % \
                        (env.request.protocol, settings.domain))

            errors.append('captcha')

        except urllib2.URLError:
            errors.append('recaptcha-fail')
        except AddressNotFound:
            return Response(redirect='%s://%s/remember?fail=1' % \
                        (env.request.protocol, settings.domain))

    return render('/auth/remember.html', errors=errors)

def reset_password(code):
    if env.request.method != 'POST':
        if env.request.args('changed'):
            return render('/auth/new-password-changed.html')
        if env.request.args('fail'):
            return render('/auth/new-password-fail.html')
        return render('/auth/new-password.html')

    errors = []

    password = env.request.args('password')
    confirm = env.request.args('confirm')

    if not password:
        errors.append('password')
    if password != confirm:
        errors.append('confirm')

    if errors:
        return render('/auth/new-password.html', errors=errors)

    if env.user.id:
        env.user.logout()

    try:
        user = users.reset_password(code, password)
    except UserNotFound:
        return Response(redirect='%s://%s/remember/%s?fail=1' % \
                        (env.request.protocol, settings.domain, code))
    WebUser(user.id).authenticate()
    return Response(redirect='%s://%s/remember/%s?changed=1' % \
                        (env.request.protocol, settings.domain, code))

def _gender(value):
    if value == 'm':
        return True
    if value == 'f':
        return False
    return None

@catch_errors
def register():
    #raise Forbidden
    if env.user.id:
        raise AlreadyAuthorized

    sess = Session()
    info = sess['reg_info'] or {}

    if env.request.method == 'GET':
        try:
            del info['network']
            del info['uid']
        except (KeyError, TypeError):
            pass
        sess['reg_info'] = info
        sess['reg_start'] = timestamp(datetime.now())
        sess.save()

        try:
            info['birthdate'] = parse_date(info['birthdate']) \
                                or datetime.now() - timedelta(days=365*16+4)
        except (KeyError, TypeError):
            info['birthdate'] = None

        return render('/auth/register.html', fields=ULOGIN_FIELDS, info=info)

    if cache_get('reg-ok:%s' % env.request.remote_host):
        raise Forbidden

    # hi1 = env.request.args('hi1')
    # try:
    #     hi2 = int(env.request.args('hi2', 0))
    # except ValueError:
    #     hi2 = 0

    #try:
    #    h = hi2 / (timestamp(datetime.now()) - int(sess['reg_start']))
    #except:
    #    raise Forbidden
    #finally:
    #    pass
    # if hi2 < 5:
    #     raise Forbidden

    # try:
    #     network = info['network'] if 'network' in info else None
    #     uid = info['uid'] if 'uid' in info else None
    # except TypeError:
    #     network = None
    #     uid = None

    errors = []

    inviter = None
    invite = env.request.args('invite', '').strip()

    if not invite:
        errors.append('invalid-invite')
    else:
        try:
            data = aes_decrypt(invite)

            now = timestamp(datetime.now())
            if data['exp'] < now:
                errors.append('invalid-invite')
            else:
                inviter = User(data['uid'])
                allow_invite = inviter.get_profile('allow_invite')
                if not allow_invite:
                    errors.append('invalid-invite')
        except Exception as e:
            log.error(e.__str__)
            errors.append('invalid-invite')

    for p in ['login', 'name', 'email', 'birthdate', 'location', 'about', 'homepage']:
        info[p] = env.request.args(p, '').decode('utf-8')

    info['gender'] = _gender(env.request.args('gender'))

    login = env.request.args('login', '').strip()

    # if hi1 != login:
    #     raise Forbidden

    if login and validate_nickname(login):
        try:
            u = User('login', login)
            if u.id:
                errors.append('login-in-use')
        except UserNotFound:
            pass
    elif login:
        errors.append('login-invalid')
    else:
        errors.append('login-empty')

    password = env.request.args('password')
    confirm = env.request.args('confirm')

    if not password:
        errors.append('password')
    elif password != confirm:
        errors.append('confirm')

    info['birthdate'] = parse_date(info['birthdate']) \
                            or datetime.now() - timedelta(days=365*21+4)

    if not errors:
        try:
            users.register(login)

        except UserExists:
            errors.append('login-in-use')

    if errors:
        tmpl = '/auth/register.html'

        sess['reg_start'] = timestamp(datetime.now())
        sess.save()
        return render(tmpl, fields=ULOGIN_FIELDS, info=info, errors=errors)

    env.user.set_info('inviter', inviter.id)

    for p in ['name', 'email', 'birthdate', 'gender', 'location', 'about', 'homepage']:
        env.user.set_info(p, info[p])

    if password:
        env.user.set_password(password)

    if env.request.args('avatar'):
        ext = env.request.args('avatar', '').split('.').pop().lower()
        if ext not in ['jpg', 'gif', 'png']:
            errors.append('filetype')
        else:
            filename = ('%s.%s' % (env.user.login, ext)).lower()

            make_avatar(env.request.files('avatar'), filename)

            env.user.set_info('avatar',
                        '%s?r=%d' % (filename, randint(1000, 9999)))

    elif 'avatar' in info and info['avatar']:
        filename = ('%s.%s' % (env.user.login, 'jpg')).lower()

        make_avatar(info['avatar'], filename)

        env.user.set_info('avatar', '%s?r=%d' % (filename, randint(1000, 9999)))

    env.user.save()
    cache_store('reg-ok:%s' % env.request.remote_host, 1, 900)

    env.user.authenticate()

    return Response(redirect=get_referer())
