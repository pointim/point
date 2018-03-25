import settings

import sys
try:
    sys.path.extend(settings.libs)
except AttributeError:
    pass

from multiprocessing import Process

if __name__ == '__main__':
    from worker import ImgprocWorker
    for i in xrange(settings.workers - 1):
        p = Process(target=ImgprocWorker)
        p.start()
    ImgprocWorker()

