from point.core.feed import Feed, FeedNotFound
from point.util.env import env

def subscriptions():
    feeds = env.user.subscriptions('feed')
    #ids = [ f.id for f in feeds ]
    return feeds

def get_feed(url):
    try:
        feed = Feed(url)
    except FeedNotFound:
        feed = Feed.from_data(None, None, url=url, fetch=True)

    #feed.posts()

    return feed

