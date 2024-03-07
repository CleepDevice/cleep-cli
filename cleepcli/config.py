#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from importlib.machinery import SourceFileLoader
try:
    import cleep
except:
    class cleep:
        # fallback to supposed cleep installation path
        __path__ = ['/usr/lib/python3/dist-packages/cleep']

def get_core_version_from_sources(repo_dir):
    try:
        cleep_sources = SourceFileLoader("cleep_sources", os.path.join(repo_dir, 'cleep', '__init__.py')).load_module()
        return cleep_sources.__version__
    except:
        return None

MODULES_REPO_URL = {
    'system': 'https://github.com/CleepDevice/cleepapp-system.git',
    'parameters': 'https://github.com/CleepDevice/cleepapp-parameters.git',
    'cleepbus': 'https://github.com/CleepDevice/cleepapp-cleepbus.git',
    'audio': 'https://github.com/CleepDevice/cleepapp-audio.git',
    'network': 'https://github.com/CleepDevice/cleepapp-network.git',
    'update': 'https://github.com/CleepDevice/cleepapp-update.git',
}
DEFAULT_MODULES = list(MODULES_REPO_URL.keys())

GITHUB_ORG = 'CleepDevice'
GITHUB_REPO = 'cleep'
GITHUB_REPO_DOCS = 'cleep-docs'
GITHUB_REPO_APP_DOCS = "cleep-app-docs"

REPO_URL = 'https://github.com/CleepDevice/cleep.git'
REPO_DIR = os.environ.get('REPO_DIR', '/root/cleep-dev')

CORE_SRC = '%s/cleep' % REPO_DIR
CORE_DST = cleep.__path__[0] if cleep.__path__ else None

HTML_SRC = '%s/html' % REPO_DIR
HTML_DST = '/opt/cleep/html'

MODULES_SRC = '%s/modules' % REPO_DIR
MODULES_DST = '/opt/cleep/modules'
MODULES_HTML_DST = '%s/js/modules' % HTML_DST
MODULES_SCRIPTS_DST = '/opt/cleep/scripts'

BIN_SRC = '%s/bin' % REPO_DIR
BIN_DST = '/usr/bin'

MEDIA_SRC = '%s/medias' % REPO_DIR
MEDIA_DST = '/opt/cleep'

DOCS_AUTHOR = 'CleepDevice'
DOCS_PROJECT_NAME = 'Cleep core'

CORE_VERSION = get_core_version_from_sources(REPO_DIR)

CONFIG_DIR = '/etc/cleep'
