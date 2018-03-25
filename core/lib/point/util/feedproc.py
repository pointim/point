from point.core.feed.exc import InvalidFeedType, FeedFetchError
from point.util import xhtmlim
from point.util.imgproc import imgproc_url
from geweb import log
import feedparser
from pytz import timezone
import dateutil.parser
from lxml import etree
from lxml.html.clean import clean_html, fromstring
from html2text import HTML2Text
from xml.sax.saxutils import unescape

try:
    import re2 as re
except ImportError:
    import re

import settings

class FeedProcessor(object):
    def __init__(self, url, fetch=True):
        self._url = url
        self._entries = []
        self._info = {}
        self._error = None

        if fetch:
            self.fetch()

    def fetch(self):
        if self._entries:
            return self._entries

        data = feedparser.parse(self.get_url())

        if 'bozo_exception' in data:
            self._error = data['bozo_exception']
            if 'entries' not in data or not data['entries']:
                if 'status' in data and data['status'] < 400:
                    raise InvalidFeedType
                else:
                    raise FeedFetchError

        self.process_info(data)

        self._entries = [self.process_entry(entry) for entry in data['entries']]

        return self._entries

    def get_error(self):
        return self._error

    def process_entry(self, entry):
        out = {'type': 'feed'}

        # UGnich - mooduck
        if entry['published'].endswith('UT'):
            entry['published'] = '%sC' % entry['published']

        tz = timezone(settings.timezone)
        try:
            out['created'] = \
               dateutil.parser.parse(entry['published']).astimezone(tz)
        except ValueError:
            entry['created'] = \
               dateutil.parser.parse(entry['published'])

        out['link'] = entry['link']
        out['title'] = re.sub(r'&#(?P<c>\d+);',
                              lambda c: unichr(int(c.group('c'))),
                              unescape(entry['title'])) \
                              if 'title' in entry else ''
        out['text'] = self.process_text(entry['summary'])
        out['tags'] = [ t['label'] or t['term'] for t in entry['tags'] ] \
                        if 'tags' in entry else []

        return out

    def process_info(self, data):
        if 'href' in data and data['href'] != self._url:
            self._url = data['href']

        self._info = {
            'name': data.feed['title'] if 'title' in data.feed else None,
            'about': data.feed['subtitle'] if 'subtitle' in data.feed else None,
            'homepage': data.feed['link'] if 'link' in data.feed else self._url
        }

    def get_info(self, param=None):
        if not self._info:
            self.fetch()
        if param:
            return self._info[param]
        return self._info

    def entries(self):
        return self._entries

    allowed_tags = ('p', 'img', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'div', 'span', 'blockquote', 'ul', 'ol', 'li')
    allowed_attrs = ('href', 'src',)
    forbidden_tags = ('script',)

    def _parse_element(self, elem):
        brcount = 0
        for child in elem.iterchildren():
            if child.tag.lower() == 'br':
                if brcount >= 1:
                    child.drop_tag()
                brcount += 1
                continue
            else:
                brcount = 0

            self._parse_element(child)

        tag = elem.tag.lower()

        if tag in self.forbidden_tags:
            elem.drop_tree()
            return

        if tag not in self.allowed_tags:
            elem.drop_tag()
            return

        for attr in elem.keys():
          if attr not in self.allowed_attrs and elem.get(attr):
              del elem.attrib[attr]

        #if elem.tag.lower() == 'img':
        #    src = elem.get('src')
        #    if src:
        #        elem.set('src', imgproc_url(src))
        #        div = etree.Element('div')
        #        div.set('class', 'clearfix')
        #        a = etree.SubElement(div, 'a')
        #        a.set('class', 'postimg')
        #        a.set('href', src)
        #        if elem.tail:
        #            p = etree.Element('p')
        #            p.text = elem.tail
        #            elem.tail = None
        #            elem.addnext(p)
        #        elem.addprevious(div)
        #        a.insert(0, elem)

    def process_text(self, text):
        try:
            tree = fromstring(clean_html(text))
        except etree.XMLSyntaxError:
            return xhtmlim(text)

        self._parse_element(tree)
        return html2md(etree.tostring(tree, method="xml", encoding=unicode))

    def get_url(self):
        return self._url

class IbigdanFeedProcessor(FeedProcessor):
    allowed_tags = ('p', 'img', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'span', 'blockquote', 'ul', 'ol', 'li')
    forbidden_tags = ('div', 'script',)

    def process_text(self, text):
        try:
            tree = fromstring(clean_html(text))
        except etree.XMLSyntaxError:
            return xhtmlim(text)

        rm = False
        for el in tree.iterchildren():
            if el.tag.lower() == 'a' and el.get('name').lower().startswith('cutid'):
                rm = True

            if rm:
                el.drop_tree()

        self._parse_element(tree)
        return html2md(etree.tostring(tree, method="xml", encoding=unicode))

class LorFeedProcessor(FeedProcessor):
    def process_entry(self, entry):
        out = super(LorFeedProcessor, self).process_entry(entry)

        out['tags'] = []

        tree = fromstring(entry['summary'])

        for el in tree.find_class('tags'):
            for t in el.find_class('tag'):
                out['tags'].append(t.text.strip())

        return out

    def process_text(self, text):
        try:
            tree = fromstring(clean_html(text))
        except etree.XMLSyntaxError:
            return xhtmlim(text)

        for el in tree.find_class('tags'):
            el.drop_tree()

        self._parse_element(tree)
        return html2md(etree.tostring(tree, method="xml", encoding=unicode))

processors = (
    (r'ibigdan\.livejournal\.com', IbigdanFeedProcessor),
    (r'linux\.org\.ru/section-rss.jsp', LorFeedProcessor),
)

def process(url):
    for regex, ProcClass in processors:
        if re.search(regex, url):
            log.debug('%s was chosen for %s' % (ProcClass.__name__, url))
            return ProcClass(url)
    return FeedProcessor(url)

def html2md(s):
    h2t = HTML2Text()
    h2t.body_width = 0
    #h2t.ignore_links = True
    #h2t.ignore_images = True
    s = h2t.handle(s)
    s = re.sub(r'\!?\[\]\((?P<url>.+?)\)', lambda m: " %s " % m.group('url'), s)
    return s

