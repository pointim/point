from point.app import posts
from point.util import timestamp, parse_logins
from point.util.env import env
from point.util.www import check_referer
from geweb.http import Response
from geweb.session import Session
from geweb.exceptions import Forbidden, NotFound
from geweb.template import render, render_string
from point.core.post import Post, PostAuthorError, PostTextError, \
                            RecommendationNotFound, RecommendationError, \
                            RecommendationExists, BookmarkExists, \
                            PostUpdateError, PostDiffError, PostCommentedError,\
                            AlreadySubscribed
from point.core.user import SubscribeError, UserNotFound, check_auth
from geweb.util import csrf
from point.util.www import catch_errors
from point.util.imgproc import make_attach, remove_attach
import PyRSS2Gen
from hashlib import md5
from datetime import datetime
from random import randint
import os
from unidecode import unidecode
import math

from views.filters import markdown_filter

import json

from geweb import log

try:
    import re2 as re
except ImportError:
    import re

import settings

@catch_errors
def blog(page=1):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    if not env.owner or not env.owner.id:
        raise UserNotFound

    offset = (page - 1) * settings.page_limit

    plist = posts.recent_blog_posts(env.owner, settings.page_limit+1, offset)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
            p['text'] = markdown_filter(None, p['text'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/blog.html', section='blog', posts=plist, page=page)

@catch_errors
def blog_rss():
    if not env.owner or not env.owner.id:
        raise UserNotFound

    if env.owner.type == 'feed':
        raise Forbidden

    plist = posts.recent_blog_posts(env.owner, settings.page_limit, 0)

    feed = PyRSS2Gen.RSS2(
            title="%s@point" % env.owner.login,
            link='http://%s.%s/' % (env.owner.login, settings.domain),
            description="Point.im user's blog")

    for p in plist:
        if 'comment_id' in p and p['comment_id']:
            title='#%s/%s' % (p['post'].id, p['comment_id'])
            link = 'http://%s/%s#%s' % \
                    (settings.domain, p['post'].id, p['comment_id'])
        else:
            title='#%s' % p['post'].id
            link = 'http://%s/%s' % (settings.domain, p['post'].id)

        feed.items.append(PyRSS2Gen.RSSItem(
            author=env.owner.login,
            title=title,
            link=link,
            guid=link,
            pubDate=p['post'].created,
            categories=p['post'].tags,
            description=render_string('/rss-text.html', p=p)
        ))

    return Response(feed.to_xml(), mimetype='application/rss+xml')

@catch_errors
@check_auth
def recent_all(page=1, unread=False):
    if not env.owner or env.owner.id != env.user.id:
        return Response(redirect="%s://%s.%s/recent" % \
                        (env.request.protocol, env.user.login, settings.domain))
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    unread = bool(unread)

    plist = posts.recent_posts(unread=unread,
                               offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/recent.html', section='recent_all', unread=unread,
                  posts=plist, page=page)

@catch_errors
@check_auth
def recent_posts(page=1, unread=False):
    if not env.owner or env.owner.id != env.user.id:
        return Response(redirect="%s://%s.%s/recent" % \
                        (env.request.protocol, env.user.login, settings.domain))
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    unread = bool(unread)

    plist = posts.recent_posts(type='post', unread=bool(unread),
                               offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/recent.html', section='recent_posts', unread=unread,
                  posts=plist, page=page)

@catch_errors
@csrf
@check_auth
@check_referer
def clear_unread_posts():
    posts.clear_unread_posts()
    return Response(redirect=env.request.referer)

@catch_errors
@check_auth
def all_posts(page=1):
    sess = Session()
    if not sess['agree']:
        if env.request.args('agree'):
            sess['agree'] = True
            sess.save()
        else:
            return all_posts_warning()

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.select_posts(private=False, author_private=False,
                               blacklist=True,
                               limit=settings.page_limit+1, offset=offset)

    return render('/all_posts.html', section='all', posts=plist, page=page)

@catch_errors
def all_posts_rss():
    plist = posts.select_posts(private=False, author_private=False,
                               deny_anonymous=False, blacklist=True,
                               limit=settings.page_limit*4)

    feed = PyRSS2Gen.RSS2(
            title="Point.im",
            link='http://%s/' % (settings.domain),
            description="Point.im")

    for p in plist:
        if 'comment_id' in p and p['comment_id']:
            title='#%s/%s' % (p['post'].id, p['comment_id'])
            link = 'http://%s/%s#%s' % \
                    (settings.domain, p['post'].id, p['comment_id'])
        else:
            title='#%s' % p['post'].id
            link = 'http://%s/%s' % (settings.domain, p['post'].id)

        feed.items.append(PyRSS2Gen.RSSItem(
            author=env.owner.login,
            title=title,
            link=link,
            guid=link,
            pubDate=p['post'].created,
            categories=p['post'].tags,
            description=render_string('/rss-text.html', p=p)
        ))

    return Response(feed.to_xml(), mimetype='application/rss+xml')

def all_posts_warning():
    try:
        referer = env.request.args('referer')
    except KeyError:
        referer = env.request.referer
    if not referer:
        referer = '%s://%s/' % (env.request.protocol, settings.domain)

    return render('/all_posts_warning.html', referer=referer)

@catch_errors
@check_auth
def messages_new(page=1):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.private_unread(offset=offset, limit=settings.page_limit+1)

    if not plist and page == 1:
        return Response(redirect='%s://%s/messages/incoming' % \
                        (env.request.protocol, settings.domain))

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/messages/index.html', section='messages', posts=plist, page=page)

@catch_errors
@check_auth
def messages_incoming(page=1):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.private_incoming(offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/messages/incoming.html', section='messages', posts=plist, page=page)

@catch_errors
@check_auth
def messages_outgoing(page=1):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.private_outgoing(offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/messages/outgoing.html', section='messages/outgoing', posts=plist, page=page)

@catch_errors
@check_auth
def comments(page=1, unread=False):
    if not env.owner or env.owner.id != env.user.id:
        return Response(redirect='%s://%s.%s%s' % \
                        (env.request.protocol,
                         env.user.login.lower(), settings.domain,
                         env.request.path))

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.recent_commented_posts(unread=unread,
                                         offset=offset,
                                         limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/comments.html', section='comments',
                  unread=unread, posts=plist, page=page)

@catch_errors
@csrf
@check_auth
@check_referer
def clear_unread_comments():
    posts.clear_unread_comments()
    return Response(redirect=env.request.referer)

@catch_errors
def taglist():
    if not env.owner or not env.owner.id:
        raise UserNotFound

    if not env.user.login and env.owner.get_profile('deny_anonymous'):
        raise Forbidden

    sort_by_name = env.request.args('order', '') != 'cnt'

    tags = env.owner.tags(all=True, sort_by_name=sort_by_name)

    return render('/tags-list.html', tags=tags, sort_by_name=sort_by_name)

@catch_errors
def tag_posts(tag, page=1):
    if env.request.host != settings.domain and (not env.owner or not env.owner.id):
        raise UserNotFound

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    if env.owner and env.owner.id:
        author = env.owner
    else:
        author = None

    if env.owner and env.owner.id == env.user.id:
        private = None
    else:
        private = False

    # variable deny_anonymous is for corresponding value of 'deny_anonymous'
    # field in 'users.profile' table
    deny_anonymous = False if not env.user.is_authorized() else None

    if not isinstance(tag, (list, tuple)):
        tag = [tag]
    tag = [t.decode('utf-8', 'ignore').replace(u"\xa0", " ") for t in tag]

    plist = posts.select_posts(author=author, private=private,
                               deny_anonymous=deny_anonymous, tags=tag,
                               offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    section = 'blog' if env.owner and env.user.id == env.owner.id else ''

    return render('/tags.html', section=section, posts=plist, page=page,
                  tags=tag)

@catch_errors
def show_post(id, page=None):
    post = posts.show_post(id)

    if env.request.method == 'POST':
        return add_comment(post.id)

    if not env.owner or env.owner.id != post.author.id:
        return Response(redirect='%s://%s.%s/%s' % \
                        (env.request.protocol,
                         post.author.login.lower(), settings.domain, id))

    errors = []
    if env.request.args('expired'):
        errors.append('expired')
    if env.request.args('commented'):
        errors.append('commented')

    sess = Session()

    tree = env.request.args('tree')

    if tree:
        if tree.lower() in ('0', 'false', 'f'):
            tree = False
        else:
            tree = True
        sess['ctree'] = tree
        sess.save()
    elif sess['ctree'] is not None:
        tree = sess['ctree']
    else:
        env.user.get_profile('tree')

    comments_count = post.comments_count()

    if comments_count > 1000:
        climit = 100

        tree = False

        last_page = int(math.ceil(float(comments_count) / climit))

        try:
            page = int(page)
        except (TypeError, ValueError):
            page = last_page

        cstart = (page - 1) * climit
        comments = post.comments(cuser=env.user, offset=cstart, limit=climit)
    else:
        comments = post.comments(cuser=env.user)
        page = None
        last_page = None

    if env.user.is_authorized():
        posts.clear_unread_posts(id)
        if comments:
            posts.clear_unread_comments(id)

    if tree:
        cout = {}
        for c in comments:
            cout[c.id] = c
            if c.to_comment_id and c.to_comment_id in cout:
                cout[c.to_comment_id].comments.append(c)
            else:
                c.to_comment_id = None
        comments = filter(lambda c: not c.to_comment_id, cout.itervalues())

    sess = Session()
    clear_post_input = sess['clear_post_input']
    if clear_post_input:
        sess['clear_post_input'] = False
        sess.save()

    section = 'messages' if post.private else ''

    return render('/post.html', post=post, comments=comments,
                  comments_count=comments_count, tree=tree,
                  errors=errors, section=section,
                  page=page, last_page=last_page,
                  clear_post_input=clear_post_input)

def _files(files):
    if not files:
        files = []
    hash = md5(str(datetime.now())).hexdigest()
    dest = '%s/%s/%s/%s' % (env.user.login[0], env.user.login,
                            hash[:2], hash[2:4])

    files_del = env.request.args('del-attach', [])
    if not isinstance(files_del, (list, tuple)):
        files_del = [files_del]
    for f in files_del:
        if f not in files:
            continue
        remove_attach(f)
        files.remove(f)

    files_in = env.request.args('attach', [])
    files_p = env.request.files('attach')

    if not isinstance(files_in, (list, tuple)):
        files_in = [files_in]
        files_p = [files_p]

    for i, file in enumerate(files_in[:10]):
        if isinstance(file, str):
            file = file.decode('utf-8')
        file = re.sub(r'[^\w\.]+', '-', unidecode(file))
        d = "%s/%s/" % (dest, randint(1000, 9999))
        make_attach(files_p[i], d, file, remove=True)
        files.append(os.path.join(d, file))

    return files

@catch_errors
@check_auth
def edit_post(id):
    try:
        post = posts.show_post(id)
    except PostAuthorError:
        raise SubscribeError

    if env.request.method == 'GET':
        return render('/post-edit.html', post=post)

    files = _files(post.files)

    @csrf
    def save(post):
        text = env.request.args('text', '').strip()

        tags = env.request.args('tags', '').strip(' \t*,;')
        if isinstance(tags, str):
            tags = tags.decode('utf-8')
        tags = [t.replace(u"\xa0", " ") for t in re.split(r'\s*[,;*]\s*', tags)]

        private = bool(env.request.args('private'))

        posts.edit_post(post, text=text, tags=tags, private=private, files=files)

        return Response(redirect='%s://%s.%s/%s' % \
                                 (env.request.protocol,
                                  env.user.login, settings.domain, post.id))
    try:
        return save(post)
    except PostUpdateError:
        return Response(redirect='%s://%s.%s/%s?expired=1' % \
                                 (env.request.protocol,
                                  env.user.login, settings.domain, post.id))
    except PostCommentedError:
        return Response(redirect='%s://%s.%s/%s?commented=1' % \
                                 (env.request.protocol,
                                  env.user.login, settings.domain, post.id))
    except PostDiffError:
        return render('/post-edit.html', post=post, errors=['diff'])

@catch_errors
@csrf
@check_auth
@check_referer
def add_post():
    text = env.request.args('text', '').strip()

    tags = env.request.args('tags', '').strip(' \t*,;')
    if isinstance(tags, str):
        tags = tags.decode('utf-8')
    tags = [t.replace(u"\xa0", " ") for t in re.split(r'\s*[,;*]\s*', tags)]

    private = bool(env.request.args('private'))

    m = re.search(r'^\s*(?P<to>(?:@[a-zA-Z0-9_-]+[,\s]*)+)', text)
    to = parse_logins(m.group('to')) if m else []

    files = _files([])

    sess = Session()
    sess['clear_post_input'] = True
    sess.save()

    try:
        id = posts.add_post(text, tags=tags, to=to, private=private, files=files)
    except PostTextError:
        return render('/post-error.html')
        
    log.info('add_post: #%s %s %s' % (id, env.user.login, env.request.remote_host))

    return Response(redirect='%s://%s.%s/%s' % \
                             (env.request.protocol,
                              env.user.login, settings.domain, id))

@catch_errors
@csrf
@check_auth
@check_referer
def add_comment(id):
    to_comment_id = env.request.args('comment_id')
    text = env.request.args('text', '').strip()
    files = _files([])

    try:
        comment_id = posts.add_comment(id, to_comment_id, text, files=files)
    except PostTextError:
        return render('/comment-error.html')

    if env.owner and env.owner.login:
        login = env.owner.login.lower()
    else:
        post = Post(id)
        login = post.author.login.lower()

    log.info('add_comment: #%s/%s %s %s' % (id, comment_id, env.user.login, env.request.remote_host))

    return Response(redirect='%s://%s.%s/%s#%s' % \
                             (env.request.protocol,
                              login, settings.domain, id, comment_id))

@catch_errors
@csrf
@check_auth
@check_referer
def edit_comment(post_id, comment_id):
    if comment_id == '0':
        raise NotFound
    else:
        try:
            posts.edit_comment(post_id, comment_id,
                env.request.args('text', ''), editor=env.user)
        except PostTextError:
            return render('/comment-error.html')

        if env.owner and env.owner.login:
            login = env.owner.login.lower()
        else:
            post = Post(post_id)
            login = post.author.login.lower()

        return Response(redirect='%s://%s.%s/%s#%s' % \
            (env.request.protocol, login, settings.domain, post_id, comment_id))


@catch_errors
@csrf
@check_auth
@check_referer
def recommend(id):
    comment_id = env.request.args('comment_id')
    text = env.request.args('text')
    try:
        rcid = posts.recommend(id, comment_id, text)
    except RecommendationError:
        raise Forbidden
    except RecommendationExists:
        return Response(redirect=env.request.referer)
    if rcid:
        rcid = '#%s' % rcid
    else:
        rcid = ''

    if env.owner and env.owner.login:
        login = env.owner.login.lower()
    else:
        post = Post(id)
        login = post.author.login.lower()

    return Response(redirect='%s://%s.%s/%s%s' % \
                    (env.request.protocol, login, settings.domain, id, rcid))

@catch_errors
@csrf
@check_auth
@check_referer
def unrecommend(id):
    comment_id = env.request.args('comment_id')
    try:
        posts.unrecommend(id, comment_id)
    except RecommendationNotFound:
        pass

    return Response(redirect=env.request.referer)

@catch_errors
@csrf
@check_auth
@check_referer
def delete(id):
    comment_id = env.request.args('comment_id')
    try:
        if comment_id:
            post = posts.delete_comment(id, comment_id)
            if env.owner:
                login = post.author.login.lower()
            else:
                post = Post(id)
                login = post.author.login.lower()

            return Response(redirect='%s://%s.%s/%s' % \
                            (env.request.protocol, login, settings.domain, id))
        else:
            posts.delete_post(id)
            return Response(redirect='%s://%s.%s/blog' % \
               (env.request.protocol, env.user.login.lower(), settings.domain))
    except PostAuthorError:
        raise SubscribeError

@catch_errors
@csrf
@check_auth
@check_referer
def subscribe(id):
    try:
        posts.subscribe(id)
    except AlreadySubscribed:
        raise Forbidden

    if env.request.is_xhr:
        return Response(json.dumps({'ok': True}), mimetype='application/json')

    return Response(redirect=env.request.referer)

@catch_errors
@csrf
@check_auth
@check_referer
def unsubscribe(id):
    posts.unsubscribe(id)

    if env.request.is_xhr:
        return Response(json.dumps({'ok': True}), mimetype='application/json')

    return Response(redirect=env.request.referer)

@catch_errors
@check_auth
def bookmarks(page=1):
    if not env.owner or env.owner.id != env.user.id:
        return Response(redirect='%s://%s.%s/%s' % \
                        (env.request.protocol, env.user.login.lower(),
                         settings.domain, env.request.path))
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.bookmarks(settings.page_limit+1, offset)

    #if env.request.is_xhr:
    #    for p in plist:
    #        p['created'] = timestamp(p['created'])
    #        p['text'] = html(None, p['text'], True)
    #    return Response(json.dumps(plist), mimetype='application/json')

    section = 'bookmarks'

    return render('/bookmarks.html', section=section, posts=plist, page=page)

@catch_errors
@csrf
@check_auth
@check_referer
def bookmark(id):
    comment_id = env.request.args('comment_id')
    text = env.request.args('text')
    try:
        posts.bookmark(id, comment_id, text)
    except BookmarkExists:
        pass

    return Response(redirect=env.request.referer)

@catch_errors
@csrf
@check_auth
@check_referer
def unbookmark(id):
    comment_id = env.request.args('comment_id')
    posts.unbookmark(id, comment_id)

    return Response(redirect=env.request.referer)

@catch_errors
@csrf
@check_auth
@check_referer
def pin(id):
    post = Post(id)
    if env.user.id == post.author.id:
        post.set_pinned(True)
        return Response(redirect=env.request.referer)
    else:
        raise Forbidden

@catch_errors
@csrf
@check_auth
@check_referer
def unpin(id):
    post = Post(id)
    if env.user.id == post.author.id:
        post.set_pinned(False)
        return Response(redirect=env.request.referer)
    else:
        raise Forbidden
