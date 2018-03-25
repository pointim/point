# -*- coding: UTF-8 -*-

import os
from jinja2 import environmentfilter
from urllib import unquote_plus
from hashlib import md5
# from point.util.env import env
from point.core.user import User, UserNotFound
from point.util import cache_get, cache_store
from point.util.imgproc import imgproc_url
from point.util.md import CodeBacktick, SharpHeader, QuoteBlock, UrlColons, \
                          StrikePattern, ColonLinkPattern
# from geweb import log
from markdown import Markdown
from markdown.inlinepatterns import Pattern, LINK_RE
from markdown.util import etree
from point.util.unique_footnotes import UniqueFootnoteExtension
from xml.sax.saxutils import escape
from random import shuffle

try:
    import re2 as re
except ImportError:
    import re

import settings

class UserLinkPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, r'(?<!\w)\@(?P<u>[a-zA-Z0-9\-]+)')

    def handleMatch(self, m):
        try:
            User('login', m.group('u'))
        except UserNotFound:
            return #'@'+m.group('u')
        a = etree.Element('a')
        a.set('href', '//%s.%s/' % (m.group('u'), settings.domain))
        a.set('class', 'user')
        a.text = m.group('u')
        return a

class PostLinkPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, ur'(?<!\w|\/)\u0005?#(?P<p>[a-zA-Z]+)(?:[/.](?P<c>\d+))?')

    def handleMatch(self, m):
        a = etree.Element('a')
        if m.group('c'):
            a.set('href', '//%s/%s#%s' % (settings.domain, m.group('p'), m.group('c')))
            a.text = '#%s/%s' % (m.group('p'), m.group('c'))
        else:
            a.set('href', '//%s/%s' % (settings.domain, m.group('p')))
            a.text = '#%s' % m.group('p')
        a.set('class', 'post')
        return a


class CommentLinkPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, ur'(?<![-\w.]|/)\u0005?(?<=\()?/(?P<c>\d+)(?=[.,;:?!)]|(?:\s|$))')
        # Pattern.__init__(self, ur'(?=\a|\s)/(?P<c>\d+)')

    def handleMatch(self, m):
        a = etree.Element('a')
        if m.group('c') == '0':
            a.set('href', '#')
        else:
            a.set('href', '#%s' % m.group('c'))
        a.text = '/%s' % m.group('c')
        a.set('class', 'post')
        return a


class UrlPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, ur'(?P<url>(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[^\s\?\u0002\u0003]*)*)(?P<qs>\?[^#\s\u0002\u0003]*)?(?:#(?P<hash>\S+))?)')

    def handleMatch(self, m):
        url = m.group('url')

        imgm = re.search(r'\.(?P<ext>jpe?g|png|gif)((:|%3a)large)?$', m.group('path'), re.I)
        if (imgm \
        or re.search("^https?://ompldr.org/v[A-Z][a-zA-Z0-9]+$", url, re.I) \
        or url.startswith("http://img.leprosorium.com") \
        or url.startswith("http://pics.livejournal.com/")) \
        and not re.search(r'^https?://(www\.)?dropbox.com', url, re.I):
            wrap = etree.Element('div')
            wrap.set('class', 'clearfix')
            a = etree.SubElement(wrap, 'a')
            a.set('href', url)
            if imgm and imgm.group('ext').lower() == 'gif':
                a.set('class', 'postimg gif')
            else:
                a.set('class', 'postimg')
            img = etree.SubElement(a, 'img')
            img.set('src', imgproc_url(re.sub(r'%3alarge', ':large', url, re.I)))

            return wrap

        # dropbox
        if re.search(r'https?://(www\.)?dropbox.com', url, re.I):
            wrap = etree.Element('div')
            wrap.set('class', 'clearfix')
            a = etree.SubElement(wrap, 'a')
            a.set('href', url)
            if imgm and imgm.group('ext').lower() == 'gif':
                a.set('class', 'postimg gif')
            else:
                a.set('class', 'postimg')

            img = etree.SubElement(a, 'img')
            img.set('src', '%s://dl.dropboxusercontent.com%s' % (m.group('proto'), m.group('path')))

            return wrap

        # vimeo
        um = re.search("(?:https?://)?(?:(?:www\.)?vimeo\.com\/(?P<id>[\d-]+))", url, re.I)
        if um:
            wrap = etree.Element('div')
            wrap.set('class', 'clearfix')
            iframe = etree.SubElement(wrap, 'iframe')
            iframe.set('src', ('https://player.vimeo.com/video/%s?'
                               'title=0&amp;byline=0&amp;portrait=0'
                               '&amp;color=999999') % (um.group('id')))
            iframe.set('frameborder', '0')
            return wrap

        # youtube iframe
        um = re.search("(?:youtube\.com\/watch\?v=(?P<id1>[\w-]+)(?:&(?P<params>.+))?)|(youtu.be/(?P<id2>[\w-]+))", url, re.I)
        if um:
            if um.group('id1'):
                _id = um.group('id1')
                # _params = um.group('params') or ''
            else:
                _id = um.group('id2')
                # _params = ''

            #wrap = etree.Element('div')
            #wrap.set('class', 'iframe-wrap')
            #iframe = etree.SubElement(wrap, 'iframe')
            #iframe.set('src', 'http://www.youtube.com/embed/%(id)s#%(params)s' %\
            #                  {'id': _id, 'params': _params})
            #iframe.set('width', '500')
            #iframe.set('height', '401')
            #iframe.set('frameborder', '0')
            #iframe.set('allowfullscreen', 'allowfullscreen')
            #return wrap

            wrap = etree.Element('div')
            wrap.set('class', 'clearfix')
            a = etree.SubElement(wrap, 'a')
            a.set('href', url)
            a.set('target', '_blank')
            a.set('class', 'postimg youtube')
            img = etree.SubElement(a, 'img')
            img.set('src', 'https://img.youtube.com/vi/%s/hqdefault.jpg' % _id)
            return wrap

        # prostopleer track
        um = re.search("(?:(?:www\.)?prostopleer\.com\/tracks\/)(?:\/.+|\/|)(?P<id>[\w-]+)(?:\/|)", url, re.I)
        if um:
            obj = etree.Element('object')
            obj.set('width', '411')
            obj.set('height', '28')
            param = etree.SubElement(obj, 'param')
            param.set('name', 'movie')
            param.set('value', 'http://embed.prostopleer.com/track?id=%s' % \
                               um.group('id'))
            embed = etree.SubElement(obj, 'embed')
            embed.set('src', 'http://embed.prostopleer.com/track?id=%s' % \
                             um.group('id'))
            embed.set('type', 'application/x-shockwave-flash')
            embed.set('width', '411')
            embed.set('height', '28')
            return obj

        # prostopleer playlist
        um = re.search("(?:(?:www\.)?prostopleer\.com\/list)(?:\/.+|\/|)(?P<id>[\w-]+)(?:\/|)", url, re.I)
        if um:
            obj = etree.Element('object')
            obj.set('width', '419')
            obj.set('height', '115')
            param = etree.SubElement(obj, 'param')
            param.set('name', 'movie')
            param.set('value', 'http://embed.prostopleer.com/list?id=%s' % \
                               um.group('id'))
            embed = etree.SubElement(obj, 'embed')
            embed.set('src', 'http://embed.prostopleer.com/list?id=%s' % \
                             um.group('id'))
            embed.set('type', 'application/x-shockwave-flash')
            embed.set('width', '419')
            embed.set('height', '115')
            return obj

        # point post links
        um = re.search(r'https?://(?:[a-z0-9-]+\.)?%s/(?P<p>[a-z]+)(?:#(?P<c>\d+))?$' % settings.domain, url, re.I)
        if um:
            t = '#'+um.group('p')
            if um.group('c'):
                t += '/' + um.group('c')
                a = etree.Element('a')
                a.set('href', url)
                if um.group('c'):
                    a.text = '#%s/#%s' % (um.group('p'), um.group('c'))
                else:
                    a.text = '#%s' % um.group('p')
                return a

        text = unquote_plus(url.encode('utf-8', 'ignore')).decode('utf-8', 'ignore')
        if len(text) > 50:
            text = '%s...%s' % (text[:27], text[-20:])

        a = etree.Element('a')
        a.set('href', url)
        a.set('rel', 'nofollow')
        a.text = text
        return a

class WordWrap(Pattern):
    def __init__(self):
        Pattern.__init__(self, r'(?P<word>\S{81,})')

    def handleMatch(self, m):
        return re.sub(r'\S{80}', lambda w: '%s '%w.group(0), m.group('word'))

class WebSpoiler(Pattern):
    def __init__(self):
        Pattern.__init__(self, r'(%{2})(?P<contents>.+?)\2')

    def handleMatch(self, m):
        el_cont = etree.Element('span')
        el_cont.set('class', 'spoiler-container')
        el = etree.Element('span')
        el.set('class', 'spoiler')
        el.text = m.group('contents')
        el_cont.append(el)
        return el_cont

# создаем собственный класс уникальных сносок
unique_footnotes = UniqueFootnoteExtension()
md = Markdown(extensions=['nl2br',unique_footnotes,'codehilite(guess_lang=False)', 'toc'],
              safe_mode='escape')

md.preprocessors.add('cbacktick', CodeBacktick(md), '_begin')
md.preprocessors.add('sharp', SharpHeader(md), '>cbacktick')
md.preprocessors.add('quoteblock', QuoteBlock(md), '>sharp')
md.preprocessors.add('urlcolons', UrlColons(md), '>quoteblock')

md.inlinePatterns.add('url', UrlPattern(), '>automail')
md.inlinePatterns.add('user', UserLinkPattern(), '>url')
md.inlinePatterns.add('post', PostLinkPattern(), '>user')
md.inlinePatterns.add('comment', CommentLinkPattern(), '>post')
md.inlinePatterns.add('strike', StrikePattern(), '>comment')
md.inlinePatterns.add('spoiler', WebSpoiler(), '>strike')
md.ESCAPED_CHARS.append('%')
# replace native LinkPattern 
md.inlinePatterns['link'] = ColonLinkPattern(LINK_RE, md)


@environmentfilter
def markdown_filter(environ, text, post=None, comment=None, img=False):
    if not text:
        return ''

    if settings.cache_markdown:
        key = 'md:'
        if post:
            key = '%s%s' % (key, post)

            if comment:
                key = '%s.%s' % (key, comment)

        else:
            key = '%s%s' % (key, md5(text.encode('utf-8')).hexdigest())

        mdstring = cache_get(key)

        if mdstring:
            return mdstring

    mdstring = md.convert(text)
    # метод reset() вызывается, чтобы сбросить определение сносок из  
    # экземпляра класса, иначе уже имеющиеся сноски попадут во все следующие 
    # сконвертированные фрагменты HTML как сказано в 
    # https://pythonhosted.org/Markdown/extensions/api.html#registerextension
    md.reset()

    if settings.cache_markdown:
        cache_store(key, mdstring, settings.cache_markdown)
    return mdstring

_nl_re = re.compile(r'[\r\n]+')

@environmentfilter
def nl2br(environ, text):
    return ''.join(['<p>%s</p>' % escape(s) for s in re.split(_nl_re, text)])

@environmentfilter
def shuffle_filter(environ, array, limit=None):
    shuffle(array)
    if limit:
        return array[:limit]
    return array

@environmentfilter
def basename(environ, path):
    return os.path.basename(path)

filters = {
    'markdown': markdown_filter,
    'nl2br': nl2br,
    'shuffle': shuffle_filter,
    'basename': basename
}
