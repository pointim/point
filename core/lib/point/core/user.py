from geweb import log
from point.util import parse_email
import geweb.db.pgsql as db
from point.util.redispool import RedisPool
from point.util.env import env
from point.util import cache_get, cache_store, cache_del, unb26
from point.util import validate_nickname
from point.core import PointError
import json
from hashlib import sha1
from psycopg2 import IntegrityError, ProgrammingError, DataError
from datetime import datetime
import dateutil.parser

try:
    import re2 as re
except ImportError:
    import re

import settings

USER_TYPES = ('user', 'group', 'feed')
ACCOUNT_TYPES = ('xmpp', 'email')

class UserError(PointError):
    pass

class AlreadyAuthorized(UserError):
    pass

class NotAuthorized(UserError):
    pass

class UserExists(UserError):
    pass

class UserNotFound(UserError):
    pass

class AlreadySubscribed(UserError):
    pass

class AlreadyRequested(UserError):
    pass

class SubscribeError(UserError):
    pass

class AddressNotFound(UserError):
    pass

class UserLoginError(UserError):
    pass

class RenameError(UserError):
    pass

class User(object):
    type = 'user'

    def __init__(self, field, value=None):
        self.id = None
        self.login = None
        self.accounts = []
        self.accounts_add = []
        self.accounts_del = []
        self.profile = {}
        self.profile_upd = {}
        self.info = {}
        self.info_upd = {}
        self.password = None
        self._private = None

        self.redis = RedisPool(settings.storage_socket)

        if isinstance(field, (int, long)):
            self.id = field

            self.login = cache_get('login:%s' % field)
            if not self.login:
                res = db.fetchone("SELECT login FROM users.logins WHERE id=%s;",
                                 [field])
                if not res:
                    raise UserNotFound
                self.login = res[0]
                cache_store('login:%s' % field, self.login)
            return

        if not value:
            #raise UserNotFound
            # empty user
            return

        if field == 'login':
            r = cache_get('id_login:%s' % value.lower())
            if r:
                try:
                    self.id, self.login, self.type = r
                except ValueError:
                    self.id, self.login = r
                    self.type = 'user'
            else:
                res = db.fetchone("SELECT id, login, type FROM users.logins "
                                  "WHERE lower(login)=%s;",
                                 [str(value).lower()])
                if not res:
                    raise UserNotFound(value)
                self.id, self.login, self.type = res
                cache_store('id_login:%s' % value.lower(), [res[0], res[1], res[2]])
            return

        r = cache_get('addr_id_login:%s' % value.lower())
        if r:
            self.id, self.login = r
        else:
            res = db.fetchone("SELECT u.id, u.login FROM users.accounts a "
                             "JOIN users.logins u ON u.id=a.user_id "
                             "WHERE a.type=%s AND lower(a.address)=%s;",
                             [field, value.lower()]) #, _cache=3600)
            if res:
                self.id, self.login = res
                cache_store('addr_id_login:%s' % value.lower(),[res[0], res[1]])

    def __repr__(self):
        return "<User: id=%s login=%s>" % (self.id, self.login)

    def __cmp__(self, other):
        if not isinstance(other, User):
            raise TypeError
        if not self.id or not other.id:
            return False
        return self.id - other.id

    @classmethod
    def from_data(cls, id, login, **kwargs):
        self = cls(None, None)
        self.id = id
        self.login = login

        if 'accounts' in kwargs:
            for type, address in kwargs['accounts']:
                if type in ACCOUNT_TYPES and not parse_email(address):
                    raise ValueError(address)
            self.accounts = kwargs['accounts']
        if 'profile' in kwargs:
            self.profile = kwargs['profile']
        if 'info' in kwargs:
            self.info = kwargs['info']
        if 'password' in kwargs and kwargs['password']:
            self.set_password(kwargs['password'])

        #self.info = {}

        return self

    @staticmethod
    def _passhash(password):
        if password is None:
            return None

        phash = sha1(password).hexdigest().lower()
        ph = sha1('%s%s' % (settings.secret, phash)).hexdigest().lower()
        #print '++++++++++++++++++++++++++++++++++', ph
        return ph

    @classmethod
    def authenticate(cls, login, password):
        #print '-------------------', login, password
        res = db.fetchone("SELECT id FROM users.logins "
                         "WHERE lower(login)=%s AND password=%s;",
                         [login.lower(), cls._passhash(password)])
        if res:
            return cls(res[0], login)

        raise NotAuthorized

    def get_tune(self):
        return cache_get("user_tune:%s" % self.id)

    def bind_ulogin(self, network, uid, nickname=None, name=None, profile=None):
        if not self.id:
            raise NotAuthorized
        try:
            db.perform("INSERT INTO users.ulogin_accounts "
                       "(id, network, uid, nickname, name, profile) "
                       "VALUES (%s, %s, %s, %s, %s, %s);",
                       [self.id, network, uid, nickname, name, profile])
        #except IntegrityError:
        #    raise UserExists
        finally: pass

    def unbind_ulogin(self, network, uid):
        if not self.id:
            raise NotAuthorized
        db.perform("DELETE FROM users.ulogin_accounts "
                   "WHERE id=%s AND network=%s AND uid=%s;",
                   [self.id, network, uid])

    def get_ulogin_accounts(self):
        if not self.id:
            return []
        return db.fetchall("SELECT * FROM users.ulogin_accounts WHERE id=%s;",
                           [self.id])

    def get_accounts(self, type):
        if type not in ACCOUNT_TYPES:
            raise ValueError(type)
        res = db.fetchall("SELECT address FROM users.accounts "
                          "WHERE user_id=%s AND type=%s;",
                          [self.id, type])
        return [r['address'] for r in res]

    def get_unconfirmed_accounts(self, type):
        if type not in ACCOUNT_TYPES:
            raise ValueError(type)
        res = db.fetchall("SELECT address FROM users.accounts_unconfirmed "
                          "WHERE user_id=%s AND type=%s;",
                          [self.id, type])
        return [r['address'] for r in res]

    def add_account(self, type, address):
        if type in ACCOUNT_TYPES and not parse_email(address):
            raise ValueError(address)

        res = db.fetchone("SELECT id FROM users.accounts "
                          "WHERE type=%s AND address=%s;",
                          [type, address])
        if res:
            return

        res = db.fetchone("SELECT id FROM users.accounts_unconfirmed "
                          "WHERE type=%s AND address=%s;",
                          [type, address])
        if res:
            return

        code = '%s%s%s%s' % (settings.secret, datetime.now(), type, address)
        code = sha1(code).hexdigest().lower()
        self.accounts_add.append((type, address, code))

        cache_del("addr_id_login:%s" % address)

        return code

    def confirm_account(self, code):
        res = db.fetchone("SELECT id, user_id, type, address, code "
                          "FROM users.accounts_unconfirmed "
                          "WHERE code=%s;",
                          [code.lower()])
        if not res:
            return False

        if res['user_id'] != self.id or res['code'] != str(code).lower():
            return False

        db.perform("DELETE FROM users.accounts_unconfirmed WHERE id=%s;",
                   [res['id']])

        try:
            db.perform("INSERT INTO users.accounts (user_id, type, address) "
                       "VALUES (%s, %s, %s);",
                       [self.id, res['type'], res['address']])
        except IntegrityError:
            log.error("%s %s already exists" % (res['type'], res['address']))
            return False

        cache_del("addr_id_login:%s" % res['address'])

        return True

    def del_account(self, type, address):
        self.accounts_del.append((type, address))
        cache_del("addr_id_login:%s" % address)

    def set_active_account(self, type, address):
        if not self.id:
            return
        if type not in ACCOUNT_TYPES:
            return
        self.redis.set('active.%d' % self.id,
                  json.dumps({'type':type, 'addr': address}))

    def get_active_account(self, type=None):
        if not self.id:
            return None
        data = self.redis.get('active.%d' % self.id)
        if data:
            data = json.loads(data)
        else:
            _type = type if type else 'xmpp'
            res = db.fetchone("SELECT type, address FROM users.accounts WHERE "
                             "user_id=%s AND type=%s;", [self.id, _type])
            if not res:
                self.redis.set('active.%d' % self.id, '{}')
                self.redis.expire('active.%d' % self.id, 60)
                return None

            self.redis.set('active.%d' % self.id,
                      json.dumps({'type': _type, 'addr': res['address']}))
            data = {'type': res['type'], 'addr': res['address']}

        if not type:
            return data
        try:
            if data['type'] == type:
                return data['addr']
        except KeyError:
            return None
        return None

    _profile_table = 'users.profile'
    _profile = {
        'private': {'type': 'bool', 'default': False},
        'lang': {'type': 'str', 're': re.compile(r'^(?:by|en|ru|uk)$'),
                 'default':settings.lang},
        'tz': {'type': 'int', 'default': settings.timezone},
        'deny_anonymous': {'type': 'bool', 'default': False}
    }

    def set_profile(self, param, value):
        def check(p, param, value):
            if p[param]['type'] == 'bool':
                if isinstance(value, (str, unicode)):
                    if value.lower() in ['no', 'false', 'none', 'null', '0']:
                        value = False
                    else:
                        value = True
                if param == 'private':
                    if self.get_profile('private') and not value:
                        self._private = False
                    elif not self.get_profile('private') and value:
                        self._private = True
            elif p[param]['type'] == 'str' and p[param]['re']:
                if not re.match(p[param]['re'], value):
                    raise ValueError
            return value

        if self.__class__ != User and param in self._profile:
            check(self._profile, param, value)
            table = self._profile_table
        elif param in User._profile:
            check(User._profile, param, value)
            table = User._profile_table
        elif param.find('.') > -1:
            table, param = param.split('.', 1)
            table = 'users.profile_%s' % table
            if param == 'id' or re.match(r'\W', param):
                raise KeyError
        else:
            raise KeyError

        if table not in self.profile:
            self.profile[table] = {}
        self.profile[table][param] = value
        if table not in self.profile_upd:
            self.profile_upd[table] = {}
        self.profile_upd[table][param] = value
        cache_del('profile:%s:%s' % (table, self.id))

    def get_profile(self, param):
        def get(table, param):
            try:
                return self.profile[table][param]
            except KeyError:
                #try:
                #    # FIXME: profile models
                #    db.perform("INSERT INTO %s (id) VALUES (%%s);" % \
                #               table, [self.id])
                #except IntegrityError:
                #    pass
                res = cache_get('profile:%s:%s' % (table, self.id))
                if res:
                    self.profile[table] = res
                else:
                    res = db.fetchone("SELECT * FROM %s WHERE id=%%s;" % \
                                     table, [self.id])
                    if not res:
                        try:
                            res = db.fetchone("INSERT INTO %s (id) VALUES (%%s) RETURNING *;" % \
                                              table, [self.id])
                        except IntegrityError:
                            return None
                    if res:
                        self.profile[table] = dict(res)
                        cache_store('profile:%s:%s' % (table, self.id),
                                    self.profile[table])
                    else:
                        #try:
                        #    return cls._profile[param]['default']
                        #except KeyError:
                        #    return None
                        return None
                # FIXME: remove recursive call
                try:
                    return self.profile[table][param]
                except KeyError:
                    cache_del('profile:%s:%s' % (table, self.id))
                    return get(table, param)
                #finally: pass

        if not self.id:
            return self.profile_defaults(param)

        if self.__class__ != User and param in self._profile:
            return get(self._profile_table, param)
        elif param in User._profile:
            return get(User._profile_table, param)
        elif param.find('.') > -1:
            table, param = param.split('.', 1)
            table = 'users.profile_%s' % table
            if param == 'id' or re.match(r'\W', param):
                raise KeyError
            return get(table, param)
        else:
            raise KeyError

    def profile_defaults(self, param=None):
        if not param:
            return {p:self._profile[p]['default'] for p in self._profile}

        cls = self.__class__
        while cls:
            try:
                return cls._profile[param]['default']
            except KeyError:
                cls = cls.__base__
            except AttributeError:
                return None

        return None

    def set_info(self, param, value):
        self.info[param] = value
        self.info_upd[param] = value

    def get_info(self, param=None):
        if not self.info:
            res = cache_get('userinfo:%s' % self.id)
            if res:
                for k in ('birthdate', 'created'):
                    res[k] = dateutil.parser.parse(res[k]) if res[k] else None
                self.info = res
            else:
                res = db.fetchone("SELECT i.name,p.private, p.deny_anonymous,"
                                "i.email, i.xmpp, i.icq, i.skype, i.about, "
                                "i.avatar, i.gender, i.birthdate, i.location,"
                                "i.homepage, i.created "
                                "FROM users.info i "
                                "LEFT OUTER JOIN users.profile p "
                                "ON (i.id = p.id) "
                                "WHERE i.id=%s;", [self.id])

                if res:
                    self.info = dict(res)
                    res = dict(res)
                    for k in ('birthdate', 'created'):
                        res[k] = res[k].isoformat() if res[k] else None
                    cache_store('userinfo:%s' % self.id, res)

            if not self.info:
                return None

            self.info.update({'tune': self.get_tune()})

        if param:
            try:
                return self.info[param]
            except KeyError:
                return None
        else:
            return self.info

    def info_changed(self):
        return bool(self.info_upd)

    def check_password_set(self):
        try:
            return self._password_set
        except AttributeError:
            pass
        if not self.id:
            self._password_set = False
            return self._password_set
        res = db.fetchone("SELECT password FROM users.logins WHERE id=%s;",
                          [self.id])
        if not res:
            self._password_set = False
            return self._password_set
        self._password_set = bool(res['password'])
        return self._password_set

    def check_password(self, password):
        res = db.fetchone("SELECT password FROM users.logins "
                         "WHERE id=%s;", [self.id])
        if not res:
            return False

        if res[0] != self._passhash(password):
            return False

        return True

    def set_password(self, password):
        self.password = self._passhash(password)

    def save(self):
        if not self.login:
            raise UserError("Cannot save anonymous user")

        is_new = False

        # create user
        if not self.id:
            if not self.login or not validate_nickname(self.login):
                raise UserError('Invalid Login: "%s"' % self.login)
            self.id = db.fetchone("INSERT INTO users.logins (login, type) "
                                 "VALUES (%s, %s) RETURNING id;",
                                 [self.login, self.type])[0]
            db.perform("INSERT INTO users.info (id, name) VALUES (%s, %s);",
                       [self.id, self.login])
            db.perform("INSERT INTO users.profile (id, private, lang) "
                       "VALUES (%s, false, 'en');", [self.id])

            self.accounts_add = self.accounts
            is_new = True

        if not is_new:
            try:
                if self._private == True:
                    self._set_private()
                elif self._private == False:
                    self._set_public()
            except AttributeError:
                pass

        # save accounts
        for acc in self.accounts_add:
            try:
                if len(acc) == 3:
                    db.perform("INSERT INTO users.accounts_unconfirmed "
                               "(user_id, type, address, code) "
                               "VALUES (%s, %s, %s, %s);",
                               [self.id, acc[0], acc[1], acc[2]])
                else:
                    db.perform("INSERT INTO users.accounts "
                               "(user_id, type, address) "
                               "VALUES (%s, %s, %s);",
                               [self.id, acc[0], acc[1]])


            except IntegrityError:
                log.error("%s %s already exists" % (acc[0], acc[1]))

        self.accounts_add = []

        for type, address in self.accounts_del:
            db.perform("DELETE FROM users.accounts WHERE "
                       "user_id=%s AND type=%s AND address=%s;",
                       [self.id, type, address])

            db.perform("DELETE FROM users.accounts_unconfirmed WHERE "
                       "user_id=%s AND type=%s AND address=%s;",
                       [self.id, type, address])

        self.accounts_del = []

        # save profile
        if self.profile_upd:
            for table in self.profile_upd:
                f = []
                for k in self.profile_upd[table]:
                    f.append("%s=%%(%s)s" % (k, k))
                try:
                    try:
                        db.perform("INSERT INTO %s (id) VALUES (%%s);" % \
                                   table, [self.id])
                    except IntegrityError:
                        pass
                    db.perform("UPDATE %s SET %s WHERE id=%s;" % \
                               (table, ','.join(f), self.id),
                               self.profile_upd[table])
                    cache_del('profile:%s:%s' % (table, self.id))
                except ProgrammingError:
                    raise KeyError
                except DataError:
                    raise ValueError
            self.profile_upd = {}

        if self.info_upd:
            f = []
            for k in self.info_upd:
                #if not self.info_upd[k]:
                #    self.info_upd[k] = None
                f.append("%s=%%(%s)s" % (k, k))
            db.perform("UPDATE users.info SET %s WHERE id=%s;" % \
                       (','.join(f), self.id),
                       self.info_upd)
            self.info_upd = {}
            cache_del('userinfo:%s' % self.id)

        if self.password:
            db.perform("UPDATE users.logins SET password=%s WHERE id=%s;",
                       (self.password, self.id))

    def _set_private(self):
        res = [u['id'] for u in \
            db.fetchall("SELECT user_id AS id FROM subs.users "
                        "WHERE to_user_id=%(id)s "
                        "EXCEPT "
                        "SELECT to_user_id AS id FROM users.whitelist "
                        "WHERE user_id=%(id)s;", {'id': self.id})]
        db.perform("DELETE FROM subs.users "
                   "WHERE user_id=ANY(%s) AND to_user_id=%s;",
                   [res, self.id])
        db.batch("INSERT INTO subs.requests VALUES(%(u)s, %(to)s);",
                 [{'u':u, 'to':self.id} for u in res])
        db.perform("DELETE FROM subs.posts s USING posts.posts p "
                   "WHERE s.post_id=p.id "
                   "AND s.user_id=ANY(%s) AND p.author=%s;",
                   [res, self.id])
        db.perform("DELETE FROM subs.tags_user "
                   "WHERE to_user_id=%s AND user_id=ANY(%s);",
                   [self.id, res])

    def _set_public(self):
        res = [u['user_id'] for u in \
                db.fetchall("DELETE FROM subs.requests "
                            "WHERE to_user_id=%s RETURNING user_id;",
                            [self.id])]
        db.batch("INSERT INTO subs.users VALUES(%(u)s, %(to)s);",
                 [{'u':u, 'to':self.id} for u in res])

    def is_authorized(self):
        return bool(self.id)

    def subscribe(self, obj):
        """Subscribe to anything
           obj - subscriptable object
        """
        obj.add_subscriber(self)

    def add_subscriber(self, user):
        try:
            db.perform("INSERT INTO subs.users (user_id, to_user_id) "
                       "VALUES (%s, %s);",
                       [user.id, self.id])
        except IntegrityError:
            raise AlreadySubscribed
        self.add_rec_subscriber(user)
        user.subs_count(False)
        self.readers_count(False)

    def add_rec_subscriber(self, user):
        try:
            db.perform("INSERT INTO subs.recommendations VALUES (%s, %s);",
                       [user.id, self.id])
        except IntegrityError:
            raise AlreadySubscribed

    def check_subscriber(self, user):
        if self == user or not user or not self.id:
            return False
        res = db.fetchone("SELECT user_id FROM subs.users WHERE "
                         "user_id=%s AND to_user_id=%s;", [user.id, self.id])
        return bool(res)

    def check_rec_subscriber(self, user):
        if self == user or not user or not self.id:
            return False
        res = db.fetchone("SELECT user_id FROM subs.recommendations WHERE "
                         "user_id=%s AND to_user_id=%s;", [user.id, self.id])
        return bool(res)

    def check_subscribe_to_user(self, login):
        user = User('login', login)
        if self == user or not user or not self.id:
            return False
        res = db.fetchone("SELECT user_id FROM subs.users WHERE "
                         "user_id=%s AND to_user_id=%s;", [self.id, user.id])
        return bool(res)

    def check_subscribe_to_user_rec(self, login):
        user = User('login', login)
        if self == user or not user or not self.id:
            return False
        res = db.fetchone("SELECT user_id FROM subs.recommendations WHERE "
                         "user_id=%s AND to_user_id=%s;", [self.id, user.id])
        return bool(res)

    def incoming_subscription_requests(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT u.id, u.login, i.name, i.gender, i.avatar "
                          "FROM subs.requests s "
                          "JOIN users.logins u ON u.id=s.user_id "
                          "LEFT OUTER JOIN users.info i ON i.id=s.user_id "
                          "WHERE s.to_user_id=%s;", [self.id])
        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)
        return users

    def outgoing_subscription_requests(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT u.id, u.login, i.name, i.gender, i.avatar "
                          "FROM subs.requests s "
                          "JOIN users.logins u ON u.id=s.to_user_id "
                          "LEFT OUTER JOIN users.info i ON i.id=s.to_user_id "
                          "WHERE s.user_id=%s;", [self.id])
        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)
        return users

    def add_subscription_request(self, user):
        if self.check_subscriber(user):
            raise AlreadySubscribed

        if not self.get_profile('private'):
            self.add_subscriber(user)
            return True

        res = db.fetchone("SELECT user_id FROM users.blacklist WHERE "
                         "user_id=%s AND to_user_id=%s;", [self.id, user.id])
        if res:
            raise SubscribeError

        res = db.fetchone("SELECT user_id FROM users.whitelist WHERE "
                         "user_id=%s AND to_user_id=%s;", [self.id, user.id])
        if res:
            self.add_subscriber(user)
            return True

        try:
            db.perform("INSERT INTO subs.requests "
                       "VALUES (%s, %s);", [user.id, self.id])
        except IntegrityError:
            raise AlreadyRequested

        return False

    def unsubscribe(self, obj):
        """Unsubscribe from anything
           obj - subscriptable object
        """
        obj.del_subscriber(self)

    def del_subscriber(self, user):
        retval = bool(user.check_subscriber(env.user))

        db.perform("DELETE FROM subs.users WHERE "
                   "user_id=%s AND to_user_id=%s;", [user.id, self.id])
        db.perform("DELETE FROM subs.requests WHERE "
                   "user_id=%s AND to_user_id=%s;", [user.id, self.id])
        self.del_rec_subscriber(user)
        user.subs_count(False)
        self.readers_count(False)

        return retval

    def del_rec_subscriber(self, user):
        db.perform("DELETE FROM subs.recommendations WHERE "
                   "user_id=%s AND to_user_id=%s;", [user.id, self.id])

    def whitelist(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT u.id, u.login, i.name, i.gender, i.avatar "
                          "FROM users.whitelist w "
                          "JOIN users.logins u ON u.id=w.to_user_id "
                          "LEFT OUTER JOIN users.info i ON i.id=w.to_user_id "
                          "WHERE w.user_id=%s;", [self.id])
        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)

        return sorted(users, key=lambda u: u.login.lower())

    def add_to_whitelist(self, user):
        try:
            db.perform("INSERT INTO users.whitelist VALUES (%s, %s);",
                       [self.id, user.id])
        except IntegrityError:
            return False

        res = db.fetchone("DELETE FROM subs.requests WHERE "
                          "user_id=%s AND to_user_id=%s "
                          "RETURNING user_id;", [user.id, self.id])
        if res:
            self.add_subscriber(user)
        return True

    def del_from_whitelist(self, user):
        res = db.fetchone("DELETE FROM users.whitelist WHERE "
                          "user_id=%s AND to_user_id=%s RETURNING user_id;",
                          [self.id, user.id])
        if self.get_profile('private'):
            self.del_subscriber(user)

        return bool(res)

    def check_whitelist(self, user):
        if self.id == user.id or not self.id:
            return True
        if not user.id:
            return False

        res = db.fetchone("SELECT user_id FROM users.whitelist "
                         "WHERE user_id=%s AND to_user_id=%s;",
                         [self.id, user.id])
        return bool(res)

    def blacklist(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT u.id, u.login, i.name, i.gender, i.avatar "
                          "FROM users.blacklist b "
                          "JOIN users.logins u ON u.id=b.to_user_id "
                          "LEFT OUTER JOIN users.info i ON i.id=b.to_user_id "
                          "WHERE b.user_id=%s;", [self.id])
        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)

        return sorted(users, key=lambda u: u.login.lower())

    def add_to_blacklist(self, user):
        try:
            db.perform("INSERT INTO users.blacklist VALUES (%s, %s);",
                       [self.id, user.id])
        except IntegrityError:
            return False
        db.perform("DELETE FROM subs.requests WHERE "
                   "user_id=%s AND to_user_id=%s;", [user.id, self.id])
        self.unsubscribe(user)
        self.del_from_whitelist(user)
        return True

    def del_from_blacklist(self, user):
        res = db.fetchone("DELETE FROM users.blacklist WHERE "
                          "user_id=%s AND to_user_id=%s RETURNING user_id;",
                          [self.id, user.id])
        return bool(res)

    def check_blacklist(self, user):
        if self == user or not user or not self.id:
            return False
        res = db.fetchone("SELECT user_id FROM users.blacklist "
                         "WHERE user_id=%s AND to_user_id=%s;",
                         [self.id, user.id])
        return bool(res)

    def posts_count(self):
        c = cache_get('posts_count:%s' % self.id)
        if c:
            return c
        try:
            c = db.fetchone("SELECT count(id) FROM posts.posts "
                            "WHERE author=%s;", [self.id])[0]
            cache_store('posts_count:%s' % self.id, c, 30)
            return c
        except IndexError:
            return 0

    def comments_count(self):
        c = cache_get('comments_count:%s' % self.id)
        if c:
            return c
        try:
            c = db.fetchone("SELECT count(id) FROM posts.comments "
                            "WHERE author=%s;", [self.id])[0]
            cache_store('comments_count:%s' % self.id, c, 30)
            return c
        except IndexError:
            return 0

    def unread_posts_count(self, ptype=None):
        if not self.id:
            return 0

        if not hasattr(self, '_unread_posts'):
            self._unread_posts = {}

        if not self._unread_posts:
            res = db.fetchall("SELECT type, count(post_id) AS cnt "
                              "FROM posts.unread_posts "
                              "WHERE user_id=%s GROUP BY type;",
                              [self.id])
            self._unread_posts = { c['type']: c['cnt'] for c in res }

        if ptype:
            try:
                return self._unread_posts[ptype]
            except KeyError:
                return 0
        else:
            return reduce(lambda memo, cnt: memo + cnt,
                          self._unread_posts.values(), 0)

    def unread_comments_count(self, ptype=None):
        if not self.id:
            return 0

        if not hasattr(self, '_unread_comments'):
            self._unread_comments = {}

        if not self._unread_comments:
            res = db.fetchall("SELECT type, count(post_id) AS cnt "
                              "FROM posts.unread_comments "
                              "WHERE user_id=%s GROUP BY type;",
                              [self.id])
            self._unread_comments = { c['type']: c['cnt'] for c in res }

        if ptype:
            try:
                return self._unread_comments[ptype]
            except KeyError:
                return 0
        else:
            return reduce(lambda memo, cnt: memo + cnt,
                          self._unread_comments.values(), 0)

    def subs_count(self, cache=True):
        if not cache:
            c = cache_get('subs_count:%s' % self.id)
            if c:
                return c
        try:
            c = db.fetchone("SELECT count(user_id) FROM subs.users "
                            "WHERE user_id=%s;", [self.id])[0]
            cache_store('subs_count:%s' % self.id, c)
            return c
        except IndexError:
            return 0

    def subscriptions(self, type=None):
        if not self.id:
            return []

        key = "subs:%s:%s" % (self.id, type or 'all')
        res = cache_get(key)

        if not res:
            values = [self.id]

            if type:
                type_filter = " AND u.type=%s"
                values.append(type)
            else:
                type_filter = ''

            res = db.fetchall("SELECT u.id, u.login, u.type, "
                              "i.name, i.gender, i.avatar, i.homepage "
                              "FROM subs.users s "
                              "JOIN users.logins u ON u.id=s.to_user_id "
                              "LEFT OUTER JOIN users.info i "
                                "ON i.id=s.to_user_id "
                              "WHERE s.user_id=%%s %s;" % type_filter,
                              values)
            cache_store(res, 120)

        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar'], 'homepage': r['homepage']})
            users.append(u)

        return sorted(users, key=lambda u: u.login.lower())

    def readers_count(self, cache=True):
        if not cache:
            c = cache_get('readers_count:%s' % self.id)
            if c:
                return c
        try:
            c = db.fetchone("SELECT count(user_id) FROM subs.users "
                            "WHERE to_user_id=%s;", [self.id])[0]
            cache_store('readers_count:%s' % self.id, c)
            return c
        except IndexError:
            return 0

    def subscribers(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT u.id, u.login, i.name, i.gender, i.avatar "
                          "FROM subs.users s "
                          "JOIN users.logins u ON u.id=s.user_id "
                          "LEFT OUTER JOIN users.info i ON i.id=s.user_id "
                          "WHERE s.to_user_id=%s;", [self.id])
        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)

        return sorted(users, key=lambda u: u.login.lower())

    def blacklisters(self):
        if not self.id:
            return []

        res = db.fetchall("""
            SELECT u.id, u.login, i.name, i.gender, i.avatar
            FROM users.blacklist AS bl
            INNER JOIN users.logins AS u ON bl.user_id = u.id
            LEFT OUTER JOIN users.info AS i ON i.id = bl.user_id
            WHERE bl.to_user_id=%s;
            """, [self.id])

        users = []
        for r in res:
            u = User.from_data(r['id'], r['login'],
                    info={'name': r['name'], 'gender': r['gender'],
                          'avatar': r['avatar']})
            users.append(u)

        users.sort(key=lambda u: u.login.lower())
        return users


    def tags(self, limit=None, sort_by_name=False, all=False):
        if not self.id:
            return []

        key = 'user_tags:%d:%s' % (self.id, (limit or 'all'))

        if not all:
            tags = cache_get(key)
            if tags:
                return tags

        order = 'tag ASC' if sort_by_name else 'cnt DESC'
        limit = ("LIMIT %d" % limit) if limit else ''

        tags = db.fetchall("SELECT tag, count(post_id) AS cnt "
                           "FROM posts.tags WHERE user_id=%%s "
                           "GROUP BY tag ORDER BY %s "
                           "%s;" % (order, limit),
                           [self.id])

        cache_store(key, [dict(t) for t in tags], 60)

        return tags

    def tag_subscriptions(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT t.to_user_id AS user_id, "
                          "COALESCE(u.login, '') AS login, "
                          "array_agg(t.tag) AS tags "
                          "FROM subs.tags t "
                          "LEFT OUTER JOIN users.logins u ON t.to_user_id=u.id "
                          "WHERE t.user_id=%s "
                          "GROUP BY t.to_user_id, u.login;", [self.id])
        return res

    def check_post_subscribed(self, post):
        """Check for user subscription to post.
        Return True, if subscribed, otherwise False
        """
        res = db.fetchone("SELECT user_id, post_id FROM subs.posts "
                          "WHERE user_id=%s AND post_id=%s;",
                          [self.id, unb26(post)])
        return bool(res)

    def check_tag_subscribed(self, tag, user=None):
        if user:
            res = db.fetchone("SELECT 1 FROM subs.tags_user "
                              "WHERE user_id=%s AND to_user_id=%s AND tag=%s;",
                              [self.id, user.id, tag])
        else:
            res = db.fetchone("SELECT 1 FROM subs.tags_global "
                              "WHERE user_id=%s AND tag=%s;",
                              [self.id, tag])
        return bool(res)

    def tag_blacklist(self):
        if not self.id:
            return []

        res = db.fetchall("SELECT t.to_user_id AS user_id, "
                          "COALESCE(u.login, '') AS login, "
                          "array_agg(t.tag) AS tags "
                          "FROM posts.tags_blacklist t "
                          "LEFT OUTER JOIN users.logins u ON t.to_user_id=u.id "
                          "WHERE t.user_id=%s "
                          "GROUP BY t.to_user_id, u.login;", [self.id])
        return res

    def check_tag_blacklisted(self, tag, user=None):
        if user:
            res = db.fetchone("SELECT 1 FROM posts.tags_blacklist_user "
                              "WHERE user_id=%s AND to_user_id=%s AND tag=%s;",
                              [self.id, user.id, tag])
        else:
            res = db.fetchone("SELECT 1 FROM posts.tags_blacklist_global "
                              "WHERE user_id=%s AND tag=%s;",
                              [self.id, tag])
        return bool(res)

    def rename(self, login):
        if not self.id:
            raise NotAuthorized
        if cache_get('renamed:%s' % self.id):
            raise RenameError

        if not validate_nickname(login):
            raise UserLoginError

        old_login = self.login
        self.login = login

        try:
            db.perform("UPDATE users.logins SET login=%s WHERE id=%s;",
                       [login, self.id])
        except IntegrityError:
            raise UserExists

        cache_store('renamed:%s' % self.id, 1, settings.user_rename_timeout)
        cache_del('id_login:%s' % old_login.lower())

        for t in ACCOUNT_TYPES:
            for addr in self.get_accounts(t):
                cache_del("addr_id_login:%s" % addr)

    def is_renamed(self):
        if not self.id:
            raise NotAuthorized
        return bool(cache_get('renamed:%s' % self.id))

    def todict(self):
        #self.info = {}
        return {
            "id": self.id,
            "login": self.login,
            "name": self.get_info("name"),
            "avatar": self.get_info("avatar"),
        }

class AnonymousUser():
    id = -1
    def __init__(self, login):
        self.login = login

def check_auth(fn):
    def _check(*args, **kwargs):
        if not env.user.is_authorized():
            raise NotAuthorized
        return fn(*args, **kwargs)
    return _check

