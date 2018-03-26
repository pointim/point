import os

workers = 8
senders = 8

libs = ['/home/point/core/lib']

# redis
cache_socket = 'tcp://redis-cache-xmpp:6379'
storage_socket = 'tcp://redis-storage:6379'
pubsub_socket = 'tcp://redis-pubsub:6379'
queue_socket = 'tcp://redis-queue:6379'
imgproc_socket = 'tcp://redis-imgproc:6379'

queue_timeout = 5

feed_fetch_timeout = 30

feed_queue_socket = 'unix:///var/run/redis/feed.sock'
feed_queue_timeout = 5

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

domain = os.getenv('DOMAIN', 'point.local')

xmpp_host = os.getenv('XMPP_HOST', 'prosody')
xmpp_port = int(os.getenv('XMPP_PORT', '5222'))
xmpp_jid = os.getenv('XMPP_BOT_JID', 'p@point.local')
xmpp_password = os.getenv('XMPP_BOT_PASSWORD', '123')
xmpp_resource = 'point'

template_path = '/home/point/xmpp/templates'
avatars_path = '/home/point/img/a'

media_path = '/home/point/img/m'

lang = 'en'
timezone = 'Europe/Moscow'

session_expire = 1800

# Web sessions
session_backend = 'geweb.session.redis.RedisBackend'
session_prefix = 'geweb-session-'
session_socket = storage_socket

sphinx_host = 'localhost'
sphinx_port = 9312

login_key_expire = 3600

actions_interval = 2

edit_expire = 24 * 60 * 60
edit_ratio = 0
edit_distance = 0
edit_comment_expire = edit_expire / 2

page_limit = 20

stoplist_file = '/home/point/core/stoplist.txt'
stoplist_expire = 600 # 10 minutes

logger = 'xmpp'
logformat = u'%(asctime)s %(process)d %(filename)s:%(lineno)d:%(funcName)s %(levelname)s  %(message)s'
logfile = None
loglevel = 'info'
logrotate = None
logcount = 7

debug = False

proctitle_prefix = 'point'

secret = os.getenv('SECRET', 'my secret phrase')

cache_markdown = True

cache_expire_max = 86400

try:
    from settings_local import *
except ImportError:
    pass

try:
    media_root
except NameError:
    media_root = '://i.%s/m' % domain
