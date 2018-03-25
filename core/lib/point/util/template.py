import os
from jinja2 import Environment, TemplateNotFound, \
                   environmentfilter, FileSystemLoader
from xml.sax.saxutils import escape
from point.core.user import User, UserNotFound
from point.util import cache_get, cache_store, striphtml
from markdown import Markdown
from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import Pattern
from markdown.treeprocessors import Treeprocessor
from point.util.md import QuoteBlock, SharpHeader, UrlColons, StrikePattern
from markdown.util import etree
import urllib
from hashlib import md5

from geweb import log

from point.util.env import env

try:
    import re2 as re
except ImportError:
    import re

import settings

# Custom jinja2 template loader based on FileSystemLoader
class NewLineFileSystemLoader(FileSystemLoader):
    def get_source(self, environment, template):
        source, path, validator = FileSystemLoader.get_source(self, environment, template)
        if len(source) > 0 and source[0] != "\n":
            source = "\n" + source
        return source, path, validator

jinja_env = Environment(loader=NewLineFileSystemLoader(settings.template_path),
                        #extensions=['jinja2.ext.i18n'],
                        autoescape=True,
                        cache_size=-1)

def xmpp_template(tmpl_name, _lang=None, _type=None, **context):
    if not _lang:
        if env.user and env.user.id:
            _lang = env.user.get_profile('lang')
        else:
            _lang = settings.lang

    if not _type:
        try:
            if env.user and env.user.get_profile('xhtml'):
                _type = 'html'
        except KeyError:
            pass

    tmpl_dict = {}

    if _type == 'html':
        try:
            tmpl_path = os.path.join(_lang, 'xhtml', tmpl_name+'.tmpl')
            tmpl = jinja_env.get_template(tmpl_path)
            log.debug('Template %s' % tmpl_path)
            tmpl_dict['html'] = tmpl.render(context, settings=settings)
        except TemplateNotFound:
            tmpl_dict['html'] = None
            log.error('Template %s not found' % tmpl_path)
        finally:
            pass

    tmpl_path = os.path.join(_lang, 'text', tmpl_name+'.tmpl')
    tmpl = jinja_env.get_template(tmpl_path)
    tmpl_dict['body'] = tmpl.render(context, settings=settings)

    return tmpl_dict

def template(tmpl_name, _lang=settings.lang, **context):
    if not _lang:
        if env.user:
            _lang = env.user.get_profile('lang')
        else:
            _lang = settings.lang

    tmpl = jinja_env.get_template(os.path.join(_lang, tmpl_name))

    return tmpl.render(context, settings=settings, env=env)

link_template = 'xmpp:%s?message;type=chat;body=%%s' % settings.xmpp_jid

class CodeBacktick(Preprocessor):
    def run(self, lines):
        _code = False
        _cseq = ''

        for l in lines:
            m = re.match(r'^(?P<spaces>\s*)(?P<cseq>```|~~~)\s*(?P<lang>.*)$', l)
            if m:
                yield '\r'
                if not _code:
                    _code = True
                    _cseq = m.group('cseq')
                else:
                    if _cseq == m.group('cseq'):
                        _code = False
                        _cseq = ''
                    else:
                        yield l
                continue

            if _code:
                yield '    %s' % l
            else:
                yield l

class UserLinkPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, r'(?<!\w)\@(?P<u>[a-zA-Z0-9\-]+)')

    def handleMatch(self, m):
        try:
            User('login', m.group('u'))
        except UserNotFound:
            return #m.group(0)
        a = etree.Element('a')
        a.set('href', link_template % '@'+m.group('u'))
        a.set('style', 'color:#4488ff;font-weight:bold;text-decoration:none;')
        a.text = '@'+m.group('u')
        return a

class PostLinkPattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, ur'(?<!\w)\u0005?#(?P<p>[a-zA-Z]+)(?:[/.](?P<c>\d+))?')

    def handleMatch(self, m):
        a = etree.Element('a')
        a.set('style', 'color:#448844;font-weight:bold;text-decoration:none;')
        if m.group('c'):
            a.set('href', link_template % \
                          urllib.quote('#%s/%s' % (m.group('p'), m.group('c'))))
            a.text = '#%s/%s' % (m.group('p'), m.group('c'))
        else:
            a.set('href', link_template % \
                          urllib.quote('#%s' % m.group('p')))
            a.text = '#%s' % m.group('p')
        return a

class UrlPattern(Pattern):
    def __init__(self):
        #Pattern.__init__(self, r'(?P<url>(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[\w\.\-\~\+%]*)*)(?P<qs>\?([^#\s\u0002\u0003]*))?(?:\#(?P<hash>\S+))?)')
        Pattern.__init__(self, ur'(?P<url>(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[^\s\?\u0002\u0003]*)*)(?P<qs>\?[^#\s\u0002\u0003]*)?(?:#(?P<hash>\S+))?)')

    def handleMatch(self, m):
        url = m.group('url')

        text = url
        if len(text) > 80:
            text = '%s...%s' % (text[:40], text[-37:])

        a = etree.Element('a')
        a.set('href', url)
        a.text = text
        return a

class HeadersReplace(Treeprocessor):
    styles = {
        'h1': 'font-size:1.5em;color:#808080;font-weight:bold;',
        'h2': 'font-size:1.4em;color:#808080;font-weight:bold;',
        'h3': 'font-size:1.3em;color:#808080;font-weight:bold;',
        'h4': 'font-size:1.2em;color:#808080;font-weight:bold;',
        'h5': 'font-size:1.1em;color:#808080;font-weight:bold;',
        'h6': 'font-size:1em;color:#808080;font-weight:bold;',
    }
    def run(self, root):
        for tag, style in self.styles.iteritems():
            for elem in root.findall(tag):
                elem.tag = 'p'
                elem.set('style', style)

class TagStyles(Treeprocessor):
    styles = {
        'blockquote': 'color:#808080;font-style:italic;margin:.5em;',
    }
    def run(self, root):
        for tag, style in self.styles.iteritems():
            for elem in root.findall(tag):
                elem.set('style', style)

class CodePre(Treeprocessor):
    def run(self, root):
        def _line(line):
            line = re.sub('^( )+', lambda s: '&nbsp;' * len(s.group(0)), line)
            print '----- line', line
            return line

        for pre in root.findall('pre'):
            pre.tag = 'div'
            pre.set('style', 'white-space:pre;')
            pre.text = '<br/>'.join(map(_line, list(pre.itertext())))
            pre.findall('')

class XmppSpoiler(Pattern):
    def __init__(self):
        Pattern.__init__(self, r'(%{2})(?P<contents>.+?)\2')

    def handleMatch(self, m):
        el = etree.Element('spoiler', style='color:black; background-color:black;')
        el.text = m.group('contents')
        return el

class XmppSpoilerContentsSanitizer(Treeprocessor):
    def run(self, root):
        spoilers = root.findall('.//spoiler')
        for spoiler in spoilers:
            # force black color on links' text
            for link in spoiler.findall('.//a'):
                link.set('style', 'color:black; background-color:black;')
            # transform images inside links into text
            for img in spoiler.findall('.//a//img'):
                img.tag = 'span'
                img.set('style', 'color:black; background-color:black;')
                img.text = img.get('src')
                img.attrib.pop('src')
                img.attrib.pop('alt')
            # transform other images into links
            for img in spoiler.findall('.//img'):
                img.tag = 'a'
                img.set('style', 'color:black; background-color:black;')
                img.set('href', img.get('src'))
                img.attrib.pop('src')
                img.attrib.pop('alt')
                img.text = img.get('href')
            spoiler.tag = 'span'

md = Markdown(extensions=['nl2br'], safe_mode='escape')
# md = Markdown(extensions=['nl2br','footnotes'], safe_mode='escape')

md.preprocessors.add('backtick', CodeBacktick(md), '_begin')
md.preprocessors.add('sharp', SharpHeader(md), '>backtick')
md.preprocessors.add('quoteblock', QuoteBlock(md), '>sharp')
md.preprocessors.add('urlcolons', UrlColons(md), '>quoteblock')

md.treeprocessors.add('headersreplace', HeadersReplace(md), '_begin')
md.treeprocessors.add('tagstyles', TagStyles(md), '>headersreplace')
#md.treeprocessors.add('codepre', CodePre(md), '>tagstyles')
md.treeprocessors.add('spoiler_san', XmppSpoilerContentsSanitizer(md), '>inline')

md.inlinePatterns.add('url', UrlPattern(), '>automail')
md.inlinePatterns.add('user', UserLinkPattern(), '>url')
md.inlinePatterns.add('post', PostLinkPattern(), '>user')
md.inlinePatterns.add('strike', StrikePattern(), '>post')
md.inlinePatterns.add('spoiler', XmppSpoiler(), '>strike')
md.ESCAPED_CHARS.append('%')

# Template filters

@environmentfilter
def strftime(environment, t, s):
    if not t:
        return ''
    return t.strftime(s)
jinja_env.filters['strftime'] = strftime

urlre = re.compile('^(?P<proto>\w+)://(?:[\w\.\-%\:]*\@)?(?P<host>[\w\.\-%]+)(?::(?P<port>\d+))?(?P<path>(?:/[\w\.\-\+%:;]*)*)(?P<qs>\?([^#]*))?')

@environmentfilter
def xhtmlim(environment, s):
    if not s:
        return ''

    if settings.cache_markdown:
        h = md5(s.encode('utf-8')).hexdigest()
        mdstring = cache_get('mdx:%s' % h)

        if mdstring:
            return mdstring

    mdstring = md.convert(s)
    if settings.cache_markdown:
        cache_store('mdx:%s' % h, mdstring, 3600)

    return mdstring

jinja_env.filters['xhtmlim'] = xhtmlim

@environmentfilter
def striphtml_filter(environment, s):
    if not s:
        return ''

    if settings.cache_markdown:
        h = md5(s.encode('utf-8')).hexdigest()
        mdstring = cache_get('h2t:%s' % h)

        if mdstring:
            return mdstring

    mdstring = striphtml(s)
    if settings.cache_markdown:
        cache_store('h2t:%s' % h, mdstring, 3600)

    return mdstring

jinja_env.filters['striphtml'] = striphtml_filter

@environmentfilter
def quote(environment, text):
    return '\n'.join(map(lambda s: '> %s' % s,
                         filter(None, text.strip().split('\n'))))
jinja_env.filters['quote'] = quote

@environmentfilter
def xquote(environment, text):
    return '<br/>'.join(map(lambda s: '&gt; %s' % escape(s),
                         filter(None, text.strip().split('\n'))))
jinja_env.filters['xquote'] = xquote

@environmentfilter
def short(environment, text):
    if len(text) > 50:
        text = '%s...%s' % (text[:27], text[-20:])
    return text
jinja_env.filters['short'] = short

@environmentfilter
def basename(environ, path):
    return os.path.basename(path)
jinja_env.filters['basename'] = basename

@environmentfilter
def login_filter(environ, login, xhtml=False):
    login = login.strip()
    if not login.startswith('@'):
        login = '@%s' % login

    if xhtml:
        login = '<a href="xmpp:%s?message;type=chat;body=%s%%20" style="color:#4488ff; font-weight:bold; text-decoration:none;">%s</a>' % \
                (settings.xmpp_jid, login, login)

    return login
jinja_env.filters['login'] = login_filter

