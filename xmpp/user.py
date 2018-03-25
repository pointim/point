from point.core.user import User, NotAuthorized
import geweb.db.pgsql as db
from psycopg2 import IntegrityError
from point.util import RedisPool
from point.util import cache_get, cache_store, cache_del
import json

try:
    import re2 as re
except ImportError:
    import re

import settings

class ImUser(User):
    _profile_table = 'users.profile_im'
    _profile = {
        'off': {'type':'bool', 'default':False},
        'xhtml': {'type':'bool', 'default':False},
        'highlight': {'type':'bool', 'default':False},
        'user_resource': {'type':'bool', 'default':False},
        'post_resource': {'type':'bool', 'default':False},
        'cut': {'type': 'int', 'default': 0},
        'auto_switch': {'type':'bool', 'default':True},
    }

    def session(self, callback=None, **data):
        sessid = 'im_session.%s' % self.get_active_account('xmpp')

        if data:
            self._sess = _Session(sessid, callback, **data)
        else:
            try:
                return self._sess
            except AttributeError:
                self._sess = _Session(sessid)
                return self._sess

    def session_destroy(self):
        try:
            self._sess.destroy()
        except AttributeError:
            pass

    def alias_list(self):
        aliases = {}
        if self.id:
            aliases['user'] = cache_get('aliases:%s' % self.id)
            if aliases['user'] is None:
                aliases['user'] = dict(db.fetchall(
                        "SELECT alias, command FROM users.user_aliases "
                        "WHERE user_id=%s;", [self.id]))
                cache_store('aliases:%s' % self.id, aliases['user'])
        aliases['global'] = cache_get('aliases:global')
        if aliases['global'] is None:
            aliases['global'] = dict(db.fetchall(
                    "SELECT alias, command FROM users.aliases;"))
            cache_store('aliases:global', aliases['global'], 300)
        return aliases

    def get_alias(self, alias):
        aliases = {}
        if self.id:
            aliases['user'] = dict(db.fetchall(
                    "SELECT alias, command FROM users.user_aliases "
                    "WHERE user_id=%s AND LOWER(alias)=%s;",
                    [self.id, alias.lower()]))
        aliases['global'] = dict(db.fetchall(
                    "SELECT alias, command FROM users.aliases "
                    "WHERE LOWER(alias)=%s;",
                    [alias.lower()]))
        return aliases

    def set_alias(self, alias, command):
        if not self.id:
            raise NotAuthorized

        try:
            db.perform("INSERT INTO users.user_aliases "
                       "(user_id, alias, command) VALUES (%s, %s, %s);",
                       [self.id, alias.lower(), command])
        except IntegrityError:
            db.perform("UPDATE users.user_aliases SET alias=%s, command=%s "
                       "WHERE user_id=%s;", [alias.lower(), command, self.id])
        cache_del('aliases:%s' % self.id)

    def delete_alias(self, alias):
        if not self.id:
            raise NotAuthorized

        res = db.fetchone("DELETE FROM users.user_aliases "
                          "WHERE user_id=%s AND alias=%s "
                          "RETURNING alias;", [self.id, alias.lower()])
        if not res:
            return False
        cache_del('aliases:%s' % self.id)
        return True

    def resolve_aliases(self, message):
        aliases = self.alias_list()
        for i in ('user', 'global'):
            try:
                lst = aliases[i]
            except KeyError:
                continue

            lmessage = message.lower()

            for alias, command in lst.iteritems():
                #r = r'^%s(?=\s|$)' % alias
                #if re.match(r, message.lower(), re.I):
                #    return re.sub(r, command, message)

                if alias == lmessage:
                    return command

                if lmessage.startswith("%s " % alias):
                    l = len(alias)
                    return "%s %s" % (command, message[l:])

        return message

    def update_tune_data(self, data):
        cache_key = 'user_tune:%s' % self.id
        if data:
            cache_store(cache_key, data)
        else:
            cache_del(cache_key)


class SessionCallError(Exception):
    pass

class _Session(object):
    def __init__(self, sessid, callback=None, **data):
        self.sessid = sessid
        self._redis = RedisPool(settings.storage_socket)

        if callback and data:
            data['__callback__'] = [callback.__module__, callback.__name__]
            self._redis.set(sessid, json.dumps(data))
            del data['__callback__']
            self._redis.expire(self.sessid, settings.session_expire)
            self._callback = callback
            self._data = data
        else:
            data = self._redis.get(self.sessid)
            if not data:
                self._callback = None
                self._data = None
                return
            data = json.loads(data)
            if '__callback__' in data:
                mod, fn = tuple(data['__callback__'])
                mod = __import__(mod, globals(), locals(), [fn], -1)
                self._callback = getattr(mod, fn)
                del data['__callback__']
            else:
                self._callback = None
            self._data = data

    def __call__(self, data):
        if self._callback:
            return self._callback(data)
        raise SessionCallError

    def __getitem__(self, key):
        return self._data[key]

    def data(self):
        return self._data

    def destroy(self):
        self._redis.delete(self.sessid)

