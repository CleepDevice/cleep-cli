#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
try:
    import cleep
except:
    class cleep:
        __file__ = None

DEFAULT_MODULES = ['system', 'parameters', 'cleepbus', 'audio', 'network', 'update']
MODULES_REPO_URL = {
    'system': 'https://github.com/CleepDevice/cleepapp-system.git',
    'parameters': 'https://github.com/CleepDevice/cleepapp-parameters.git',
    'cleepbus': 'https://github.com/CleepDevice/cleepapp-cleepbus.git',
    'audio': 'https://github.com/CleepDevice/cleepapp-audio.git',
    'network': 'https://github.com/CleepDevice/cleepapp-network.git',
    'update': 'https://github.com/CleepDevice/cleepapp-update.git',
}

GITHUB_ORG = 'CleepDevice'
GITHUB_REPO = 'cleep'
GITHUB_DOCS_BRANCH = 'docs'

REPO_URL = 'https://github.com/CleepDevice/cleep.git'
REPO_DIR = os.environ.get('REPO_DIR', '/root/cleep-dev')

CORE_SRC = '%s/cleep' % REPO_DIR
CORE_DST = os.path.dirname(cleep.__file__) if cleep.__file__ else None

HTML_SRC = '%s/html' % REPO_DIR
HTML_DST = '/opt/cleep/html'

MODULES_SRC = '%s/modules' % REPO_DIR
MODULES_DST = '%s/modules' % CORE_DST
MODULES_HTML_DST = '%s/js/modules' % HTML_DST
MODULES_SCRIPTS_DST = '/opt/cleep/scripts'

BIN_SRC = '%s/bin' % REPO_DIR
BIN_DST = '/usr/bin'

MEDIA_SRC = '%s/medias' % REPO_DIR
MEDIA_DST = '/opt/cleep'

