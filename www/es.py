#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import settings

try:
    sys.path.extend(settings.libs)
except AttributeError:
    pass

import elasticsearch
import geweb.db.pgsql as db
from point.util import b26
from pprint import pprint
#es = elasticsearch.Elasticsearch()
es = Elasticsearch(host=settings.elasticsearch_host, port=settings.elasticsearch_port)

def indices():
    idx_settings = {
        "settings" : {
            "analysis" : {
                "analyzer" : {
                    "my_analyzer" : {
                        "tokenizer" : "standard",
                        "filter": ["lowercase", "russian_morphology",
                                   "english_morphology", "my_stopwords"]
                    }
                },
                "filter": {
                    "my_stopwords": {
                        "type": "stop",
                        "stopwords": u"а,без,более,бы,был,была,были,было,быть,в,вам,вас,весь,во,вот,все,всего,всех,вы,где,да,даже,для,до,его,ее,если,есть,еще,же,за,здесь,и,из,или,им,их,к,как,ко,когда,кто,ли,либо,мне,может,мы,на,надо,наш,не,него,нее,нет,ни,них,но,ну,о,об,однако,он,она,они,оно,от,очень,по,под,при,с,со,так,также,такой,там,те,тем,то,того,тоже,той,только,том,ты,у,уже,хотя,чего,чей,чем,что,чтобы,чье,чья,эта,эти,это,я,a,an,and,are,as,at,be,but,by,for,if,in,into,is,it,no,not,of,on,or,such,that,the,their,then,there,these,they,this,to,was,will,with"
                    }
                }
            }
        },
        "mappings" : {
            "post": {
                "_all": {"analyzer": "russian_morphology"},
                "properties": {
                    "text": {"type": "string", "analyzer": "russian_morphology"}
                }
            }
        }
    }

    for idx in ['point-posts', 'point-comments']:
        try:
            es.indices.delete(index=idx)
        except elasticsearch.exceptions.NotFoundError:
            pass
        es.indices.create(index=idx, body=idx_settings)

def index_posts():
    res = db.fetchall("SELECT u.id user_id, u.login, p.id post_id, "
                      "p.type post_type, "
                      "p.title, p.tags, p.text, p.created, p.private "
                      "FROM posts.posts p "
                      "JOIN users.logins u ON p.author=u.id;")
    for r in res:
        post = dict(r)
        post['post_id'] = b26(post['post_id'])
        _id = post['post_id']

        es.index(index='point-posts', id=_id,
                 doc_type='post', body=post)

def index_comments():
    res = db.fetchall("SELECT u.id user_id, u.login, c.post_id, "
                      "p.type post_type, "
                      "c.comment_id, c.text, c.created, p.private "
                      "FROM posts.comments c "
                      "JOIN users.logins u ON c.author=u.id "
                      "JOIN posts.posts p ON p.id=c.post_id;")
    for r in res:
        c = dict(r)
        c['post_id'] = b26(c['post_id'])
        _id = '%s-%s' % (c['post_id'], c['comment_id'])

        es.index(index='point-comments', id=_id,
                 doc_type='post', body=c)

def search(text, offset=0, limit=10):
    res = es.search(from_=offset, size=limit, body={
        #'from': offset,
        #'size': limit,
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
                        'query': text
                    }
                }
            }
        },
        'sort': [{'created': {'order': 'desc'}}],
        'highlight': {
            'fields': {
                'text': {
                    'pre_tags': ['<b class="pre">'], 'post_tags': ['</b>'],
                    'number_of_fragments': 1,
                    'fragment_size': 150,
                }
            }
        }
    })
    pprint(res)
    print 'LEN', len(res['hits']['hits'])

indices()
index_posts()
index_comments()
#search(u'хуй', 0, 3)
