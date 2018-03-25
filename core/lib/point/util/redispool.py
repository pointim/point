import gevent
from redis.client import Redis
import hashlib
import json

import settings

class RedisPool(Redis):
    __instances = {}
    def __new__(cls, *args, **kwargs):
        k = str(args)+str(kwargs)
        if k not in cls.__instances:
            cls.__instances[k] = Redis.__new__(cls, *args, **kwargs)
        return cls.__instances[k]

    def __init__(self, addr):
        if not addr:
            raise ValueError('Invalid redis address')
        if addr.startswith('unix://'):
            cargs = {'unix_socket_path':addr.replace('unix://', '')}
        elif addr.startswith('tcp://'):
            h = addr.replace('tcp://', '').split(':')
            cargs = {'host': h[0]}
            if len(h) == 2:
                cargs['port'] = int(h[1])
        else:
            raise ValueError('Invalid redis address')
        Redis.__init__(self, **cargs)

# caching decorator
def cache(fn):
    def _cache_fn(*args, **kwargs):
        pool = RedisPool(settings.cache_socket)
        try:
            c = kwargs['_cache']
            del kwargs['_cache']
        except KeyError:
            c = None
        if not c:
            return fn(*args, **kwargs)

        try:
            key = kwargs['_key']
            del kwargs['_key']
        except KeyError:
            key = 'cache.'+hashlib.md5(str(args)+str(kwargs)).hexdigest()

        res = pool.get(key)
        if res:
            return json.loads(res)

        res = fn(*args, **kwargs)

        if res:
            pool.set(key, json.dumps(res))
            pool.expire(key, c)
        return res
    return _cache_fn

def del_cache(key):
    pool = RedisPool(settings.cache_socket)
    pool.delete(key)

def publish(channel, data):
    pool = RedisPool(settings.pubsub_socket)
    pool.publish(channel, json.dumps(data))

