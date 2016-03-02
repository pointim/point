workers = 1
senders = 1

cache_socket = 'tcp://127.0.0.1:6379'
storage_socket = 'tcp://127.0.0.1:6379'
pubsub_socket = 'tcp://127.0.0.1:6379'
queue_socket = 'tcp://127.0.0.1:6379'
imgproc_socket = 'tcp://127.0.0.1:6379'
feed_queue_socket =  'tcp://127.0.0.1:6379'

domain = '${POINT_DOMAIN}'

xmpp_jid = 'p@${POINT_DOMAIN}'
xmpp_password = '${POINT_BOT_PASSWORD}'

loglevel = 'debug'
debug = True

media_root = '://i.${POINT_DOMAIN}/m'
