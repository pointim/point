# -*- coding: UTF-8 -*-

from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import Pattern, LinkPattern
from markdown.util import etree

try:  
    from urllib.parse import urlparse, urlunparse
except ImportError:
    from urlparse import urlparse, urlunparse

try:
    import re2 as re
except ImportError:
    import re

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
                    if m.group('lang'):
                        yield '    #!%s\r' % m.group('lang')
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

class QuoteBlock(Preprocessor):
    def run(self, lines):
        qblock = False
        for l in lines:
            if l.startswith('>'):
                qblock = True

            elif qblock:
                qblock = False
                if l.strip():
                    yield '\r'

            yield l

        if qblock:
            yield '\r'

class SharpHeader(Preprocessor):
    def run(self, lines):
        return [u"\u0005%s" % l if re.match(r'^#+[a-z]', l) else l for l in lines]

class UrlColons(Preprocessor):
    url_re = re.compile(
        ur'(?P<scheme>((\w+)://))'
        ur'(?P<pass>(\S+(?::\S*)?@)?)' 
        ur'(?P<authority>([^/?#]*)?)'
        ur'(?P<undef>([^?#]*)?)'
        ur'(?P<query>(\?([^#]*))?)'
        ur'(?P<fragment>(#(\S+))?)'
        , re.IGNORECASE)

    def replace(self, m):
        return '%s%s%s%s%s%s' % (m.group('scheme'),
            m.group('pass'),
            m.group('authority'),
            m.group('undef'),
            m.group('query'),
            re.sub(r':', '%3a', m.group('fragment')))

    def run(self, lines):
        for l in lines:
            yield re.sub(self.url_re, self.replace, l)


class StrikePattern(Pattern):
    def __init__(self):
        Pattern.__init__(self, ur'~~(?!~)(?P<text>.+?)~~')

    def handleMatch(self, m):
        s = etree.Element('s')
        s.text = m.group('text')
        return s


class ColonLinkPattern(LinkPattern):
    '''
    Redefine sanitize_url method of the standart LinkPattern class 
    because of Twitter use 'size' attribute in pics and other media 
    enitities (See https://dev.twitter.com/overview/api/entities-in-twitter-objects)
    '''
    def sanitize_url(self, url):
        if not self.markdown.safeMode:
            # Return immediately bipassing parsing.
            return url

        try:
            scheme, netloc, path, params, query, fragment = url = urlparse(url)
        except ValueError:
            # Bad url - so bad it couldn't be parsed.
            return ''

        locless_schemes = ['', 'mailto', 'news']
        allowed_schemes = locless_schemes + ['http', 'https', 'ftp', 'ftps']
        if scheme not in allowed_schemes:
            # Not a known (allowed) scheme. Not safe.
            return ''

        if netloc == '' and scheme not in locless_schemes:  # pragma: no cover
            # This should not happen. Treat as suspect.
            return ''

        for part in url[2:]:
            if ":" in part:
                # Check if this is just Twitter media link with 'size'
                colon_regex = re.compile('[/\w]*?\.(jpe?g|png|gif)(:large)?')
                if not colon_regex.match(part):
                    # If not -- a colon in "path", "parameters", "query"
                    # or "fragment" is suspect.
                    return ''

        # Url passes all tests. Return url as-is.
        return urlunparse(url)
