workers = 1

cache_socket = 'tcp://127.0.0.1:6379'
storage_socket = 'tcp://127.0.0.1:6379'
pubsub_socket = 'tcp://127.0.0.1:6379'
queue_socket = 'tcp://127.0.0.1:6379'
imgproc_socket = 'tcp://127.0.0.1:6379'

feed_queue_socket = 'tcp://127.0.0.1:6379'

db = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'point',
    'user': 'point',
    'password': '${POINT_DB_PASSWORD}',
    'maxsize': 10
}

domain = '${POINT_DOMAIN}'
loglevel = 'debug'
debug = True

avatars_root = '://i.${POINT_DOMAIN}/a'
thumbnail_root = '://i.${POINT_DOMAIN}/t'
media_root = '://i.${POINT_DOMAIN}/m'
blogcss_root = '://${POINT_DOMAIN}/blogcss'
usercss_root = '://${POINT_DOMAIN}/usercss'

imgproc_sock = 'tcp://127.0.0.1:6379'
session_socket = 'tcp://127.0.0.1:6379'

recaptcha_public_key = '${RECAPTCHA_PUBLIC_KEY}'
recaptcha_private_key = '${RECAPTCHA_PRIVATE_KEY}'
