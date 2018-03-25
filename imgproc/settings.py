import os

workers = 4

libs = ['/home/point/core/lib']

domain = os.getenv(DOMAIN, 'point.local')

cache_socket = 'tcp://redis-cache:6379'
imgproc_socket = 'tcp://redis-imgproc:6379'

queue_timeout = 5

cache_expire_max = 86400

avatars_path = '/home/point/img/a'
avatar_sizes = [24, 40, 80, 280]

thumbnail_path = '/home/point/img/t'
thumbnail_size = [400, 300]

media_path = '/home/point/img/m'
media_size = [1920, 1080]

max_image_size = 6000 * 6000

upload_dir = '/home/point/upload'

proctitle_prefix = 'point'

logger = 'imgproc'
logfile = None
loglevel = 'info'

debug = False

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

