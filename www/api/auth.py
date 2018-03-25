from point.core.user import NotAuthorized, AlreadyAuthorized
from point.util.env import env
from geweb.util import csrf, csrf_token

from api import api

@api
def login():
    if env.user.is_authorized():
        raise AlreadyAuthorized

    try:
        login = env.request.args('login')
        password = env.request.args('password')
        if not login or not password:
            raise NotAuthorized
        return {
            'token': env.user.authenticate(login, password),
            'csrf_token': csrf_token()
        }
    except KeyError:
        raise NotAuthorized

@csrf
@api
def logout():
    env.user.logout()

