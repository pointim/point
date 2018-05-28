from elasticsearch import Elasticsearch
#import dateutil.parser

try:
    import re2 as re
except ImportError:
    import re

import settings

def search_posts(text, user=None, private=None, bookmarks=False,
                 offset=0, limit=20):
    text = re.sub(r'[\(\)\[\]\{\}!?\\/]+', ' ', text).strip()

    es = Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)

    body = {
        'query': {
            'filtered': {
                'filter': {
                    'term': {
                        'private': False
                    }
                },
                'query': {
                    'query_string': {
                        'fields': ['text', 'tags'],
                        'query': text,
                        #'analyze_wildcard': True
                    }
                }
            }
        },
        #'sort': [{'created': {'order': 'desc'}}],
        'highlight': {
            'fields': {
                'text': {
                    'pre_tags': ['**'], 'post_tags': ['**'],
                    'number_of_fragments': 2,
                    'fragment_size': 200,
                }
            }
        }
    }

    res = es.search(index='point-posts,point-comments',
                    from_=offset, size=limit+1, body=body)

    results = _plist(res)
    #results = res['hits']['hits']
    has_next = len(results) > limit
    total = res['hits']['total']
    #from pprint import pprint
    #pprint(res)

    return results[:limit], has_next, total

def _plist(res):
    def _p(res):
        for r in res['hits']['hits']:
            item = { key: r['_source'][key] \
                     for key in ['login', 'created', 'private', 'post_id'] }

            #item['created'] = dateutil.parser.parse(item['created'])

            try:
                item['comment_id'] = r['_source']['comment_id']
            except KeyError:
                pass

            try:
                item['tags'] = r['_source']['tags']
            except KeyError:
                pass

            try:
                item['title'] = r['_source']['title']
            except KeyError:
                pass

            try:
                item['text'] = '... '.join(r['highlight']['text'])
            except KeyError:
                item['text'] = r['_source']['text']

            yield item

    return list(_p(res))
