import settings

import sys
#sys.path.append(settings.core_path)

import os
import re
import socket

from gevent import monkey; monkey.patch_all()
from gevent import spawn, spawn_later

from geweb import log
from point.util.queue import Queue
from point.util import proctitle
from point.util import cache_get, cache_store, cache_del
import json
import sleekxmpp
from sleekxmpp.xmlstream.jid import JID
from pprint import pprint

#register_stanza_plugin(Message, RequestPlugin)

TAG_NAME_RE = re.compile(r'(?:\{.+\})?(?P<name>.+)$')

def tag_name_without_ns(element):
    match = TAG_NAME_RE.match(element.tag)
    return match.group('name')


class XMPPBot(sleekxmpp.ClientXMPP):
    def __init__(self):
        proctitle('bot')
        log.info('bot started with PID=%d' % os.getpid())

        self._jid = "%s/%s" % (settings.xmpp_jid, settings.xmpp_resource)
        sleekxmpp.ClientXMPP.__init__(self, self._jid, settings.xmpp_password)

        self.register_plugin('xep_0184')
        self.register_plugin('xep_0163')
        self.plugin['xep_0163'].add_interest('http://jabber.org/protocol/tune')
        self.plugin['xep_0060'].map_node_event('http://jabber.org/protocol/tune', 'user_tune')

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.handle_message)
        self.add_event_handler("presence_subscribed", self.handle_subscription)
        self.add_event_handler("user_tune_publish", self.handle_tune)
        self.add_event_handler("got_offline", self.handle_disconnection)

        self.add_event_handler("receipt_received", self.handle_receipt)

        self.xin = Queue('xin', addr=settings.queue_socket)
        self.xout = Queue('xout', addr=settings.queue_socket)

        self.auto_authorize = True
        self.auto_subscribe = True

        spawn(self.listen_queue)

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

    def handle_subscription(self, presence):
        key = 'presence:%s:%s' % (presence['type'], presence['from'].bare)
        data = cache_get(key)
        if data:
            cache_del(key)
            self.send_message(**data)

    def handle_receipt(self, msg):
        if msg['receipt']:
            receipt = msg['receipt']
        elif msg['id']:
            receipt = msg['id']
        if receipt and receipt.startswith('post_'):
            self.xin.push(json.dumps({'from': str(msg['from']),
                                      'receipt': receipt[5:]}))

    def handle_message(self, msg):
        if msg['type'] in ('chat', 'normal'):
            if msg['id'] and msg['id'].startswith('post_'):
                _msg_id = msg['id'].strip()
                self.xin.push(json.dumps({'from': str(msg['from']),
                                          'id': _msg_id}))

            try:
                jid, resource = str(msg['to']).split('/', 1)
            except ValueError:
                jid = settings.xmpp_jid
                resource = settings.xmpp_resource
            self.xin.push(json.dumps({'from': str(msg['from']),
                                      'resource': resource,
                                      'body': msg['body'].strip()}))

    def handle_tune(self, msg):
        tune = msg['pubsub_event']['items']['item']['payload']
        tune_data = { tag_name_without_ns(el):el.text for el in tune.getchildren() }
        self.xin.push(json.dumps({'type': 'tune', 'from': str(msg['from']), 'tune': tune_data}))

    def handle_disconnection(self, presence):
        try:
            jid, resource = str(presence['from']).split('/', 1)
        except ValueError:
            jid = str(presence['from'])
        self.xin.push(json.dumps({'type': 'tune', 'from': jid, 'tune': {}}))

    def listen_queue(self):
        try:
            data = self.xout.pop()
            if data:
                data = json.loads(data)
        except Exception, e:
            log.error('%s %s %s' % (e.__class__.__name__, e.message,
                                    type(data), data))
            data = None
        if not data:
            spawn_later(0.05, self.listen_queue)
            return

        try:
            html = None
            if 'html' in data and data['html']:
                html = sleekxmpp.xmlstream.ET.XML('<div style="margin-top:0">%s</div>' % data['html'])
                    #'<html xmlns="http://jabber.org/protocol/xhtml-im">' + \
                    #'<body xmlns="http://www.w3.org/1999/xhtml">%s</body></html>'
            if '_resource' in data and data['_resource']:
                mfrom = '%s/%s' % (settings.xmpp_jid, data['_resource'])
            else:
                mfrom = self._jid

            if self.check_subscription(data['to']):
                if '_presence' in data and data['_presence']:
                    pstatus = data['_presence'] \
                                if isinstance(data['_presence'], (str, unicode)) \
                                else "I'm online"
                    self.send_presence(pto=data['to'], pstatus=pstatus)

                mid = data['_msg_id'] if '_msg_id' in data else None

                self.send_message(mfrom=mfrom, mto=data['to'], mtype='chat',
                                  mid=mid, mbody=data['body'], mhtml=html)
            elif '_authorize' in data and data['_authorize']:
                # TODO: request subscription
                self.sendPresenceSubscription(pto=data['to'])
                cache_store('presence:subscribed:%s' % JID(data['to']).bare,
                            {'mfrom': mfrom, 'mto': data['to'], 'mtype': 'chat',
                             'mbody': data['body'], 'mhtml': html},
                            3600 * 24 * 7)
        finally:
            spawn(self.listen_queue)

    def send_message(self, mto, mbody, msubject=None, mtype=None, mid=None,
                     mhtml=None, mfrom=None, mnick=None):
        msg = self.makeMessage(mto, mbody, msubject, mtype, mhtml, mfrom, mnick)
        if mid:
            msg['id'] = mid
            msg['request_receipt'] = True
        msg.send()

    def check_subscription(self, jid):
        try:
            return self.roster[settings.xmpp_jid][JID(jid).bare]['subscription'] == 'both'
        except KeyError:
            return False

if __name__ == '__main__':
    host = socket.gethostbyname(settings.xmpp_host)
    bot = XMPPBot()
    bot.connect(address=(host, settings.xmpp_port))
    bot.process(block=False)

