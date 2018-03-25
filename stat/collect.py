#!/usr/bin/env python

import settings

#import sys
#sys.path.append(settings.core_path)

import os
from datetime import datetime, timedelta

from gevent import monkey; monkey.patch_all()
import json

import geweb.db.pgsql as db
from geweb import log

from pprint import pprint

end = datetime.now() - timedelta(days=1)
start = end - timedelta(days=settings.period)

def users():
    res = db.fetchall("SELECT created::date, count(id) AS cnt "
            "FROM users.info "
            "WHERE created::date >= %s AND created::date <= %s "
            "GROUP BY created::date "
            "ORDER BY created::date;", [start.date(), end.date()])
    fd = open(os.path.join(settings.stat_path, "users.json"), "w")
    json.dump(map(lambda o: [o[0].strftime("%Y-%m-%d"), o[1]], res), fd)
    fd.close()

def posts():
    res = db.fetchall("SELECT created::date, count(id) AS cnt "
            "FROM posts.posts "
            "WHERE created::date >= %s AND created::date <= %s AND private=false "
            "GROUP BY created::date "
            "ORDER BY created::date;", [start.date(), end.date()])
    fd = open(os.path.join(settings.stat_path, "posts.json"), "w")
    json.dump(map(lambda o: [o[0].strftime("%Y-%m-%d"), o[1]], res), fd)
    fd.close()

def comments():
    res = db.fetchall("SELECT c.created::date, count(c.id) AS cnt "
            "FROM posts.comments c "
            "JOIN posts.posts p ON c.post_id=p.id AND p.private=false "
            "WHERE c.created::date >= %s AND c.created::date <= %s "
            "GROUP BY c.created::date "
            "ORDER BY c.created::date;", [start.date(), end.date()])
    fd = open(os.path.join(settings.stat_path, "comments.json"), "w")
    json.dump(map(lambda o: [o[0].strftime("%Y-%m-%d"), o[1]], res), fd)
    fd.close()

def posters_weekly():
    res = db.fetchall("SELECT u.login, count(p.id) cnt "
                      "FROM posts.posts p "
                      "JOIN users.logins u ON p.author=u.id "
                      "WHERE p.created::date > now() - interval '7 days' AND p.private=false "
                      "GROUP BY u.login ORDER BY cnt DESC LIMIT 20;")
    fd = open(os.path.join(settings.stat_path, "posters_weekly.json"), "w")
    json.dump(list(res), fd)
    fd.close()

def commenters_weekly():
    res = db.fetchall("SELECT u.login, count(c.id) cnt "
                      "FROM posts.comments c "
                      "JOIN posts.posts p ON c.post_id=p.id AND p.private=false "
                      "JOIN users.logins u ON c.author=u.id "
                      "WHERE c.created::date > now() - interval '7 days' "
                      "GROUP BY u.login ORDER BY cnt DESC LIMIT 20;")
    fd = open(os.path.join(settings.stat_path, "commenters_weekly.json"), "w")
    json.dump(list(res), fd)
    fd.close()

def most_commented_weekly():
    res = db.fetchall("SELECT u.login, count(c.id) cnt "
                      "FROM posts.comments c "
                      "JOIN posts.posts p ON p.id=c.post_id AND p.private=false "
                      "JOIN users.logins u ON u.id=p.author "
                      "WHERE p.created::date > now() - interval '7 days' "
                      "AND c.author != p.author "
                      "GROUP BY u.login ORDER BY cnt DESC LIMIT 20;")
    fd = open(os.path.join(settings.stat_path, "most_commented_weekly.json"), "w")
    json.dump(list(res), fd)
    fd.close()

def posts_avg():
    res = db.fetchall("SELECT "
                      "CASE WHEN d::int=1 THEN 6 ELSE d::int-2 END d, "
                      "round(avg(cnt))::int "
                      "FROM "
                        "(SELECT to_char(created::date, 'd') d, count(id) cnt "
                        "FROM posts.posts "
                        "WHERE created::date > now() - interval '1 month' AND private=false "
                        "GROUP BY created::date) AS wt "
                      "GROUP BY d ORDER BY d;")
    fd = open(os.path.join(settings.stat_path, "posts_avg.json"), "w")
    json.dump(map(lambda r: r[1], sorted(res, key=lambda r: r[0])), fd)
    fd.close()

def comments_avg():
    res = db.fetchall("SELECT "
                      "CASE WHEN d::int=1 THEN 6 ELSE d::int-2 END d, "
                      "round(avg(cnt))::int "
                      "FROM "
                        "(SELECT to_char(created::date, 'd') d, count(id) cnt "
                        "FROM posts.comments "
                        "WHERE created::date > now() - interval '1 month' "
                        "GROUP BY created::date) AS wt "
                      "GROUP BY d ORDER BY d;")
    fd = open(os.path.join(settings.stat_path, "comments_avg.json"), "w")
    json.dump(map(lambda r: r[1], sorted(res, key=lambda r: r[0])), fd)
    fd.close()

def blacklisted():
    res = db.fetchall("SELECT u.login, count(b.user_id) cnt "
                      "FROM users.blacklist b "
                      "JOIN users.logins u ON b.to_user_id=u.id "
                      "GROUP BY u.login ORDER BY cnt DESC LIMIT 20;")
    fd = open(os.path.join(settings.stat_path, "blacklisted.json"), "w")
    json.dump(list(res), fd)
    fd.close()

def blacklisters():
    res = db.fetchall("SELECT u.login, count(b.to_user_id) cnt "
                      "FROM users.blacklist b "
                      "JOIN users.logins u ON b.user_id=u.id " 
                      "GROUP BY u.login ORDER BY cnt DESC LIMIT 20;")
    fd = open(os.path.join(settings.stat_path, "blacklisters.json"), "w")
    json.dump(list(res), fd)
    fd.close()

if __name__ == "__main__":
    #users()
    #posts()
    #comments()
    #posters_weekly()
    #commenters_weekly()
    #most_commented_weekly()
    #posts_avg()
    #comments_avg()
    #blacklisted()
    blacklisters()

