import os
import gevent
from gevent import monkey; monkey.patch_all()
from datetime import datetime

from point.util.queue import Queue
from point.util import proctitle
from geweb import log
from time import sleep

import settings

class FeedManager(object):
    def __init__(self):
        proctitle('feed-manager')
        log.info('FeedManager started with PID=%d' % os.getpid())

        self.fqueue = Queue('fqueue', settings.feed_queue_socket,
                            channels=False)

        #gevent.spawn(self.put_tasks)
        gevent.joinall([gevent.spawn(self.run)])

    def run(self):
        later = 0
        while True:
            gevent.sleep(later)
            later = self.put_tasks()

    def put_tasks(self):
        dstart = datetime.now()

        qname = 'fqueue:%02d%02d' % (dstart.hour, dstart.minute)
        queue = Queue(qname, settings.feed_queue_socket,
                      blocking=False, channels=False)

        ids = []
        cnt = 0
        while True:
            data = queue.pop()
            if not data:
                break
            self.fqueue.push(data)
            if 'id' in data:
                ids.append(data['id'])
            cnt += 1

        dend = datetime.now()

        td = dend - dstart

        later = settings.feed_queue_update_timeout - td.seconds
        if later < 0:
            later = 0

        if cnt:
            log.info('put_tasks: %d tasks in %d sec for IDs: %s' % \
                     (cnt, td.seconds, str(ids)))
        #gevent.spawn_later(later, self.put_tasks)
        return later

if __name__ == '__main__':
    FeedManager()

