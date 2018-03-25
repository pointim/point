from point.util.redispool import RedisPool
from geweb.session import Session
import json

import settings

def _sessions_key(id):
    return 'sessions:%s' % id

def user_sessions(user):
    redis = RedisPool(settings.session_socket)
    try:
        sessions = json.loads(redis.get(_sessions_key(user.id)))
        print '>>>>>>> sessions', sessions
        return sessions
    except (TypeError, ValueError):
        return []

def save_sessions(user, sessions):
    redis = RedisPool(settings.session_socket)
    redis.set(_sessions_key(user.id), json.dumps(sessions))

def add_session(user, sessid):
    sessions = user_sessions(user)
    if sessid not in sessions:
        sessions.append(sessid)
        save_sessions(user, sessions)

def del_session(user, sessid):
    sessions = user_sessions(user)
    dsessions = filter(lambda s: s!=sessid, sessions)
    if len(sessions) != len(dsessions):
        save_sessions(user, dsessions)

def set_sessions_param(user, param, value):
    sessions = user_sessions(user)
    for sessid in sessions:
        sess = Session(sessid)
        sess[param] = value
        sess.save()
 
