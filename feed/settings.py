workers = 8

libs = ['/home/point/point/lib']

# redis
cache_socket = 'tcp://127.0.0.1:16380'
storage_socket = 'unix:///var/run/redis/storage.sock'
pubsub_socket = 'unix:///var/run/redis/pubsub.sock'
queue_socket = 'unix:///var/run/redis/queue.sock'
queue_timeout = 5

feed_fetch_timeout = 30

feed_queue_socket = 'unix:///var/run/redis/feed.sock'
feed_queue_timeout = 5

feed_queue_update_timeout = 5

feed_min_update_timeout = 60
feed_max_update_timeout = 43140

feed_retries = 5
feed_retry_timeout = 60

db = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'point',
    'user': 'point',
    'password': '',
    'maxsize': 10
}

domain = 'point.im'

lang = 'en'
timezone = 'Europe/Moscow'

session_expire = 1800

thumbnail_path = '/home/point/point/www/static/img/t'
thumbnail_root = '://i.point.im/t'
thumbnail_size = [400, 300]

logger = 'feed'
logformat = u'%(asctime)s %(process)d %(filename)s:%(lineno)d:%(funcName)s %(levelname)s  %(message)s'
logfile = '/home/point/log/feed.log'
loglevel = 'error'
logrotate = None
logcount = 7

debug = False

proctitle_prefix = 'point'

secret = 'my secret phrase'

try:
    from settings_local import *
except ImportError:
    pass

