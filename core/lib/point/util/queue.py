#from redis import Redis

import json

from geweb import log
from point.util.redispool import RedisPool

import settings

class Queue(object):
    def __init__(self, _id, addr=None, blocking=True, channels=True):
        self._id = _id
        self.queue = RedisPool(addr)
        self.blocking = blocking
        self.channels = channels

        log.debug('queue %s connected using %s' % (_id, addr))

    def pop(self):
        if self.blocking:
            data = self.queue.brpop(self._id, settings.queue_timeout)
        else:
            data = self.queue.rpop(self._id)
        if not data:
            return None
        try:
            if self.channels:
                data = data[1]
            log.debug('POP %s: %s' % (self._id, data))
            return json.loads(data)
        except ValueError:
            return None

    def push(self, data):
        log.debug('PUSH %s: %s' % (self._id, json.dumps(data)))
        self.queue.lpush(self._id, json.dumps(data))

