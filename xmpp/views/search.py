from point.core.user import UserNotFound
from point.app import search
from point.util import parse_tags
from point.util.template import xmpp_template

def search_posts(login=None, taglist=None, text=None, offset=None, limit=None):
    taglist = parse_tags(taglist)
    if text:
        text = text.strip()

    offset = int(offset) if offset else 0
    limit = int(limit) if limit else 10

    results, has_next, total = search.search_posts(text,
                                         offset=offset, limit=limit)

    return xmpp_template('search', text=text, results=results, has_next=has_next,
                         limit=limit, offset=offset, total=total)

