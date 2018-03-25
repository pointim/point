from point.util.queue import Queue
#from geweb import log
from point.util.env import env
from hashlib import md5
from urllib import quote_plus

try:
    import re2 as re
except ImportError:
    import re

import settings

# utilities

def make_avatar(path, filename, remove=True, old=None):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'avatar',
        'path': path, 'filename': filename, 'remove': remove, 'old': old})

def move_avatar(old, new):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'move_avatar', 'old': old, 'new': new})

def remove_avatar(filename):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'remove_avatar', 'filename': filename})

def make_attach(path, dest, filename, remove=True):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'attach',
                 'path': path, 'dest': dest, 'filename': filename,
                'remove': remove})

def remove_attach(filename):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'remove_attach', 'filename': filename})

def make_thumbnail(url):
    queue = Queue('imgq', settings.imgproc_socket)
    queue.push({'fn': 'thumbnail', 'url': url})

def imgproc_url(url):
    if isinstance(url, unicode):
        url = url.encode('utf-8')
    h = md5(re.sub('"', '%22', url)).hexdigest()
    return 'https%s/%s/%s?u=%s' % (settings.thumbnail_root, h[:2], h,
                                quote_plus(url))

