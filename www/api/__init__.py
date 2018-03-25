import json
import datetime
from geweb.http import Response
from geweb.exceptions import HTTPError
from point.util.env import env
from geweb.util import csrf_token
from point.core import PointError
from point.core.user import User
from point.core.post import Post, Comment
#from point.util import timestamp

import settings

class CSRFError(PointError):
    pass

def serialize(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
        #return timestamp(obj)

    if isinstance(obj, (Post, Comment, User)):
        return obj.todict()

    return None

def api(fn):
    def _fn(*args, **kwargs):
        code = 200
        message = "OK"

        env.owner = None

        try:
            resp = fn(*args, **kwargs)

        except HTTPError, e:
            code = e.code
            message = e.message
            resp = {
                "error": e.__class__.__name__,
                "code": code,
                "message": message
            }

        except PointError, e:
            resp = {
                "error": e.__class__.__name__
            }

        if resp is None or resp == '':
            resp = {'ok': True}

        indent = 4 if settings.debug else None
        return Response(json.dumps(resp, indent=indent, default=serialize),
                        code=code, message=message, mimetype="application/json")
    return _fn

def write_api(fn):
    @api
    def _fn(*args, **kwargs):
        token = env.request.args('csrf_token') or env.request.header('X-CSRF')
        if not token or token != csrf_token():
            raise CSRFError
        return fn(*args, **kwargs)
    return _fn

