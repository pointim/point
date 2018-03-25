from point.core.user import User, UserNotFound, SubscribeError, \
                            AlreadySubscribed
from point.core.post import Post, PostNotFound, PostTextError, \
                            PostCommentedError, \
                            PostAlreadyPinnedError, PostNotPinnedError
from point.core.post import CommentNotFound, CommentAuthorError
from point.core.post import RecommendationError, RecommendationNotFound, \
                            RecommendationExists, PostAuthorError, \
                            PostDiffError, PostUpdateError, \
                            PostLimitError, PostReadonlyError
from point.core.post import BookmarkExists
from point.app import posts
from point.util import parse_tags, parse_logins
from geweb.env import env
from point.util.template import xmpp_template

def recent(show=None, offset=None, limit=None):
    if offset:
        offset = int(offset)
    if limit:
        limit = int(limit)
    else:
        limit = 10

    plist = posts.recent_posts(offset=offset, limit=limit)
    plist.reverse()

    return xmpp_template('posts', posts=plist)

def tag_posts(tag, login=None, show=None, offset=None, limit=None):
    if offset:
        offset = int(offset)
    if limit:
        limit = int(limit)
    else:
        limit = 10

    try:
        author = User('login', login) if login else None
    except UserNotFound, e:
        return xmpp_template('user_not_found', login=e.message)

    if env.user and author and env.user.id == author.id:
        private = None
    else:
        private = False

    plist = posts.select_posts(author=author, private=private,
                               tags=parse_tags(tag),
                               offset=offset, limit=limit)

    plist.reverse()

    return xmpp_template('posts', posts=plist)

def all_posts(show=None, offset=None, limit=None):
    if offset:
        offset = int(offset)
    if limit:
        limit = int(limit)
    else:
        limit = 10

    plist = posts.select_posts(offset=offset, limit=limit, private=False, blacklist=True)
    plist.reverse()

    return xmpp_template('posts', posts=plist)

def private_posts(show=False, offset=None, limit=None):
    if offset:
        offset = int(offset)
    if limit:
        limit = int(limit)
    else:
        offset = 0
        limit = 10

    plist = posts.private_unread(offset=offset, limit=limit)
    if not plist:
        plist = posts.private_incoming(offset=offset, limit=limit)
    plist.reverse()

    return xmpp_template('posts', posts=plist)

def add_post(text, taglist=None, to=None, private=False):
    taglist = parse_tags(taglist)
    if to:
        text = '%s %s' % (to.strip(), text.strip())
    to = parse_logins(to)
    try:
        post_id = posts.add_post(text, tags=taglist, to=to, private=private)
    except PostTextError:
        return xmpp_template('post_inadmissible')
    except UserNotFound, e:
        return xmpp_template('user_not_found', login=e.message)
    except SubscribeError, e:
        return xmpp_template('user_post_denied', login=e.message)
    except PostLimitError:
        return xmpp_template('post_interval_exceeded')
    return xmpp_template('msg_post_sent', post_id=post_id, private=private)

def edit_post(post_id, text, taglist=None, private=None):
    taglist = parse_tags(taglist)
    try:
        posts.edit_post(post_id, text, taglist, private)
    except (SubscribeError, PostAuthorError):
        return xmpp_template('post_denied', post_id=post_id)
    except PostUpdateError:
        return xmpp_template('post_upd_err', post_id=post_id)
    except PostCommentedError:
        return xmpp_template('post_commented_err', post_id=post_id)
    except PostDiffError:
        return xmpp_template('post_diff_err', post_id=post_id)
    return xmpp_template('post_upd', post_id=post_id)

def edit_last(text, taglist=None):
    post_id = posts._get_last()
    if not post_id:
        return xmpp_template("nothing_to_edit")

    return edit_post(post_id, text=text, taglist=taglist)

def delete_post(post_id):
    try:
        posts.delete_post(post_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except PostAuthorError:
        return xmpp_template('post_del_denied', post_id=post_id)

    return xmpp_template('post_del', post_id=post_id)

def update_post(post_id, text):
    try:
        posts.update_post(post_id, text)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except (SubscribeError, PostAuthorError):
        return xmpp_template('post_denied', post_id=post_id)
    except PostUpdateError:
        return xmpp_template('post_upd_err', post_id=post_id)
    return xmpp_template('post_upd', post_id=post_id)

def update_tags(post_id, taglist):
    taglist = parse_tags(taglist)
    try:
        posts.update_tags(post_id, taglist)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except (SubscribeError, PostAuthorError):
        return xmpp_template('post_denied', post_id=post_id)
    except PostUpdateError:
        return xmpp_template('post_upd_err', post_id=post_id)
    return xmpp_template('post_upd', post_id=post_id)

def show_post(post_id, last=False, all=False, show=False,
              offset=None, limit=None):
    try:
        post = posts.show_post(post_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except (SubscribeError, PostAuthorError):
        return xmpp_template('post_denied', post_id=post_id)

    subscribed = post.check_subscriber(env.user) if env.user.id else False

    updates = []
    for i, upd in enumerate(post.updates()):
        updates.append({'no': i+1, 'text': upd['text']})

    comments = []

    posts.clear_unread_posts(post_id)
    if last or all or show:
        if offset:
            offset = int(offset)
        if limit:
            limit = int(limit)
        else:
            limit = 10
        res = post.comments(last=last, all=all, offset=offset, limit=limit)
        for c in res:
            comments.append({
                'comment_id': c.id,
                'to_comment_id': c.to_comment_id,
                'comment_author': c.author.login,
                'comment_text': c.text,
                'is_rec': c.is_rec,
                'files': c.files
            })
        cnt = None
        posts.clear_unread_comments(post_id, map(lambda c: c.id, res))
    else:
        cnt = post.comments_count()

    return xmpp_template('post', post_id=post_id, author=post.author.login,
                                 type=post.type, private=post.private,
                                 title=post.title, link=post.link,
                                 tags=post.tags, text=post.text,
                                 tune=post.tune, files=post.files,
                                 subscribed=subscribed,
                                 updates=updates, comments=comments,
                                 comments_count=cnt,
                                 archive=post.archive,
                                 rec_users=post.recommended_users())

def add_comment(post_id, to_comment_id, text):
    try:
        comment_id = posts.add_comment(post_id, to_comment_id, text)
    except PostTextError:
        return xmpp_template('post_inadmissible')
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except CommentNotFound:
        return xmpp_template('comment_not_found', post_id=post_id,
                                                  comment_id=to_comment_id)
    except PostReadonlyError:
        return xmpp_template('post_readonly', post_id=post_id)
    except (PostAuthorError, SubscribeError):
        return xmpp_template('post_denied', post_id=post_id)

    return xmpp_template('msg_comment_sent', post_id=post_id,
                                             comment_id=comment_id)

def show_comment(post_id, comment_id):
    try:
        comment = posts.show_comment(post_id, comment_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except CommentNotFound:
        return xmpp_template('comment_not_found', post_id=post_id,
                                                  comment_id=comment_id)
    except PostAuthorError:
        return xmpp_template('post_denied', id=post_id)

    return xmpp_template('comment', post_id=post_id, comment_id=comment_id,
                                    to_comment_id=comment.to_comment_id,
                                    author=comment.author.login,
                                    text=comment.text, files=comment.files)

def delete_comment(post_id, comment_id):
    try:
        posts.delete_comment(post_id, comment_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except CommentNotFound:
        return xmpp_template('comment_not_found', post_id=post_id,
                                                  comment_id=comment_id)
    except CommentAuthorError:
        return xmpp_template('comment_del_denied', post_id=post_id,
                                                   comment_id=comment_id)
    return xmpp_template('comment_del', post_id=post_id,
                                        comment_id=comment_id)

def delete_last():
    try:
        item = posts.delete_last()
    except PostNotFound, e:
        return xmpp_template('post_not_found', post_id=e.post_id)
    except CommentNotFound, e:
        return xmpp_template('comment_not_found', post_id=e.post_id,
                                                  comment_id=e.comment_id)
    except PostAuthorError, e:
        return xmpp_template('post_del_denied', post_id=e.post_id)
    except CommentAuthorError, e:
        return xmpp_template('comment_del_denied', post_id=e.post_id,
                                                   comment_id=e.comment_id)
    if not item:
        return xmpp_template('nothing_to_del')
    if isinstance(item, Post):
        return xmpp_template('post_del', post_id=item.id)
    else:
        return xmpp_template('comment_del', post_id=item.post.id,
                                        comment_id=item.id)

def subscribe(post_id):
    try:
        post = posts.subscribe(post_id)
        cnt = post.comments_count()
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except (PostAuthorError, SubscribeError):
        return xmpp_template('post_denied', post_id=post_id)
    except AlreadySubscribed:
        return xmpp_template('post_sub_already', post_id=post_id)
    return xmpp_template('post_sub_ok', post_id=post_id, comments=cnt)

def unsubscribe(post_id):
    """Unsubscribe from certain post. 
    If user is not subscribed to this post, return "You are not subscribed 
    to #post_id", else return "You've sucessfully unsubscribed..."
    """
    try:
        if posts.check_subscribe_to(post_id):
            posts.unsubscribe(post_id)
            return xmpp_template('post_unsub_ok', post_id=post_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)
    return xmpp_template('post_not_subscribed', post_id=post_id)

def recommend(post_id, comment_id=None, text=None):
    try:
        try:
            posts.recommend(post_id, comment_id, text)
            return xmpp_template('recommendation_sent',
                                  post_id=post_id, comment_id=comment_id)
        except RecommendationExists:
            try:
                posts.unrecommend(post_id, comment_id)
                return xmpp_template('recommendation_cancel_sent',
                                      post_id=post_id, comment_id=comment_id)
            except RecommendationNotFound:
                pass
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except CommentNotFound:
        return xmpp_template('comment_not_found', post_id=post_id,
                                                  comment_id=comment_id)
    except PostReadonlyError:
        return xmpp_template('post_readonly', post_id=post_id)
    except RecommendationError:
        return xmpp_template('post_recommend_denied', post_id=post_id)
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)

def bookmarks(show=None, offset=None, limit=None):
    if offset:
        offset = int(offset)
    if limit:
        limit = int(limit)
    else:
        limit = 10

    plist = posts.bookmarks(offset=offset, limit=limit)
    plist.reverse()

    return xmpp_template('posts', posts=plist)
    #return 'bookmarks offset=%s limit=%s' % (offset, limit)

def bookmark(post_id, comment_id=None, text=None):
    try:
        try:
            posts.bookmark(post_id, comment_id, text)
            return xmpp_template('bookmark_sent',
                                  post_id=post_id, comment_id=comment_id)
        except BookmarkExists:
            posts.unbookmark(post_id, comment_id)
            return xmpp_template('bookmark_cancel_sent',
                                  post_id=post_id, comment_id=comment_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except CommentNotFound:
        return xmpp_template('comment_not_found', post_id=post_id,
                                                  comment_id=comment_id)
    except RecommendationError:
        return xmpp_template('post_bookmark_denied', post_id=post_id)
    except (PostAuthorError, SubscribeError):
        return xmpp_template('post_denied', post_id=post_id)


def pin_post(post_id):
    try:
        post = Post(id)
        if env.user.id == post.author.id:
            if not post.pinned:
                post.set_pinned(True)
                return xmpp_template('post_pinned', post_id=post_id)
            else:
                raise PostAlreadyPinnedError
        else:
            raise PostAuthorError
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)
    except PostAlreadyPinnedError:
        return xmpp_template('post_already_pinned', post_id=post_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)


def unpin_post(post_id):
    try:
        post = Post(id)
        if env.user.id == post.author.id:
            if post.pinned:
                post.set_pinned(False)
                return xmpp_template('post_unpinned', post_id=post_id)
            else:
                raise PostNotPinnedError
        else:
            raise PostAuthorError
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)
    except PostNotPinnedError:
        return xmpp_template('post_not_pinned', post_id=post_id)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)


def add_recipients(post_id, to):
    to = parse_logins(to)
    try:
        to_users = posts.add_recipients(post_id, to)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)
    except UserNotFound, e:
        return xmpp_template('user_not_found', login=e.message)
    except SubscribeError, e:
        return xmpp_template('user_post_denied', login=e.message)
    if to_users:
        return xmpp_template('rcpt_add', post_id=post_id, to_users=to_users)
    else:
        return xmpp_template('rcpt_add_already', post_id=post_id)

def del_recipients(post_id, to):
    to = parse_logins(to)
    try:
        posts.del_recipients(post_id, to)
    except PostNotFound:
        return xmpp_template('post_not_found', post_id=post_id)
    except PostAuthorError:
        return xmpp_template('post_denied', post_id=post_id)
    except UserNotFound, e:
        return xmpp_template('user_not_found', login=e.message)
    except SubscribeError, e:
        return xmpp_template('user_post_denied', login=e.message)
    return xmpp_template('rcpt_del', post_id=post_id, to_users=to)

