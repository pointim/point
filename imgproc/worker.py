# -*- coding: utf-8 -*-

import traceback
import os
import shutil
import urllib2
import magic
import Image
from PIL.ExifTags import TAGS
from cStringIO import StringIO
from hashlib import md5
from random import randint
from point.util.queue import Queue
from geweb import log
from point.util import proctitle, cache_get, cache_store, cache_del

import settings

_ROTATE = {
    3: 180,
    6: -90,
    8: 90
}

def _rotate(img):
    try:
        exif = {
            TAGS[k]: v
            for k, v in img._getexif().items()
            if k in TAGS
        }
    except AttributeError:
        return img

    try:
        img = img.rotate(_ROTATE[exif['Orientation']])
    except KeyError:
        return img

    return img

class ImgprocWorker(object):
    proctitle('imgproc-worker')
    def __init__(self):
        self.queue = Queue('imgq', settings.imgproc_socket)

        log.info('imgproc worker started')

        while True:
            data = self.queue.pop()
            if data and isinstance(data, dict):
                fn = data['fn']
                del data['fn']
                try:
                    handlers[fn](**data)
                except Exception:
                    log.error(traceback.format_exc())

# handlers

def avatar(path, filename, remove=True, old=None):
    if old:
        remove_avatar(old)
    if isinstance(path, str):
        path = path.decode('utf-8')
    if isinstance(filename, str):
        filename = filename.decode('utf-8')
    log.info('Making avatars %s %s' % (path, filename))

    if path.startswith('http://') or path.startswith('https://'):
        try:
            resp = urllib2.urlopen(path)
            tmp_path = os.path.join(settings.upload_dir,
                                    "%s.%s" % (filename, randint(1000, 9999)))
            fd = open(tmp_path, 'w')
            fd.write(resp.read())
            fd.close()

            resp.close()

            path = tmp_path

        except (urllib2.URLError, OSError), e:
            return {'status': 'fail', 'message': e.msg}

    source = Image.open(path)
    if source.size[0] * source.size[1] > settings.max_image_size:
        log.error('too big: %sx%s %s' % (source.size[0], source.size[1], path))
        return

    if source.format == 'GIF':
        source.seek(0)
    log.debug('%s opened: %s' % (path, source))

    w, h = source.size

    if w > h:
        box = ((w-h)/2, 0, (w+h)/2, h)
    elif w < h:
        box = (0, (h-w)/2, w, (h+w)/2)
    else:
        box = None

    if box:
        crop = source.crop(box)
    else:
        crop = source

    for s in settings.avatar_sizes:
        img = crop.resize((s, s), Image.ANTIALIAS)
        img.save(os.path.join(settings.avatars_path, str(s), filename),
                 source.format, **source.info)
        log.debug('Save %s (%d)' % (filename, s))

    if remove:
        try:
            os.remove(path)
        except OSError:
            pass

def move_avatar(old, new):
    for s in settings.avatar_sizes:
        os.rename(os.path.join(settings.avatars_path, str(s), old),
                  os.path.join(settings.avatars_path, str(s), new))

def remove_avatar(filename):
    for s in settings.avatar_sizes:
        try:
            os.remove(os.path.join(settings.avatars_path, str(s), filename))
        except OSError:
            pass

def thumbnail(url):
    log.debug('- URL %s %s' % (type(url), url))
    hash = md5(url).hexdigest()
    dirname = os.path.join(settings.thumbnail_path, hash[:2])
    path = os.path.join(dirname, hash)
    if os.path.isfile(path) and os.stat(path) > 0:
        log.debug('%s: thumbnail exists' % path)
        return
    log.info('Making thumbnail %s %s' % (path, url))

    if cache_get('thumbnail:%s' % hash):
        return

    cache_store('thumbnail:%s' % hash, 1, 60)

    try:
        try:
            os.mkdir(dirname)
        except OSError, e:
            if e.errno == 17:
                log.debug('OSError %s: %s %s' % (e.errno, e.strerror, dirname))
            else:
                log.warn('OSError %s: %s %s' % (e.errno, e.strerror, dirname))

        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        resp = opener.open(url)
        #resp = urllib2.urlopen(url)
        buf = StringIO(resp.read())
        img = Image.open(buf)
        if img.size[0] * img.size[1] > settings.max_image_size:
            log.error('too big: %sx%s %s' % (img.size[0], img.size[1], url))
            return

        img.load()

        fmt = img.format

        if fmt == 'JPEG':
            img = _rotate(img)

        elif fmt == 'GIF':
            img.seek(0)
            #img = img.copy()

        img.thumbnail(settings.thumbnail_size, Image.ANTIALIAS)
        img.save(path, fmt, **img.info)

    #except IOError, e:
    #    log.error('IOError %s' % str(e))
    #    fd = open(path, 'w')
    #    fd.close()
    except urllib2.HTTPError, e:
        log.warn('HTTPError %s: %s' % (e.code, url))
        fd = open(path, 'w')
        fd.close()
    except urllib2.URLError, e:
        log.warn('URLError %s: %s' % (e.reason, url))
    except Exception, e:
        log.error(traceback.format_exc())
    finally:
        cache_del('thumbnail:%s' % hash)

def _attach_image(src, dest, filename):
    def thumb(name, size, orig=False):
        fd = open(src)
        img = Image.open(fd)

        if img.size[0] * img.size[1] > settings.max_image_size:
            log.error('too big: %sx%s %s' % (img.size[0], img.size[1], src))
            return

        img.load()

        fmt = img.format

        if fmt == 'JPEG':
            img = _rotate(img)

        elif fmt == 'GIF':
            img.seek(0)

        if orig:
            (w, h) = img.size
            if w <= settings.media_size[0] and h <= settings.media_size[1]:
                shutil.copyfile(src, os.path.join(dest, name))
                return

        img.thumbnail(size, Image.ANTIALIAS)
        img.save(os.path.join(dest, name), fmt, **img.info)

    thumb(filename, settings.media_size, orig=True)
    thumb('%s.thumb' % filename, settings.thumbnail_size)

mime = magic.Magic(flags=magic.MAGIC_MIME_TYPE)

def attach(path, dest, filename, remove=True):
    if isinstance(path, str):
        path = path.decode('utf-8')
    if isinstance(dest, str):
        dest = dest.decode('utf-8')
    if isinstance(filename, str):
        filename = filename.decode('utf-8')

    dirname = os.path.join(settings.media_path, dest)
    error = False
    try:
        os.makedirs(dirname)
    except OSError, e:
        if e.errno == 17:
            log.debug('OSError %s: %s %s' % (e.errno, e.strerror, dirname))
        else:
            log.warn('OSError %s: %s %s' % (e.errno, e.strerror, dirname))
            error = True

    if not error:
        filetype = mime.id_filename(path)

        if filetype.startswith('image/'):
            _attach_image(path, dirname, filename)
        else:
            if remove:
                os.rename(path, os.path.join(dirname, filename))
            else:
                shutil.copyfile(path, os.path.join(dirname, filename))
            return

    if remove:
        try:
            os.remove(path)
        except OSError:
            pass

def remove_attach(filename):
    if isinstance(filename, str):
        filename = filename.decode('utf-8')
    os.remove(os.path.join(settings.media_path, filename))
    os.remove(os.path.join(settings.media_path, "%s.thumb" % filename))

handlers = {
    'avatar': avatar,
    'move_avatar': move_avatar,
    'remove_avatar': remove_avatar,
    'thumbnail': thumbnail,
    'attach': attach,
    'remove_attach': remove_attach
}

if __name__ == '__main__':
    ImgprocWorker()

