from point.app import tags
from point.core.user import UserNotFound, SubscribeError
from point.util import parse_tags
from point.util.template import xmpp_template

def subscribe(taglist, login=None):
    taglist = parse_tags(taglist)

    try:
        tags.subscribe(taglist, login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)
    except SubscribeError:
        return xmpp_template('sub_denied', login=login)

    return xmpp_template('tags_sub_ok', login=login, tags=taglist)

def unsubscribe(taglist, login=None):
    taglist = parse_tags(taglist)

    try:
        tags.unsubscribe(taglist, login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)

    return xmpp_template('tags_unsub_ok', login=login, tags=taglist)

def add_to_blacklist(taglist, login=None):
    taglist = parse_tags(taglist)

    try:
        tags.add_to_blacklist(taglist, login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)
    except SubscribeError:
        return xmpp_template('bl_denied', login=login)

    return xmpp_template('blacklist_updated')

def del_from_blacklist(taglist, login=None):
    taglist = parse_tags(taglist)

    try:
        tags.del_from_blacklist(taglist, login)
    except UserNotFound:
        return xmpp_template('user_not_found', login=login)

    return xmpp_template('blacklist_updated')

