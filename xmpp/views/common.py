# -*- coding: utf-8 -*-
"""
Common commands (uncategorized).
"""
import settings
import os.path
from contextlib import closing
from point.util.env import env

DEF_HELP = 'Help is temporarily available here: http://point.im/help/commands.'

def show_help():
    if env.user and env.user.id:
        _lang = env.user.get_profile('lang')
    else:
        _lang = settings.lang

    template_path = settings.template_path
    help_file = os.path.join(template_path, _lang, "help.txt")
    help_msg = ""
    if not os.path.exists(help_file):
        return DEF_HELP
    try:
        with closing(open(help_file)) as f:
            help_msg = f.read()
            return help_msg
    except Exception as e:
        return DEF_HELP

def ping():
    return {'body': 'Pong.', '_presence': True}

