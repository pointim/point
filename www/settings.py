import os

workers = 8

domain = os.getenv(DOMAIN, 'point.local')

libs = ['/home/point/core/lib']

apps = ['views', 'api']

# redis
cache_socket = 'tcp://redis-cache:6379'
session_socket = 'tcp://redis-sessions:6379'
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

server_host = '0.0.0.0'
server_port = 8088

websocket_host = '0.0.0.0'
websocket_port = 8089
websocket_url = '/ws'
websocket_timeout = 60 #540

elasticsearch_host = '127.0.0.1'
elasticsearch_port = 9200

lang = 'en'
timezone = 'Europe/Moscow'

template_path = '/home/point/www/templates'

avatars_path = '/home/point/img/a'

thumbnail_path = '/home/point/img/t'
thumbnail_size = [400, 300]

media_path = '/home/point/img/m'

blogcss_path = '/home/point/www/static/css/blogcss'

usercss_path = '/home/point/www/static/css/usercss'

imgproc_sock = '/tmp/imgproc.sock'
upload_dir = '/home/point/upload'

session_cookie = 'user'
session_expire = 90 # 90 days
session_backend = 'geweb.session.redis.RedisBackend'
session_prefix = 'geweb-session-'
session_socket = 'tcp://redis-sessions:6379'

middleware = [
    'geweb.session.SessionMiddleware',
    'user.UserMiddleware',
    'point.util.www.DomainOwnerMiddleware'
]

page_limit = 20

actions_interval = 2

edit_expire = 24 * 60 * 60
edit_ratio = 0
edit_distance = 0
edit_comment_expire = edit_expire / 2

user_rename_timeout = 60 * 60 * 24

stoplist_file = '/home/point/core/stoplist.txt'
stoplist_expire = 600 # 10 minutes

doc_path = '/home/point/doc'

proctitle = 'point-www'

logger = 'www'
logfile = None
loglevel = 'info'
logrotate = None
logcount = 7

debug = False

report_mail = 'arts@point.im'
smtp_host = 'smtp.googlemail.com'
smtp_port = 587
smtp_from = 'noreply@point.im'
smtp_auth_required = True
smtp_login = 'noreply@point.im'
smtp_password = os.getenv('SMTP_PASSWORD', '')

secret = os.getenv('SECRET', 'my secret phrase')

recaptcha_public_key = os.getenv('RECAPTCHA_PUBLIC_KEY', '')
recaptcha_private_key = os.getenv('RECAPTCHA_PRIVATE_KEY', '')

cache_markdown = 86400 * 3

cache_expire_max = 86400 * 3

try:
    from settings_local import *
except ImportError:
    pass

try:
    avatars_root
except NameError:
    avatars_root = '://i.%s/a' % domain

try:
    thumbnail_root
except NameError:
    thumbnail_root = '://i.%s/t' % domain

try:
    media_root
except NameError:
    media_root = '://i.%s/m' % domain

try:
    blogcss_root
except NameError:
    blogcss_root = '://%s/blogcss' % domain

try:
    usercss_root
except NameError:
    usercss_root = '://%s/usercss' % domain

