from point.core.user import UserExists, UserLoginError, RenameError
from point.core.user import check_auth
from point.app import users
from point.util.env import env
from geweb.http import Response
from geweb.template import render
from geweb.exceptions import Forbidden
from point.util import parse_email, parse_date, tzlist, check_tz
from point.util.imgproc import make_avatar, remove_avatar
from point.util.www import redirect_anonymous
from point.util.sessions import add_session
from geweb.session import Session
from random import randint
import urllib2
import json

import settings

def _gender(value):
    if value == 'm':
        return True
    if value == 'f':
        return False
    return None

def _check_css(value):
    if len(value) > 4096:
        return False
    return True

_info_form = {
    #'avatar': {'check': lambda f: re.match(r'\.(jpe?g|png|gif)$', f)},
    'name': {'check': lambda n: len(n) <= 128},
    'birthdate': {'type': parse_date, 'check': lambda d: d!=0},
    'gender': {'type': _gender},
    'location': {'check': lambda l: len(l) <= 128},
    'about': {'check': lambda a: len(a) <= 1024},
    'homepage': {'check': lambda h: len(h) <= 255},
    'email': {'check': lambda h: len(h) <= 255},
    'xmpp': {'check': lambda h: len(h) <= 255},
    'skype': {'check': lambda h: len(h) <= 255},
    'icq': {'check': lambda h: len(h) <= 255},
}

_profile_form = {
    'lang': {'check': lambda l: len(l) == 2},
    #'tz': {'type': int, 'check': lambda t: -43200 <= t <= 43200},
    'tz': {'type': str, 'check': check_tz},
    'private': {'type': bool},
    'deny_anonymous': {'type': bool},

    'im.off': {'type': bool},
    'im.xhtml': {'type': bool},
    'im.highlight': {'type': bool},
    'im.user_resource': {'type': bool},
    'im.post_resource': {'type': bool},
    'im.cut': {'type': int, 'check': lambda c: c <= 65536},
    'im.auto_switch': {'type': bool},

    'www.blogcss': {'check': _check_css},
    'www.usercss': {'check': _check_css},
    'www.ignorecss': {'type': bool},
    'www.tree': {'type': bool},

    #'domain', 'check': lambda d: len(d) <= 255},
}

@redirect_anonymous
@check_auth
def profile():
    errors = []

    if env.request.method == 'POST':
        if env.user.check_password_set():
            try:
                if not env.user.check_password(env.request.args('password', '')):
                    errors.append('password')
            except KeyError:
                errors.append('password')

        if env.request.args('remove-avatar'):
            old = env.user.get_info('avatar')
            if old:
                old = old.rsplit('?')[0]
                remove_avatar(old)
                env.user.set_info('avatar', None)
        else:
            if env.request.args('avatar'):
                if not errors:
                    avatar = env.request.args('avatar', '')
                    if isinstance(avatar, (list, tuple)):
                        avatar = avatar[0]
                    ext = avatar.split('.').pop().lower()
                    if ext not in ['jpeg', 'jpg', 'gif', 'png']:
                        errors.append('filetype')
                    else:
                        filename = ('%s.%s' % (env.user.login, ext)).lower()

                        old = env.user.get_info('avatar')
                        if old:
                            old = old.rsplit('?')[0]

                        avatar_file = env.request.files('avatar')
                        if isinstance(avatar_file, (list, tuple)):
                            avatar_file = avatar_file[0]
                        make_avatar(avatar_file, filename, remove=True, old=old)

                        env.user.set_info('avatar',
                                    '%s?r=%d' % (filename, randint(1000, 9999)))

        #try:
        #    bday = int(env.request.args('birthdate-day'))
        #    bmon = int(env.request.args('birthdate-month'))
        #    byear = int(env.request.args('birthdate-year'))
        #    env.user.set_info('birthdate', datetime(byear, bmon, bday))
        #except (KeyError, ValueError):
        #    pass

        #try:
        #    env.user.set_info('gender',
        #        {'1':True, '0':False, '':None}[env.request.args('gender')])
        #except KeyError:
            pass

        for name, field in _info_form.iteritems():
            v = env.request.args(name, '').decode('utf-8')
            if v is None:
                continue
            if 'type' in field:
                try:
                    v = field['type'](v)
                except:
                    errors.append(name)
            if 'check' in field and not field['check'](v):
                errors.append(name)
                continue
            env.user.set_info(name, v)

        for name, field in _profile_form.iteritems():
            v = env.request.args(name, '').decode('utf-8')
            if v is None:
                continue
            if 'type' in field:
                try:
                    if field['type'] in (int, long, float) and v == '':
                        continue
                    v = field['type'](v)
                except (TypeError, ValueError):
                    errors.append(name)
                    continue
            if 'check' in field and not field['check'](v):
                errors.append(name)
                continue
            env.user.set_profile(name, v)

        new_password = env.request.args('new-password')
        confirm = env.request.args('confirm')
        if new_password:
            if new_password != confirm:
                errors.append('confirm')
            else:
                env.user.set_password(new_password)

        if not errors:
            blogcss = env.request.args('www.blogcss', '').strip()
            env.user.set_profile('www.usercss', blogcss)
            #if blogcss:
            #    try:
            #        fd = open(os.path.join(settings.blogcss_path,
            #                  '%s.css' % env.user.login), 'w')
            #        fd.write(blogcss)
            #        fd.close()
            #        env.user.set_profile('www.blogcss',
            #                             '%s.css?r=%d' % \
            #                             (env.user.login, randint(1000, 9999)))
            #    except IOError:
            #        pass
            #else:
            #    try:
            #        os.unlink(os.path.join(settings.blogcss_path,
            #                  '%s.css' % env.user.login))
            #    except OSError:
            #        pass
            #    env.user.set_profile('www.blogcss', None)

            usercss = env.request.args('www.usercss', '').strip()
            env.user.set_profile('www.usercss', usercss)
            #if usercss:
            #    try:
            #        fd = open(os.path.join(settings.usercss_path,
            #                  '%s.css' % env.user.login), 'w')
            #        fd.write(usercss)
            #        fd.close()
            #        env.user.set_profile('www.usercss',
            #                             '%s.css?r=%d' % \
            #                             (env.user.login, randint(1000, 9999)))
            #    except IOError:
            #        pass
            #else:
            #    try:
            #        os.unlink(os.path.join(settings.blogcss_path,
            #                  '%s.css' % env.user.login))
            #    except OSError:
            #        pass
            #    env.user.set_profile('www.usercss', None)

        if not errors:
            new_login = env.request.args('login', '').strip()
            if env.user.login != new_login:
                sess = Session()
                add_session(env.user, sess.sessid)
                try:
                    users.rename(new_login)
                except (UserLoginError, UserExists):
                    errors.append('invalid-login')
                except RenameError:
                    #errors.append('rename-timeout')
                    pass

        if not errors:
            env.user.save()
            return Response(redirect='%s://%s.%s/profile?saved=1' % \
                       (env.request.protocol, env.user.login, settings.domain))

    saved = bool(env.request.args('saved'))

    info = env.user.get_info()

    profile = {}
    for k in _profile_form:
        val = env.user.get_profile(k)
        if k.find('.') > -1:
            t, k = k.split('.', 1)
            #t = 'profile_%s' % t
            if not t in profile:
                profile[t] = {}
            profile[t][k] = val
        else:
            profile[k] = val
    #_profile = { k:env.user.get_profile(k) for k in keys }

    #if env.request.method == 'GET':
        #if profile['www']['blogcss']:
        #    try:
        #        with open(os.path.join(settings.blogcss_path,
        #                               '%s.css' % env.user.login)) as fd:
        #            profile['www']['blogcss'] = fd.read()
        #    except IOError:
        #        profile['www']['blogcss'] = ''
        #
        #if profile['www']['usercss']:
        #    try:
        #        with open(os.path.join(settings.usercss_path,
        #                               '%s.css' % env.user.login)) as fd:
        #            profile['www']['usercss'] = fd.read()
        #    except IOError:
        #        profile['www']['usercss'] = ''

    return render('/profile/index.html', saved=saved,
                  errors=errors, info=info, profile=profile, tzlist=tzlist())

@redirect_anonymous
@check_auth
def accounts():
    if env.request.method == 'GET':
        return render('/profile/accounts.html',
                      jids=env.user.get_accounts('xmpp'),
                      unconfirmed=env.user.get_unconfirmed_accounts('xmpp'),
                      active_jid=env.user.get_active_account('xmpp'),
                      saved=env.request.args('saved', False))

    errors = []

    if env.user.check_password_set():
        try:
            if not env.user.check_password(env.request.args('password')):
                errors.append('password')
        except KeyError:
            errors.append('password')

    jids_del = env.request.args('xmpp-del', [])
    if not isinstance(jids_del, list):
        jids_del = [jids_del]
    jids = filter(None, [jid.strip() for jid in jids_del])

    for jid in jids_del:
        env.user.del_account('xmpp', jid)

    jids = env.request.args('xmpp', [])
    if not isinstance(jids, list):
        jids = [jids]
    jids = filter(None, [jid.strip().decode('utf-8') for jid in jids])

    jids_err = []
    for jid in jids:
        try:
            if not parse_email(jid):
                raise ValueError
            users.add_account('xmpp', jid)
        except ValueError:
            jids_err.append(jid)
    if jids_err:
        errors.append('xmpp')

    jid_active = env.request.args('xmpp-set-active')
    if jid_active == 'new':
        jid_active = jids[0] if jids else None
    if jid_active in jids_del or jid_active in jids_err:
        jid_active = None

    if 'password' in errors:
        if not jid_active:
            jid_active = env.user.get_active_account('xmpp')
        return render('/profile/accounts.html',
                      jids=env.user.get_accounts('xmpp'),
                      active_jid=jid_active,
                      jids_err=jids, errors=errors)

    env.user.save()

    if jid_active:
        env.user.set_active_account('xmpp', jid_active)

    if errors:
        if not jid_active:
            jid_active = env.user.get_active_account('xmpp')
        return render('/profile/accounts.html',
                      jids=env.user.get_accounts('xmpp'),
                      active_jid=jid_active,
                      jids_err=jids_err, errors=errors)

    ulogin_del = env.request.args('ulogin-del')
    if ulogin_del:
        if not isinstance(ulogin_del, (list, tuple)):
            ulogin_del = [ulogin_del]

        for u in ulogin_del:
            network, uid = u.strip().split('|')
            env.user.unbind_ulogin(network, uid)

    return Response(redirect='%s://%s.%s/profile/accounts?saved=1' % \
                             (env.request.protocol,
                              env.user.login, settings.domain))

def confirm_account(code):
    if not env.user.id:
        referer = '%s://%s/profile/accounts/confirm/%s' % \
                  (env.request.protocol, settings.domain, code)
        return render('/auth/login.html', referer=referer)

    if not users.confirm_account(code):
        jid_active = env.user.get_active_account('xmpp')
        return render('/profile/accounts.html',
                      jids=env.user.get_accounts('xmpp'),
                      active_jid=jid_active,
                      errors=['confirm'])

    return Response(redirect='%s://%s.%s/profile/accounts?saved=1' % \
                             (env.request.protocol,
                              env.user.login, settings.domain))

@check_auth
def ulogin():
    if env.request.method == 'GET':
        raise Forbidden

    url = "http://ulogin.ru/token.php?token=%s&host=%s" % \
            (env.request.args('token'), settings.domain)
    try:
        resp = urllib2.urlopen(url)
        data = json.loads(resp.read())
        resp.close()
    except urllib2.URLError:
        return render('/profile/accounts.html', errors=['ulogin-fail'])

    if 'error' in data:
        raise Forbidden

    try:
        env.user.bind_ulogin(data['network'], data['uid'],
            nickname=data['nickname'],
            name=('%s %s' % (data['first_name'], data['last_name'])).strip(),
            profile=data['profile'])
    except (KeyError, UserExists):
        pass

    return Response(redirect='%s://%s.%s/profile/accounts?saved=1' % \
                             (env.request.protocol,
                              env.user.login, settings.domain))

