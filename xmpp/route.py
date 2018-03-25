""" Routes """

from views import users, posts, tags, search, common, command_disabled
import settings

post_re = r'(?:#(?P<post_id>[a-z]+))'
login_re = r'(?:@(?P<login>[a-z0-9_-]+))'
show_re = r'(?:\s*(?P<show>\+)(?:\s*(?:(?P<offset>\d+)\s+)?(?P<limit>\d+))?)'

route = [
    {'resource': r'%s$' % post_re, 'route': [
        [r'^%s$' % show_re, posts.show_post],
    ]},
    {'resource': r'^%s$' % login_re, 'route': [
        [r'^%s$' % show_re, users.info],
    ]},
    {'resource': settings.xmpp_resource, 'route': [
        # profile & info
        [r'^%s%s?$' % (login_re, show_re), users.info],
        [r'^%s *(?P<show>\+\+)$' % (login_re), users.info],
        [r'^(?:set\s*)?passw(?:or)?d(?:\s+.+)?$', users.set_password],
        [r'^set\s+(?P<param>\S+)[=\s]+(?P<value>.*)', users.set_param],
        [r'^set\s+(?P<param>\S+)$', users.get_param],
        [r'^get\s+(?P<param>\S+)', users.get_param],
        [r'^reg(?:ister)?\s+@?(?P<login>[a-z0-9_-]+)?(?:\s+(?P<password>.+))?$', users.register],
        [r'^on$', users.im_online],
        [r'^off$', users.im_offline],

        [r'^login$', users.login],
        [r'^w(?:hoami)?$', users.whoami],

        [r'^confirm\s*(?P<code>\S.+)', users.confirm_account],

        # subscriptions
        [r'^s(?:ubscribe)?\s*(?P<rec>!)?\s*%s\s*$' % login_re, users.subscribe],
        [r'^u(?:nsubscribe)?\s*(?P<rec>!)?\s*%s\s*$' % login_re, users.unsubscribe],
        [r'^wl\s*(?P<logins>(?:@[a-z0-9_-]+[\s,]*)+)\s*', users.add_to_whitelist],
        [r'^uwl\s*(?P<logins>(?:@[a-z0-9_-]+[\s,]*)+)\s*', users.del_from_whitelist],
        [r'^bl\s*(?P<logins>(?:@[a-z0-9_-]+[\s,]*)+)\s*$', users.add_to_blacklist],
        [r'^ubl\s*(?P<logins>(?:@[a-z0-9_-]+[\s,]*)+)\s*$', users.del_from_blacklist],

        [r'^s(?:ubscribe)?\s*(?:%s\s*)?\*\*(?P<taglist>.+)' % login_re, tags.subscribe],
        [r'^s(?:ubscribe)?\s*(?:%s\s*)?\*(?P<taglist>.+)' % login_re, tags.subscribe],
        [r'^u(?:nsubscribe)?\s*(?:%s\s*)?\*\*(?P<taglist>.+)' % login_re, tags.unsubscribe],
        [r'^u(?:nsubscribe)?\s*(?:%s\s*)?\*(?P<taglist>.+)' % login_re, tags.unsubscribe],
        [r'^bl\s*(?:@%s\s*)?\*\*(?P<taglist>.+)' % login_re, tags.add_to_blacklist],
        [r'^bl\s*(?:%s\s*)?\*(?P<taglist>.+)' % login_re, tags.add_to_blacklist],
        [r'^ubl\s*(?:%s\s*)?\*\*(?P<taglist>.+)' % login_re, tags.del_from_blacklist],
        [r'^ubl\s*(?:%s\s*)?\*(?P<taglist>.+)' % login_re, tags.del_from_blacklist],

        [r'^s(?:ub(?:s(?:cription(?:s)?)?)?)?$', users.subscriptions],
        [r'^(?:wl|whitelist)$', users.whitelist],
        [r'^(?:bl|blacklist)$', users.blacklist],

        [r'^e(?:dit)?\s*%s\s*\*\*(?P<taglist>.*)$' % post_re, posts.update_tags],
        [r'^e(?:dit)?\s*%s\s*\*(?P<taglist>.*)$' % post_re, posts.update_tags],

        [r'^s(?:ubscribe)?\s*%s(?:\s*[/.]\s*\d+)?$' % post_re, posts.subscribe],
        [r'^u(?:nsubscribe)?\s*%s(?:\s*[/.]\s*\d+)?$' % post_re, posts.unsubscribe],

        [r'^d\s*%s$' % post_re, posts.delete_post],

        [r'^%s\s*(?P<all>\+\+)$' % post_re, posts.show_post],
        [r'^%s\s*(?P<last>\+)$' % post_re, posts.show_post],
        [r'^%s%s?$' % (post_re, show_re), posts.show_post],

        [r'^%s\s*[/.]\s*(?P<comment_id>\d+)$' % post_re, posts.show_comment],
        [r'^%s(?:\s*[/.]\s*(?P<to_comment_id>\d+))?(?P<text>.+)$' % post_re, posts.add_comment],
        [r'^s(?:ubscribe)?\s*%s(?:\s*[/.]\s*(?P<to_comment_id>\d+))?\s*(?P<text>.+)$' % post_re, posts.add_comment], # special for @hirthwork
        [r'^d\s*%s\s*[/.]\s*(?P<comment_id>\d+)$' % post_re, posts.delete_comment],

        [r'^#\s*%s?' % show_re, posts.all_posts],

        [r'^d\s*l(ast)?$', posts.delete_last],
        [r'^d\s*l(ast)?$', command_disabled],

        [r'^i(?:nvite)?\s*%s\s*(?P<to>(?:(?:@[a-z0-9_-]+)+\s*)+)$' % post_re, posts.add_recipients],
        [r'^(?:ui|uninvite)?\s*%s\s*(?P<to>(?:(?:@[a-z0-9_-]+)+\s*)+)$' % post_re, posts.del_recipients],

        [r'^!\s*%s(?:[/.](?P<comment_id>\d+))?(?:\s*(?P<text>.+))?$' % post_re, posts.recommend],
        [r'^~\s*%s(?:[/.](?P<comment_id>\d+))?(?:\s*(?P<text>.+))?$' % post_re, posts.bookmark],
        [r'^~(?:\s*(?:(?P<offset>\d+)\s+)?(?P<limit>\d+))?', posts.bookmarks],

        [r'^pin\s*%s$' % post_re, posts.pin_post],
        [r'^unpin\s*%s$' % post_re, posts.unpin_post],

        #[r'^upd\s*%s(?:[/.]\d+)?\s*(?P<text>.+)$' % post_re, posts.update_post],

        [r'^pm?%s?$' % show_re, posts.private_posts],
        [r'^%s$' % show_re, posts.recent],
        [r'^\*\*\s*(?P<tag>[^\+\*\/\n]+)%s?$' % (show_re), posts.tag_posts],
        [r'^(?P<tag>(?:\*\s*[^\s\+\*]+\s*)+)%s?$' % (show_re), posts.tag_posts],
        [r'^%s\s*\*\*\s*(?P<tag>[^\+\*\n]+)%s?$' % (login_re, show_re), posts.tag_posts],
        [r'^%s\s*(?P<tag>(?:\*\s*[^\s\+\*]+\s*)+)%s?$' % (login_re, show_re), posts.tag_posts],

        [r'^alias$', users.alias_list],
        [r'^alias\s+(?P<alias>[^=]+)$', users.get_alias],
        [r'^alias\s+(?P<alias>.+?)\s*(?<!\\)=\s*(?P<command>.*)$', users.set_alias],
        [r'^unalias\s+(?P<alias>[^=]+)$', users.unalias],

        [r'^help', common.show_help],
        [r'^ping', common.ping],

        #[r'^(?:nick|rename)\s+@?(?P<login>[a-z0-9_-]+)', users.rename],

        #[r'^\?\s*(?:\s*(?:(?P<offset>\d+)\s*)?(?P<limit>\d+))?\s*%s\s*(?P<text>.+)' % login_re, search.search_user_posts],
        [r'^\?\s*(?:\s*(?:(?P<offset>\d+)\s*)?(?P<limit>\d+))?\s*(?P<text>.+)', search.search_posts],

        [r'^e(?:dit)?\s*%s\s*\*\*?(?P<taglist>.+?)\s*(?:\r?\n|\*\*)\s*(?P<text>.*)$' % post_re, posts.edit_post],
        [r'^e(?:dit)?\s*%s\s*(?:(?P<taglist>(?:\*\s*\S+?\s*)+)\s+)?(?P<text>.*)$' % post_re, posts.edit_post],
        #[r'^e(?:dit)?\s*l(?:ast)?\s*\*\*?(?P<taglist>.+?)\s*(?:\r?\n|\*\*)\s*(?P<text>.*)$', posts.edit_last],
        #[r'^e(?:dit)?\s*l(?:ast)?\s*(?:(?P<taglist>(?:\*\s*\S+?\s*)+)\s+)?(?P<text>.*)$', posts.edit_last],
        [r'^e(?:dit)?\s*l(?:ast)?\s*\*\*?(?P<taglist>.+?)\s*(?:\r?\n|\*\*)\s*(?P<text>.*)$', command_disabled],
        [r'^e(?:dit)?\s*l(?:ast)?\s*(?:(?P<taglist>(?:\*\s*\S+?\s*)+)\s+)?(?P<text>.*)$', command_disabled],

        #[r'^(?P<private>pm?\s+)?(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)?\*\*?(?P<taglist>.+?)\s*(?:\r?\n|(?<![a-z]:)//)\s*(?P<text>.*)$', posts.add_post],

        #[r'^(?P<private>pm?\s+)?(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)?\*\*?(?P<taglist>.+?)\s*(?:\r?\n|\*\*|(?<![a-z]:)//)\s*(?P<text>.*)$', posts.add_post],
        #[r'^(?P<private>pm?\s+)?\*\*?(?P<taglist>.+?)(?:\r?\n|\*\*)\s*(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)\s*(?P<text>.*)$', posts.add_post],
        #[r'^(?P<private>pm?\s+)?(?:(?P<taglist>(?:\*\s*[^\s\*]+\s*)+)\s+)(?P<to>(?:@[a-z0-9_-]+[,\s]*)+\s+)(?P<text>.*)$', posts.add_post],
        #[r'^(?P<private>pm?\s+)?(?P<to>(?:@[a-z0-9_-]+[,\s]*)+)?(?:(?P<taglist>(?:[ \t]*\*[ \t]*\S+)+)\s+)?(?P<text>.*)$', posts.add_post],

        # point style tags
        [r'^\s*(?P<private>pm?\s*)?(?P<taglist>\*\*(?:[^,\*\r\n]+[ \t]*[\*,][ \t]*)*[^,\r\n]+(?:[\r\n]+|\*\*))\s*(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)\s*(?P<text>.+)?$', posts.add_post],
        [r'^\s*(?P<private>pm?\s*)?(?P<taglist>\*\*(?:[^,\*\r\n]+[ \t]*[\*,][ \t]*)*[^,\r\n]+(?:[\r\n]+|\*\*))\s*(?P<text>.+)?$', posts.add_post],
        [r'^\s*(?P<private>pm?\s*)?(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)\s*(?P<taglist>\*\*(?:[^,\*\r\n]+[ \t]*[\*,][ \t]*)*[^,\r\n]+(?:[\r\n]+|\*\*))\s*(?P<text>.+)?$', posts.add_post],
        [r'^\s*(?P<private>pm?\s*)?(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)\s*(?P<text>.+)?$', posts.add_post],

        # juick style tags
        [r'^\s*(?P<private>pm?\s*)?(?P<taglist>(?:\*[ \t]*\S+[ \t]*)+)\s*(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)\s*(?P<text>.+)$', posts.add_post],
        [r'^\s*(?P<private>pm?\s*)?(?P<taglist>(?:\*[ \t]*\S+[ \t]*)+)\s*(?P<text>.+)$', posts.add_post],
        [r'^\s*(?P<private>pm?\s*)?(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)\s*(?P<taglist>(?:\*[ \t]*\S+[ \t]*)+)\s*(?P<text>.+)$', posts.add_post],

        [r'^\s*(?P<private>pm?\s*)?(?P<to>(?:@[a-zA-Z0-9_-]+[, \t]*)+)(?P<text>.+)$', posts.add_post],

        [r'^\s*(?P<private>pm?\s+)?(?P<text>.+)$', posts.add_post]
    ]}
]
