import settings

import sys
try:
    sys.path.extend(settings.libs)
except AttributeError:
    pass

from optparse import OptionParser
from multiprocessing import Process

def run_manager():
    from feedmanager import FeedManager
    FeedManager()

def run_workers():
    from worker import FeedWorker
    for i in xrange(settings.workers):
        p = Process(target=FeedWorker)
        p.start()

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-w', '--workers', action='store_true', dest='workers',
                      default=False, help='Run workers')
    parser.add_option('-m', '--manager', action='store_true', dest='manager',
                      default=False, help='Run queue manager')

    (options, args) = parser.parse_args()

    if options.workers:
        run_workers()

    if options.manager:
        run_manager()

