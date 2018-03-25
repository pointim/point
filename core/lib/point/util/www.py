import geweb.db.pgsql as db
from point.util.env import env
from point.core.user import User, UserNotFound, NotAuthorized
from geweb.http import Response
from geweb.exceptions import Forbidden
from geweb.middleware import Middleware
from geweb.template import render_string

from geweb.exceptions import Forbidden, NotFound
from point.core.post import PostAuthorError, PostLimitError, \
                            PostNotFound, CommentNotFound, PostReadonlyError, \
                            CommentEditingForbiddenError
from point.core.user import SubscribeError, UserNotFound, NotAuthorized, \
                            AlreadyAuthorized
import settings
import geweb.log as log
import traceback


try:
    import re2 as re
except ImportError:
    import re

import settings

def domain_owner(domain):
    if domain == settings.domain:
        return User.from_data(None, None)

    if domain.endswith(settings.domain):
        return User('login', domain[0:domain.find(settings.domain)-1])

    res = db.fetchone("SELECT id FROM users.domains WHERE domain=%s;",
                     [domain]) #, _cache=600)
    if res:
        return User(res[0])

    raise UserNotFound

def domain(user):
    if not user.id:
        raise NotAuthorized

    res = db.fetchone("SELECT domain FROM users.domains WHERE id=%s;",
                     [user.id]) #, _cache=600)
    if res:
        return res[0]
    else:
        return '%s.%s' % (user.login, settings.domain)

urlre = re.compile('^(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?P<port>::(\d+))?(?P<path>(?:/[\w\.\-%]*)*)(?:\?(?P<query>[^#]*))?')
def parse_url(url):
    if not url:
        return None
    m = re.search(urlre, url)
    if m:
        return m.groupdict()

def check_referer(fn):
    def _fn(*args, **kwargs):
        referer = parse_url(env.request.referer)
        if not referer or not referer['host'].endswith(settings.domain):
            raise Forbidden
        return fn(*args, **kwargs)
    return _fn

def redirect_anonymous(fn):
    def _fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotAuthorized:
            return Response(redirect='%s://%s/' % \
                            (env.request.protocol, settings.domain))
    return _fn

def get_referer():
    try:
        referer = env.request.args('referer')
    except KeyError:
        referer = env.request.referer
    if not referer:
        referer = '%s://%s/' % (env.request.protocol, settings.domain)
    return referer

class DomainOwnerMiddleware(Middleware):
    def process_request(self, request):
        try:
            env.owner = domain_owner(request.host)
        except UserNotFound:
            env.owner = None

def catch_errors(fn):
    def _fn(*args, **kwargs):
        try:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if settings.debug:
                    log.error(traceback.format_exc())
                raise e
        except UserNotFound:
            body = render_string('/user-not-found.html')
            return Response(body, code=NotFound.code, message=NotFound.message)
        except PostAuthorError:
            body = render_string('/blog-denied.html')
            return Response(body, code=Forbidden.code, message=Forbidden.message)
        except SubscribeError:
            body = render_string('/post-denied.html')
            return Response(body, code=Forbidden.code, message=Forbidden.message)
        except PostReadonlyError:
            body = render_string('/post-readonly.html')
            return Response(body, code=Forbidden.code, message=Forbidden.message)
        except PostNotFound:
            body = render_string('/post-not-found.html')
            return Response(body, code=NotFound.code, message=NotFound.message)
        except CommentNotFound:
            body = render_string('/comment-not-found.html')
            return Response(body, code=NotFound.code, message=NotFound.message)
        except CommentEditingForbiddenError:
            body = render_string('/comment-past-editing.html')
            return Response(body, code=Forbidden.code, message=Forbidden.message)
        except NotAuthorized:
            raise Forbidden
        except AlreadyAuthorized:
            raise Forbidden
        except PostLimitError:
            body = render_string('/post-interval-exceeded.html')
            return Response(body, code=Forbidden.code, message=Forbidden.message)
    return _fn


