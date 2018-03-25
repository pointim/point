import os
import time
from geweb import log
from point.util.redispool import RedisPool
import json
import struct
from datetime import datetime
import pytz
from Levenshtein import distance, ratio
from xml.sax.saxutils import escape
from html2text import HTML2Text

try:
    import re2 as re
except ImportError:
    import re

import settings


class Singleton(object):

    def __new__(cls, *args, **kwargs):
        name = "_%s__instance" % cls.__name__
        try:
            result = getattr(cls, name)
        except AttributeError:
            result = (super(Singleton, cls).__new__(cls, *args, **kwargs))
            setattr(cls, name, result)
        return result

    @classmethod
    def get_instance(cls):
        name = "_%s__instance" % cls.__name__
        return getattr(cls, name)


# singleton decorator
# def singleton(cls):
#     instances = {}
#     def getinstance(*args, **kwargs):
#         if cls not in instances:
#             instances[cls] = cls(*args, **kwargs)
#         return instances[cls]
#     return getinstance

def uniqify(array):
    #return dict.fromkeys(array).keys()
    array_out = []
    for a in array:
        if a not in array_out:
            array_out.append(a)
    return array_out

b26chars = "eocapgvqrynhmlsubixdftwzjk"

_ekeys = (69, 75, 89, 91)
_dkeys = (141, 99, 233, 211)

def _encrypt(n):
    packed = struct.pack(">L", n)
    encrypted = ''.join(chr((_ekeys[i] * ord(c)) % 256) for i, c in enumerate(packed))
    return struct.unpack(">L", encrypted)[0]

def _decrypt(n):
    packed = struct.pack(">L", n)
    decrypted = ''.join(chr((_dkeys[i] * ord(c)) % 256) for i, c in enumerate(packed))
    return struct.unpack(">L", decrypted)[0]

def b26(k):
    n = _encrypt(k)
    res = []
    while n > 0:
        n, m = divmod(n, 26)
        res.append(b26chars[m])
    if not res:
        return b26chars[0]
    res.reverse()
    return ''.join(res)

def unb26(s):
    n = 0
    for i, c in enumerate(s[::-1].lower()):
        n += b26chars.index(c)*26**i
    try:
        return _decrypt(n)
    except:
        return 0

def xhtmlim(s):
    s = escape(s).replace('\n', '<br/>')
    return s

def striphtml(s):
    #s = unescape(s).replace('<br/>', '\n')
    #s = re.sub(r'<.+?>', '', s)
    #return s
    h2t = HTML2Text()
    h2t.body_width = 0
    #h2t.ignore_links = True
    h2t.ignore_images = True
    return h2t.handle(s)

def parse_email(address):
    m = re.match(r'^(?P<user>\w|\w[\w.-]*\w)@(?P<domain>(?:(?:\w|\w[\w-]*\w)\.)+(?:\w|\w[\w-]*\w))$', address)
    try:
        return m.groupdict()
    except AttributeError:
        return None

def parse_tags(tags):
    if tags:
        tags = tags.strip(' \r\n\t*')
        if isinstance(tags, str):
            tags = tags.decode('utf-8')
        #tags = re.findall(r'[^\s*]+', tags)
        tags = filter(None,
                [t.replace(u"\xa0", " ").strip()[:64] for t in \
                        uniqify(re.split(r'(?<!\\)[\*,]', tags)[:10])])
        if not tags:
            tags = None

    else:
        tags = []
    return map(lambda t: re.sub(r'\\,', ',', t), tags)

def parse_logins(logins):
    if not logins:
        return None
    return re.findall(r'(?<=@)[a-zA-Z0-9_-]+', logins)

url_regex = re.compile('(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[\w\.\-\+\~%:;]*)*)(?P<qs>\?([^#\s]*))?(?:#(?P<hash>\S+))?')
url_regex_exact = re.compile('^(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[\w\.\-\+\~%:;]*)*)(?P<qs>\?([^#\s]*))?(?:#(?P<hash>\S+))?$')

def parse_url(url, exact=False):
    regex = url_regex_exact if exact else url_regex
    m = re.match(regex, url)
    if m:
        return m.groups()
    return None

date_regex = [
    r'(?P<year>(?:19|20)\d\d)\s*-\s*(?P<month>\d{1,2})\s*-\s*(?P<day>\d{1,2})',
    r'(?P<day>\d{1,2})\s*\.\s*(?P<month>\d{1,2})\s*\.\s*(?P<year>(?:19|20)\d\d)',
    r'(?P<month>\d{1,2})\s*/\s*(?P<day>\d{1,2})\s*/\s*(?P<year>(?:19|20)\d\d)',
]
def parse_date(v):
    if not v:
        return None

    for r in date_regex:
        m = re.match(r, v)
        if m:
            return datetime(int(m.group('year')), int(m.group('month')),
                            int(m.group('day')))

    return 0

def timestamp(d):
    return time.mktime(d.timetuple())

def validate_nickname(s):
    if not s or not (1 < len(s) <= 32):
        return False

    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', s, re.I):
        return False

    return True

def cache_store(key, data, expire=None):
    log.debug('cache_store %s' % key)
    redis = RedisPool(settings.cache_socket)
    redis.set(key, json.dumps(data))
    if not expire:
        try:
            expire = settings.cache_expire_max
        except AttributeError:
            expire = 3600 * 24 # day
    redis.expire(key, expire)

def cache_get(key):
    log.debug('cache_get %s' % key)
    redis = RedisPool(settings.cache_socket)
    data = redis.get(key)
    if data:
        return json.loads(data)

def cache_del(key):
    log.debug('cache_del %s' % key)
    redis = RedisPool(settings.cache_socket)
    redis.delete(key)

date_regex = [
    r'(?P<year>(?:19|20)\d\d)\s*-\s*(?P<month>\d{1,2})\s*-\s*(?P<day>\d{1,2})',
    r'(?P<day>\d{1,2})\s*\.\s*(?P<month>\d{1,2})\s*\.\s*(?P<year>(?:19|20)\d\d)',
    r'(?P<month>\d{1,2})\s*/\s*(?P<day>\d{1,2})\s*/\s*(?P<year>(?:19|20)\d\d)',
]
def parse_date(v):
    if not v:
        return None

    for r in date_regex:
        m = re.match(r, v)
        if m:
            return datetime(int(m.group('year')), int(m.group('month')),
                            int(m.group('day')))

    return 0

def diff_ratio(str1, str2):
    if not isinstance(str1, unicode):
        str1 = str1.decode('utf-8')
    str1 = ' '.join(re.split(r'[\s\.]+', str1)).lower()
    if not isinstance(str2, unicode):
        str2 = str2.decode('utf-8')
    str2 = ' '.join(re.split(r'[\s\.]+', str2)).lower()

    d = distance(str1, str2)
    if d <= 1:
        return True

    if settings.edit_distance > 0 and d > settings.edit_distance:
        return False

    r = ratio(str1, str2)
    if r < settings.edit_ratio:
        return False

    return True

_tzlist = {}
def tzlist():
    if _tzlist:
        return _tzlist
    for tz in pytz.common_timezones:
        try:
            reg, sub = tz.split('/', 1)
        except ValueError:
            reg, sub = '', tz
        if reg not in _tzlist:
            _tzlist[reg] = []
        _tzlist[reg].append(sub)
    return _tzlist

def check_tz(tz):
    try:
        reg, sub = tz.split('/', 1)
    except ValueError:
        reg, sub = '', tz

    if not _tzlist:
        tzlist()
    if reg not in _tzlist:
        return False
    if sub not in _tzlist[reg]:
        return False
    return True

def proctitle(title=None):
    try:
        prefix = settings.proctitle_prefix
    except AttributeError:
        prefix = None
    if not title and not prefix:
        raise ValueError('Process title is not set')

    from setproctitle import setproctitle
    if prefix and title:
        setproctitle('%s-%s' % (prefix, title))
    elif prefix:
        setproctitle(prefix)
    elif title:
        setproctitle(title)

