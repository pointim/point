from geweb import log
from point.util import cache_get, cache_store

try:
    import re2 as re
except ImportError:
    import re

import settings

def check_stoplist(text):
    slist = cache_get('stoplist')
    if not slist:
        slist = load_stoplist()
    for s in slist:
        if re.search(s, text, re.I):
            return True
    return False

def load_stoplist():
    fd = open(settings.stoplist_file)
    slist = [s.strip().decode('utf-8') for s in fd]
    fd.close()
    cache_store('stoplist', slist, settings.stoplist_expire)
    return slist

