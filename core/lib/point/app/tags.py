from geweb import log
import geweb.db.pgsql as db
from point.util.env import env
from point.core.user import User, SubscribeError

from psycopg2 import IntegrityError

def subscribe(taglist, login=None):
    if login:
        user = User('login', login)
        uid = user.id

        if user == env.user:
            raise SubscribeError
    else:
        uid = None

    if not isinstance(taglist, (list, tuple)):
        taglist = [taglist]
    for tag in taglist:
        try:
            db.perform("INSERT INTO subs.tags "
                       "(user_id, to_user_id, tag) "
                       "VALUES (%s, %s, %s);",
                       [env.user.id, uid, tag])
        except IntegrityError:
            pass

def unsubscribe(taglist, login=None):
    if login:
        user = User('login', login)
        uid = user.id
    else:
        uid = None

    if not isinstance(taglist, (list, tuple)):
        taglist = [taglist]
    if uid:
        db.perform("DELETE FROM subs.tags "
                   "WHERE user_id=%s AND to_user_id=%s "
                   "AND tag=ANY(%s);",
                   [env.user.id, uid, taglist])
    else:
        db.perform("DELETE FROM subs.tags "
                   "WHERE user_id=%s AND to_user_id IS NULL "
                   "AND tag=ANY(%s);",
                   [env.user.id, taglist])

def add_to_blacklist(taglist, login=None):
    if login:
        user = User('login', login)
        uid = user.id

        if user == env.user:
            raise SubscribeError
    else:
        uid = None

    if not isinstance(taglist, (list, tuple)):
        taglist = [taglist]
    for tag in taglist:
        try:
            db.perform("INSERT INTO posts.tags_blacklist "
                       "(user_id, to_user_id, tag) "
                       "VALUES (%s, %s, %s);",
                       [env.user.id, uid, tag])
        except IntegrityError:
            pass

def del_from_blacklist(taglist, login=None):
    if login:
        user = User('login', login)
        uid = user.id
    else:
        uid = None

    if not isinstance(taglist, (list, tuple)):
        taglist = [taglist]
    if uid:
        db.perform("DELETE FROM posts.tags_blacklist "
                   "WHERE user_id=%s AND to_user_id=%s "
                   "AND tag=ANY(%s);",
                   [env.user.id, uid, taglist])
    else:
        db.perform("DELETE FROM posts.tags_blacklist "
                   "WHERE user_id=%s AND to_user_id IS NULL "
                   "AND tag=ANY(%s);",
                   [env.user.id, taglist])

