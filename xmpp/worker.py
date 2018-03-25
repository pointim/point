"""
XMPP worker
"""
import settings

import sys
#sys.path.append(settings.core_path)

import os

import gevent
from gevent import monkey; monkey.patch_all()
import json

from geweb import log
from point.util.queue import Queue
from point.util.env import env
from point.util.template import xmpp_template
from point.util import proctitle
from point.util.antispam import check_stoplist

from point.core.user import NotAuthorized
from user import ImUser, SessionCallError
from point.core import PointError
from point.app import posts

from route import route

try:
    import re2 as re
except ImportError:
    import re

def prepare_route(route):
    for r in route:
        r['resource'] = re.compile(r['resource'], re.I|re.S)
        for rr in r['route']:
            rr[0] = re.compile(rr[0], re.I|re.S)
    return route

class XMPPWorker(object):
    """XMPPWorker class"""
    def __init__(self):
        proctitle('worker')
        log.info('worker started with PID=%s' % os.getpid())

        self.route = prepare_route(route)

        self.qin = Queue('xin', settings.queue_socket)
        self.qout = Queue('xout', settings.queue_socket)

        while True:
            data = self.qin.pop()
            if data:
                try:
                    data = json.loads(data)
                    data_type = data.get('type', 'msg')
                    if data_type == 'msg':
                        method = self.handle_message
                    elif data_type == 'tune':
                        method = self.handle_tune
                    gevent.spawn(method, data)
                except ValueError, err:
                    log.error("%s: %s" % (err.__class__.__name__, err.message))
            #else:
            #    gevent.sleep(seconds=0.1)

    def handle_message(self, msg):
        """Handle message
        """

        if 'presence' in msg:
            pass

        if 'body' in msg and check_stoplist(msg['body']):
            return

        try:
            jid, resource = msg['from'].split('/', 1)
        except ValueError:
            jid = msg['from']
            resource = None

        env.user = ImUser('xmpp', jid)
        env.jid = jid
        env.resource = resource

        try:
            if 'receipt' in msg and msg['receipt']:
                try:
                    uid, post_id, comment_id = msg['receipt'].split('_')
                    posts.clear_unread_comments(post_id, int(comment_id))
                    return
                except ValueError:
                    try:
                        uid, post_id = msg['receipt'].split('_')
                        posts.clear_unread_posts(post_id)
                        return
                    except ValueError:
                        pass
        except NotAuthorized:
            pass

        if env.user.get_profile('im.auto_switch'):
            bare_from = msg['from'].split('/', 1)[0]
            env.user.set_active_account('xmpp', bare_from)

        def _route(user, jid, msg):
            session = env.user.session()
            try:
                return session(msg['body'])
            except SessionCallError:
                pass

            message = env.user.resolve_aliases(msg['body'])

            args = {}
            for r in self.route:
                m = re.search(r['resource'], msg['resource'])
                if m:
                    args = m.groupdict()
                    route = r['route']
                    break

            for regex, view in route:
                match = re.search(regex, message)
                if match:
                    for g, val in match.groupdict().iteritems():
                        args[g] = val
                    log.debug(">>> %s routed to %s(%s) via '%s'" % \
                              (jid, view.__name__, str(args), regex.pattern))
                    return view(**args)

        _presence = False

        try:
            reply = _route(env.user, jid, msg)
            if 'body' in reply and reply['body']:
                reply['body'] = re.sub(r'&#(\d+);',
                                       lambda c: chr(int(c.group(1))),
                                       reply['body'])
                reply['body'] = u''.join([ c if c == '\n' or ord(c) > 16 else ' ' \
                                           for c  in reply['body'] ])

            if '_presence' in reply and reply['_presence']:
                _presence = True

            if isinstance(reply, (str, unicode)):
                reply = {'body': reply}
        except NotAuthorized:
            reply = xmpp_template('user_not_authorized')
        except PointError, e:
            reply = {'body':"%s: %s" % (e.__class__.__name__, e.message)}

        if env.user.get_profile('xhtml') and 'html' in reply:
            out = {'to':msg['from'], 'html':reply['html'],
                                     'body':reply['body']}
        else:
            out = {'to':msg['from'], 'body':reply['body']}
        if _presence:
            out['_presence'] = True
        self.qout.push(json.dumps(out))
        return

    def handle_tune(self, data):
        user = ImUser('xmpp', data['from'])
        user.update_tune_data(data['tune'])

if __name__ == '__main__':
    XMPPWorker()

