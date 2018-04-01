import os

libs = ['/home/point/core/lib']

feed_min_update_timeout = 60
feed_max_update_timeout = 86340

db = {
    'host': 'db',
    'port': 5432,
    'database': 'point',
    'user': 'point',
    'password': 'point',
    'maxsize': 10
}

period = 30

stat_path = '/home/point/stat/stat'

lang = 'en'
timezone = 'Europe/Moscow'

logger = 'stat'
logformat = u'%(asctime)s %(process)d %(filename)s:%(lineno)d:%(funcName)s %(levelname)s  %(message)s'
logfile = None
loglevel = 'error'
logrotate = None
logcount = 7

debug = False

try:
    from settings_local import *
except ImportError:
    pass

