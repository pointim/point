#from point.util import db
import geweb.db.pgsql as db
from point.util.redispool import RedisPool
from point.util.env import env
from point.core.user import User, NotAuthorized
from geweb.middleware import Middleware
from geweb.session import Session
from point.util.sessions import add_session, del_session

import settings

class WebUser(User):
    _profile_table = 'users.profile_www'
    _profile = {
        'blogcss': {'type': 'str', 'default': None},
        'usercss': {'type': 'str', 'default': None},
        'ignorecss': {'type': 'bool', 'default': False},
        'tree': {'type': 'bool', 'default': False},
    }

    def __init__(self, field=None, value=None):
        if isinstance(field, (int, long)):
            User.__init__(self, field)
            return
        if field and value:
            User.__init__(self, field, value)
            return

        sess = Session()

        self.id = sess['id']
        self.login = sess['login']
        self.type = 'user'

        self.accounts = []
        self.accounts_add = []
        self.accounts_del = []
        self.profile = {}
        self.profile_upd = {}
        self.info = {}
        self.info_upd = {}
        self.password = None

        self.redis = RedisPool(settings.storage_socket)

        if self.id:
            self._get_avatar()

    def authenticate(self, login=None, password=None):
        if login is not None:
            res = db.fetchone("SELECT id, login FROM users.logins "
                             "WHERE lower(login)=%s AND password=%s;",
                             [login.lower(), self._passhash(password)])

            if not res:
                self.id = None
                self.login = None
                raise NotAuthorized

            self.id = res['id']
            self.login = res['login']
            self._get_avatar()

        elif not self.id:
            raise NotAuthorized

        sess = Session()
        sess['id'] = self.id
        sess['login'] = self.login
        sess.save()

        add_session(self, sess.sessid)

        return sess.sessid

    def authenticate_ulogin(self, network, uid):
        res = db.fetchone("SELECT id FROM users.ulogin_accounts "
                          "WHERE network=%s AND uid=%s;", [network, uid])
        if not res:
            raise NotAuthorized

        User.__init__(self, int(res[0]))
        self.authenticate()

    def logout(self):
        sess = Session()
        del_session(self, sess.sessid)
        sess.destroy()

    def _get_avatar(self):
        if not self.id:
            self.avatar = None
            return
        self.avatar = self.get_info('avatar')

    def set_info(self, param, value):
        User.set_info(self, param, value)
        if param == 'avatar':
            self.avatar = value

class UserMiddleware(Middleware):
    def process_request(self, request):
        env.user = WebUser()

