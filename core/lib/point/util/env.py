import gevent

import settings

class Env(object):
    def __setattr__(self, attr, value):
        g = gevent.getcurrent()
        g.__dict__[attr] = value

    def __getattr__(self, attr):
        g = gevent.getcurrent()
        return g.__dict__[attr]

env = Env()

