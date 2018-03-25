import logging

import settings

levels = {
    'error': logging.ERROR,
    'warn': logging.WARN,
    'info': logging.INFO,
    'debug': logging.DEBUG
}
level = levels[settings.loglevel.lower()]

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                    filename=settings.logfile, level=level)

_log = logging.getLogger(settings.logger)

def info(msg):
    _log.info(msg)

def error(msg):
    _log.error(msg)

def warn(msg):
    _log.warn(msg)

def debug(msg):
    _log.debug(msg)

