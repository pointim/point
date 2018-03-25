import sys, os
from geweb import log
from point.util.redispool import RedisPool
from point.util.queue import Queue
#from point.core.user import User
from user import ImUser
import geweb.db.pgsql as db
from point.util.template import xmpp_template
import gevent
from gevent import monkey; monkey.patch_all()
from point.util import proctitle
import json
#from base64 import b64encode

import settings

class XMPPSenderQueue(object):
    def __init__(self):
        proctitle('sender-queue')
        log.info('sender queue started with PID=%s' % os.getpid())

        self.xsq = Queue('xsq', settings.queue_socket)

        pool = RedisPool(settings.pubsub_socket)
        pubsub = pool.pubsub()
        pubsub.subscribe(['msg', 'sub', 'rec', 'confirm', 'remember'])

        for msg in pubsub.listen():
            self.xsq.push("%s %s" % (msg['channel'], msg['data']))

class XMPPSender(object):
    def __init__(self):
        proctitle('sender')
        log.info('sender started with PID=%s' % os.getpid())

        self.xsq = Queue('xsq', settings.queue_socket)
        self.xout = Queue('xout', settings.queue_socket)

        while True:
            msg = self.xsq.pop()
            if msg:
                channel, msg = msg.split(' ', 1)
                data = json.loads(msg)
                if isinstance(data, int):
                    continue
                gevent.spawn(self.handle_message, channel, data)

    def handle_message(self, channel, data):
        tmpl = {}

        #if channel == 'msg' and 'author' in data:
            #redis = RedisPool(settings.redis_socket)
            #avatar = redis.get('avatar32.%s' % data['author'])
            #if not avatar:
                #av_path = os.path.join(settings.avatars_path, '32',
                                       #'%s.png' % data['author'])
                #if not os.path.exists(av_path):
                    #av_path = os.path.join(settings.avatars_path, '32.png')

                #avfd = open(av_path)
                #avatar = 'data:image/png;base64,%s' % b64encode(avfd.read())
                #avfd.close()

            #data['avatar'] = avatar

        if channel == 'confirm':
            if 'type' not in data or data['type'] != 'xmpp' or \
                    not 'address' in data or not data['address'].strip():
                return
            body = xmpp_template('confirm_code', settings.lang, None, **data)
            out = {
                'to': data['address'],
                'body': body['body'],
                '_authorize': True
            }
            self.xout.push(json.dumps(out))
            return

        if channel == 'remember':
            body = xmpp_template('remember', settings.lang, None, **data)
            out = {
                'to': data['address'],
                'body': body['body'],
                '_authorize': True
            }
            self.xout.push(json.dumps(out))
            return

        if not isinstance(data['to'], (list, tuple)):
            data['to'] = [data['to']]

        res = db.fetchall("SELECT * FROM users.profile_im "
                          "WHERE id=ANY(%s);", [data['to']])
        profile = {r['id']:dict(r) for r in res}

        for i in data['to']:
            cdata = data.copy()

            user = ImUser.from_data(i, None)
            try:
                jid = user.get_active_account('xmpp')
                if not jid:
                    continue
            except TypeError:
                continue

            if i not in profile:
                profile[i] = user.profile_defaults()
            if profile[i]['off']:
                continue
            lang = user.get_profile('lang')

            cut = None
            if ('type' not in cdata or cdata['type'] != 'feed') and \
                'cut' in data and 'text' in data:
                cut = user.get_profile('im.cut')
                if cut and len(cdata['text']) > cut-3:
                    cdata['text'] = cdata['text'][:cut] + '...'

            if cut:
                ctmpl = xmpp_template("%s_%s"%(channel, cdata['a']),
                                      lang, 'html', **cdata)
            else:
                if not lang in tmpl:
                    tmpl[lang] = xmpp_template("%s_%s"%(channel, cdata['a']),
                                               lang, 'html', **cdata)
                ctmpl = tmpl[lang]

            if profile[i]['xhtml']:
                out = {'to':jid, 'body':ctmpl['body'],
                                 'html':ctmpl['html']}
            else:
                out = {'to':jid, 'body':ctmpl['body']}

            if 'post_id' in cdata and 'comment_id' in cdata:
                out['_msg_id'] = 'post_%s_%s_%s' % (i, cdata['post_id'], cdata['comment_id'])
            elif 'post_id' in cdata:
                out['_msg_id'] = 'post_%s_%s' % (i, cdata['post_id'])

            #if channel == 'msg':
            #    if profile[i]['post_resource']:
            #        out['_resource'] = '#%s' % data['id']
            #    elif profile[i]['user_resource']:
            #        out['_resource'] = '@%s' % data['author']

            self.xout.push(json.dumps(out))

if __name__ == '__main__':
    try:
        sys.path.extend(settings.libs)
    except AttributeError:
        sys.exit(1)

    if len(sys.argv) == 1:
        XMPPSender()
        sys.exit(0)

    for arg in sys.argv:
        if arg == 'sender':
            XMPPSender()
        elif arg == 'queue':
            XMPPSenderQueue()


