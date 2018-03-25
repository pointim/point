from point.core.user import AlreadySubscribed, check_auth
from point.core.feed.exc import InvalidFeedUrl, InvalidFeedType, \
                                FeedFetchError
from point.app import feeds, posts
from point.util.env import env
from geweb.http import Response
from geweb.template import render
from geweb.util import csrf, urlencode, timestamp
from point.util.www import catch_errors
import json

import settings

@catch_errors
@check_auth
def index(page=1):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if not page:
        page = 1

    offset = (page - 1) * settings.page_limit

    plist = posts.recent_posts(type='feed',
                               offset=offset, limit=settings.page_limit+1)

    if env.request.is_xhr:
        for p in plist:
            p['created'] = timestamp(p['created'])
        return Response(json.dumps(plist), mimetype='application/json')

    return render('/feeds/index.html', feeds=feeds.subscriptions(),
                  posts=plist, page=page, section='feeds')

@catch_errors
@check_auth
def add_feed():
    url = env.request.args('url', '').strip()

    try:
        if url.index(settings.domain):
            return Response(redirect=url)
    except ValueError:
        pass

    if env.request.method == 'GET':
        return render('/feeds/add.html', section='feeds',
                      feeds=feeds.subscriptions(), url=url)

    errors = env.request.args('errors')
    if not errors:
        errors = []
    elif not isinstance(errors, (list, tuple)):
        errors = [errors]

    try:
        feed = feeds.get_feed(url)
    except InvalidFeedUrl:
        errors.append('url')
    except InvalidFeedType:
        errors.append('type')
    except FeedFetchError:
        errors.append('fetch')

    if errors:
        return render('/feeds/add.html', section='feeds',
                      feeds=feeds.subscriptions(), url=url, errors=errors)

    if feed.id and feed.check_subscriber(env.user):
        return Response(redirect="%s://%s.%s/" % \
                   (env.request.protocol, feed.login.lower(), settings.domain))
    try:
        feed.fetch()
    except FeedFetchError:
        errors.append('fetch')

    return render('/feeds/subscribe.html', section='feeds',
                  feeds=feeds.subscriptions(), feed=feed, url=url)

@catch_errors
@csrf
@check_auth
def subscribe():
    url = env.request.args('url', '').strip()

    if not url:
        return Response(redirect="%s://%s.%s/feeds/add" % \
                        (env.request.protocol, env.user.login.lower(),
                         settings.domain))

    try:
        if url.index(settings.domain):
            return Response(redirect=url)
    except ValueError:
        pass

    errors = []

    try:
        feed = feeds.get_feed(url)
        feed.fetch()
    except InvalidFeedUrl:
        errors.append('url')
    except InvalidFeedType:
        errors.append('type')
    except FeedFetchError:
        errors.append('fetch')

    if errors:
        return Response(redirect="%s://%s.%s/feeds/add?url=%s&%s" % \
                    (env.request.protocol, env.user.login.lower(),
                     settings.domain, urlencode(url),
                     '&'.join(["errors=%s" % e for e in errors])))

    if not feed.id:
        feed.save()

    try:
        env.user.subscribe(feed)
    except AlreadySubscribed:
        pass


    return Response(redirect="%s://%s.%s/" % \
                   (env.request.protocol, feed.login.lower(), settings.domain))

    if env.request.method == 'GET':
        return render('/feeds/subscribe.html', feeds=feeds.subscriptions(),
                                               feed=feed)


