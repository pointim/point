# -*- coding: UTF-8 -*-

from api import auth, blog, users

prefix = r'/api'

urls = (
    # user blog by id
    (r'^%s/blog(?:/id/(?P<uid>\d+))?/?$' % prefix, blog.blog_by_id),
    # user blog by login (DEPRECATED)
    (r'^%s/blog(?:/(?P<login>[-a-zA-Z0-9]+))?/?$' % prefix, blog.blog),
    # user blog by login
    (r'^%s/blog(?:/login/(?P<login>[-a-zA-Z0-9]+))?/?$' % prefix, blog.blog),

    (r'^%s/recent/?' % prefix, blog.recent_all),
    (r'^%s/recent/posts/?$' % prefix, blog.recent_posts),
    (r'%s/all/?$' % prefix, blog.all_posts),

    (r'^%s/post/?$' % prefix, 'POST', blog.add_post),

    (r'^%s/post/(?P<id>[a-z]+)$' % prefix, 'GET', blog.show_post),
    (r'^%s/post/(?P<id>[a-z]+)$' % prefix, 'PUT', blog.edit_post),
    (r'^%s/post/(?P<id>[a-z]+)$' % prefix, 'DELETE', blog.delete_post),

    (r'^%s/post/(?P<id>[a-z]+)$' % prefix, 'POST', blog.add_comment),
    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)$' % prefix, 'DELETE', blog.delete_comment),
    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)$' % prefix, 'PATCH', blog.edit_comment),

    (r'^%s/post/(?P<id>[a-z]+)/r$' % prefix, 'POST', blog.recommend_post),
    (r'^%s/post/(?P<id>[a-z]+)/r$' % prefix, 'DELETE', blog.unrecommend_post),

    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)/r$' % prefix, 'POST', blog.recommend_comment),
    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)/r$' % prefix, 'DELETE', blog.unrecommend_comment),


    (r'^%s/post/(?P<id>[a-z]+)/s$' % prefix, 'POST', blog.subscribe),
    (r'^%s/post/(?P<id>[a-z]+)/s$' % prefix, 'DELETE', blog.unsubscribe),

    (r'^%s/post/(?P<id>[a-z]+)/pin$' % prefix, 'POST', blog.post_pin),
    (r'^%s/post/(?P<id>[a-z]+)/unpin$' % prefix, 'DELETE', blog.post_unpin),

    (r'^%s/comments/?$' % prefix, blog.comments),

    (r'^%s/messages(/incoming)?/?$' % prefix, blog.messages_incoming),
    (r'^%s/messages/outgoing/?$' % prefix, blog.messages_outgoing),

    (r'^%s/bookmarks/?$' % prefix, blog.bookmarks),

    (r'^%s/post/(?P<id>[a-z]+)/b$' % prefix, 'POST', blog.bookmark_post),
    (r'^%s/post/(?P<id>[a-z]+)/b$' % prefix, 'DELETE', blog.unbookmark_post),

    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)/b$' % prefix, 'POST', blog.bookmark_comment),
    (r'^%s/post/(?P<id>[a-z]+)/(?P<comment_id>\d+)/b$' % prefix, 'DELETE', blog.unbookmark_comment),

    #(r'^/feeds(?:/(?P<page>\d+))?/?$' % prefix, feeds.index),
    #(r'^/feeds/add/?$' % prefix, feeds.add_feed),
    #(r'^/feeds/subscribe/?$' % prefix, feeds.subscribe),

    (r'^%s/login/?$' % prefix, 'POST', auth.login),
    (r'^%s/logout/?$' % prefix, 'POST', auth.logout),

    (r'^%s/user/id/(?P<uid>\d+)/subscriptions/?$' % prefix, users.subscriptions_byid),
    (r'^%s/user/login/(?P<login>[-a-zA-Z0-9]+)/subscriptions/?$' % prefix, users.subscriptions),

    (r'^%s/user/(?P<login>[-a-zA-Z0-9]+)/subscriptions/?$' % prefix, users.subscriptions),
    # WILL BE DEPRECATED soon
    (r'^%s/user/id/(?P<uid>\d+)/subscribers/?$' % prefix, users.subscribers_byid),
    (r'^%s/user/login/(?P<login>[-a-zA-Z0-9]+)/subscribers/?$' % prefix, users.subscribers),
    # WILL BE DEPRECATED soon
    (r'^%s/user/(?P<login>[-a-zA-Z0-9]+)/subscribers/?$' % prefix, users.subscribers),

    (r'^%s/user/s/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'POST', users.subscribe),
    (r'^%s/user/s/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'DELETE', users.unsubscribe),

    (r'^%s/user/sr/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'POST', users.subscribe_rec),
    (r'^%s/user/sr/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'DELETE', users.unsubscribe_rec),

    (r'^%s/user/wl/?$' % prefix, 'GET', users.whitelist),
    (r'^%s/user/wl/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'POST', users.add_to_whitelist),
    (r'^%s/user/wl/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'DELETE', users.del_from_whitelist),

    (r'^%s/user/bl/?$' % prefix, 'GET', users.blacklist),
    (r'^%s/user/bl/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'POST', users.add_to_blacklist),
    (r'^%s/user/bl/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, 'DELETE', users.del_from_blacklist),
    (r'^%s/user/blers/?$' % prefix, 'GET', users.blacklisters),

    (r'^%s/unread-counters' % prefix, 'GET', users.unread_counters),

    # user info via id
    (r'^%s/user/id/(?P<uid>\d+)/?$' % prefix, users.user_info_byid),
    # WILL BE DEPRECATED soon
    # user info via login (for old clients)
    (r'^%s/user/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, users.info),
    # user info via login
    (r'^%s/user/login/(?P<login>[-a-zA-Z0-9]+)/?$' % prefix, users.info),
    # user info via settings.domain/api/me
    (r'^%s/me/?$' % prefix, users.my_info),

    # Получение спика тегов пользователя по его user id или логину. 
    # Во избежание дублирования кода оба шаблона URL используют именованное 
    # регулярное выражение login
    # by id
    (r'^%s/tags(?:/id/(?P<login>\d+))?/?$' % prefix, blog.tags),
    # by login
    (r'^%s/tags(?:/login/(?P<login>[-a-zA-Z0-9]+))?/?$' % prefix, blog.tags),
    # by login (DEPRECATED)
    (r'^%s/tags(?:/(?P<login>[-a-zA-Z0-9]+))?/?$' % prefix, blog.tags),
    #(r'^%s/tag/s$' % prefix, users.tag_subscribe),
    #(r'^%s/tag/u$' % prefix, users.tag_unsubscribe),
    #(r'^%s/tag/bl$' % prefix, users.tag_add_to_blacklist),
    #(r'^%s/tag/ubl$' % prefix, users.tag_del_from_blacklist),

    #(r'^%s/profile/?$' % prefix, profile.profile),
    #(r'^%s/profile/accounts/?$' % prefix, profile.accounts),
    #(r'^%s/profile/ulogin/?$' % prefix, profile.ulogin),
    #(r'^%s/profile/accounts/confirm/(?P<code>[0-9a-f]{40})/?$' % prefix, profile.confirm_account),

    

    
)

