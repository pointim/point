from views import index, blog, feeds, doc, mdoc, auth, users, profile, search, thumbnail

urls = (
    (r'^/(?:(?P<page>\d+)/?)?$', index),
    (r'^/recent(?P<unread>/unread)?(?:/(?P<page>\d+))?/?$', blog.recent_all),
    (r'^/recent/clear$', blog.clear_unread_posts),
    (r'^/_(?P<path>.+)$', doc),
    (r'^/doc/(?P<path>.+)/?$', mdoc),
    (r'^(?P<path>/(?:help.*|about|tos))$', mdoc),
    (r'^/blog(?:/(?P<page>\d+))?/?$', blog.blog),
    (r'^/posts(?:/(?P<page>\d+))?/?$', blog.recent_posts),
    (r'^/post/?$', blog.add_post),

    (r'^/t/(?:[0-9a-f]{2})/(?P<hash>[0-9a-f]{32})(?:\.jpg)?/?$', thumbnail),
    (r'^/usercss/(?P<login>[-a-zA-Z0-9]+)(?:\.css)?', users.usercss),

    (r'^/messages(?:/(?P<page>\d+))?/?$', blog.messages_new),
    (r'^/messages/incoming(?:/(?P<page>\d+))?/?$', blog.messages_incoming),
    (r'^/messages/outgoing(?:/(?P<page>\d+))?/?$', blog.messages_outgoing),

    (r'^/comments(?P<unread>/unread)?(?:/(?P<page>\d+))?/?$', blog.comments),
    (r'^/comments/clear$', blog.clear_unread_comments),

    (r'^/subscriptions/?$', users.subscriptions),
    (r'^/subscribers/?$', users.subscribers),

    (r'^/bookmarks(?:/(?P<page>\d+))?/?$', blog.bookmarks),

    (r'^/rss/?$', blog.blog_rss),

    (r'^/feeds(?:/(?P<page>\d+))?/?$', feeds.index),
    (r'^/feeds/add/?$', feeds.add_feed),
    (r'^/feeds/subscribe/?$', feeds.subscribe),

    (r'^/all(?:/(?P<page>\d+))?/?$', blog.all_posts),
    (r'^/all/warning/?', blog.all_posts_warning),
    (r'^/all/rss/?$', blog.all_posts_rss),

    (r'^/info/(?P<login>[-a-zA-Z0-9]+)?$', users.info),
    # this template DEPRECATED
    (r'^/avatar/(?P<login>[-a-zA-Z0-9]+)(?:/(?P<size>24|40|80|280))?/?$', users.avatar), 
    (r'^/avatar/id/(?P<login>[-a-zA-Z0-9]+)(?:/(?P<size>24|40|80|280))?/?$', users.avatar),
    (r'^/avatar/login/(?P<login>[-a-zA-Z0-9]+)(?:/(?P<size>24|40|80|280))?/?$', users.avatar),
    (r'^/user/s$', users.subscribe),
    (r'^/user/u$', users.unsubscribe),
    (r'^/user/sr$', users.subscribe_rec),
    (r'^/user/ur$', users.unsubscribe_rec),
    (r'^/user/wl$', users.add_to_whitelist),
    (r'^/user/uwl$', users.del_from_whitelist),
    (r'^/user/bl$', users.add_to_blacklist),
    (r'^/user/ubl$', users.del_from_blacklist),

    (r'^/tags/?$', blog.taglist),
    (r'^/tag/s$', users.tag_subscribe),
    (r'^/tag/u$', users.tag_unsubscribe),
    (r'^/tag/bl$', users.tag_add_to_blacklist),
    (r'^/tag/ubl$', users.tag_del_from_blacklist),

    (r'^(?P<path>/help.*)$', doc),
    (r'^(?P<path>/(?:donate|contacts|statistics))/?$', doc),

    (r'^/register/?$', auth.register),
    (r'^/(?P<path>register)/?$', mdoc),

    #(r'^/ulogin/?$', auth.ulogin),
    (r'^/login/?$', auth.login),
    (r'^/login/(?P<key>[0-9a-f]{40})$', auth.login_key),
    (r'^/logout/?$', auth.logout),
    (r'^/remember/?$', auth.remember),
    (r'^/remember/(?P<code>[0-9a-f]{64})/?$', auth.reset_password),

    (r'^/profile/?$', profile.profile),
    (r'^/profile/accounts/?$', profile.accounts),
    (r'^/profile/ulogin/?$', profile.ulogin),
    (r'^/profile/accounts/confirm/(?P<code>[0-9a-f]{40})/?$', profile.confirm_account),

    (r'/search/?$', search.search_posts),

    (r'^/(?P<id>[a-z]+)/?$', blog.show_post),
    (r'^/(?P<id>[a-z]+)/(?P<page>\d+)/?$', blog.show_post),

    (r'^/(?P<id>[a-z]+)/r$', blog.recommend),
    (r'^/(?P<id>[a-z]+)/ur$', blog.unrecommend),

    (r'^/(?P<id>[a-z]+)/d$', blog.delete),
    (r'^/(?P<id>[a-z]+)/e$', blog.edit_post),

    (r'^/(?P<id>[a-z]+)/s$', blog.subscribe),
    (r'^/(?P<id>[a-z]+)/u$', blog.unsubscribe),

    (r'^/(?P<id>[a-z]+)/b$', blog.bookmark),
    (r'^/(?P<id>[a-z]+)/ub$', blog.unbookmark),

    (r'^/(?P<id>[a-z]+)/pin$', blog.pin),
    (r'^/(?P<id>[a-z]+)/upin$', blog.unpin),

    (r'^/(?P<post_id>[a-z]+)/edit-comment/(?P<comment_id>[0-9]+)$', blog.edit_comment)
)

