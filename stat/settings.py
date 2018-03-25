libs = ['/home/point/core/lib']

cache_socket = 'unix:///var/run/redis/cache.sock'
storage_socket = 'unix:///var/run/redis/storage.sock'
pubsub_socket = 'unix:///var/run/redis/pubsub.sock'
queue_socket = 'unix:///var/run/redis/queue.sock'

feed_queue_socket = 'unix:///var/run/redis/feed.sock'

feed_min_update_timeout = 60
feed_max_update_timeout = 86340

db = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'point',
    'user': 'point',
    'password': 'point',
    'maxsize': 10
}

domain = 'point.im'

period = 30

stat_path = '/home/point/www/static/files/stat'
images_path = '/home/point/www/static/img/stat'

lang = 'en'
timezone = 'Europe/Moscow'

logger = 'stat'
logformat = u'%(asctime)s %(process)d %(filename)s:%(lineno)d:%(funcName)s %(levelname)s  %(message)s'
logfile = '/home/point/log/stat.log'
loglevel = 'error'
logrotate = None
logcount = 7

debug = False

try:
    from settings_local import *
except ImportError:
    pass

