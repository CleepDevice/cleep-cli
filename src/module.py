#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import click
from console import Console
import logging
import config

@click.group()
def mod():
    pass

@mod.command()
@click.option('--mod', required=True, help='Module name.')
def modsync(mod):
    """
    Copy specified module content to valid execution location
    """
    if not os.path.exists(os.path.join(config.MODULES_SRC, mod)):
        sys.exit('Module "%s" doesn\'t exist [%s]' % (mod, os.path.join(config.MODULES_SRC, mod)))

    if not os.path.exists(os.path.join(config.MODULES_DST, mod)):
        os.mkdir(os.path.join(config.MODULES_DST, mod))

    mod_backend_src = os.path.join(config.MODULES_SRC, mod, 'backend/')
    mod_backend_dst = os.path.join(config.MODULES_DST, mod)
    mod_frontend_src = os.path.join(config.MODULES_SRC, mod, 'frontend/')
    mod_frontend_dst = os.path.join(config.MODULES_HTML_DST, mod)
    mod_scripts_src = os.path.join(config.MODULES_SRC, mod, 'scripts/')
    mod_scripts_dst = os.path.join(config.MODULES_SCRIPTS_DST, mod)

    c = Console()
    cmd = """
if [ -d "%(BACKEND_SRC)s" ]; then
    rsync -av "%(BACKEND_SRC)s" "%(BACKEND_DST)s"
fi
if [ -d "%(FRONTEND_SRC)s" ]; then
    rsync -av "%(FRONTEND_SRC)s" "%(FRONTEND_DST)s"
fi
if [ -d "%(SCRIPTS_SRC)s" ]; then
    rsync -av "%(SCRIPTS_SRC)s" "%(SCRIPTS_DST)s"
fi
    """ % {
        'BACKEND_SRC': mod_backend_src, 'BACKEND_DST': mod_backend_dst,
        'FRONTEND_SRC': mod_frontend_src, 'FRONTEND_DST': mod_frontend_dst,
        'SCRIPTS_SRC': mod_scripts_src, 'SCRIPTS_DST': mod_scripts_dst
    }
    logging.debug('modsync resp: %s' % cmd)
    resp = c.command(cmd, 15)
    if resp['error'] or resp[u'killed']:
        logging.error(u'Error occured while sync module content: %s' % (u'killed' if resp[u'killed'] else resp[u'stderr']))


