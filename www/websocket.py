import sys

import settings

try:
    sys.path.extend(settings.libs)
except AttributeError:
    pass

import gevent
from gevent import monkey; monkey.patch_all()
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource, \
                            WebSocketError
from point.util.redispool import RedisPool
from geweb import log
from Cookie import Cookie
from geweb.session import Session
from point.core.user import User, UserNotFound
from views.filters import markdown_filter

import json

wss = {}

class WsPubsub(object):
    def __init__(self):
        log.info('ws: pubsub init')
        pool = RedisPool(settings.pubsub_socket)
        pubsub = pool.pubsub()
        pubsub.subscribe(['msg', 'msg.self', 'sub', 'rec', 'confirm'])
        for msg in pubsub.listen():
            self.handle_message(msg)

    def handle_message(self, msg):
        global wss
        try:
            data = json.loads(msg['data'])
        except TypeError:
            return

        try:
            to = data['to']
            if not isinstance(to, (list, tuple)):
                to = [to]
            del data['to']
        except KeyError:
            return

        if 'text' in data and data['text']:
            data['html'] = markdown_filter(None, data['text'])

        for uid in to:
            gevent.spawn(send_message, uid, json.dumps(data))

class WsApplication(WebSocketApplication):
    def _auth(self, sessid, ws):
        sess = Session(sessid.strip())
        user = User(sess['id'])

        if user.id not in wss:
            wss[user.id] = []
        wss[user.id].append(ws)

        return user

    def on_open(self):
        global wss
        #for k, v in self.ws.environ.iteritems():
        #    print '>', k, v

        try:
            cookies = Cookie(self.ws.environ['HTTP_COOKIE'])
            sessid = cookies[settings.session_cookie].value
            user = self._auth(sessid, self.ws)
            if user and user.id:
                self.ws.send(json.dumps({'login': user.login}))

        except (KeyError, UserNotFound):
            return

        except WebSocketError:
            pass

    def on_message(self, message):
        if not message:
            return

        global wss

        if message.lower().startswith('authorization:'):
            sessid = message[14:].strip()
            try:
                user = self._auth(sessid, self.ws)
                self.ws.send(json.dumps({'login': user.login}))
            except (KeyError, UserNotFound):
                self.ws.send('NotAuthorized')
                self.ws.close()

            except WebSocketError:
                pass


    def on_close(self, reason):
        print '>> close', reason, self.ws

gevent.spawn(WsPubsub)

def ping_sockets():
    while True:
        gevent.sleep(settings.websocket_timeout)
        for uid in wss:
            gevent.spawn(send_message, uid, 'ping')

def send_message(uid, message):
    try:
        wslist = wss[uid]
    except KeyError:
        return

    dead = []

    for i, ws in enumerate(wslist):
        try:
            ws.send(message)
        except WebSocketError:
            log.debug('WebSocket %s (uid=%s) id dead.' % (ws, uid))
            dead.append(i)

    wss[uid] = [i for j, i in enumerate(wss[uid]) if j not in dead]

gevent.spawn(ping_sockets)

WebSocketServer(
    (settings.websocket_host, settings.websocket_port),
    Resource([(settings.websocket_url, WsApplication)]),
    debug=settings.debug
).serve_forever()

