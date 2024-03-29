#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from .console import Console
import logging
from . import config

class File():
    """
    Handle file operations
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def core_sync(self):
        """
        Synchronize core content between source and execution folders
        """
        # check vars
        if not config.CORE_DST:
            raise Exception('Cleep needs to be installed before using this command')

        c = Console()
        variables = {
            'REPO_DIR': config.REPO_DIR,
            'CORE_DST': config.CORE_DST,
            'HTML_DST': config.HTML_DST,
            'BIN_DST': config.BIN_DST,
            'MEDIA_DST': config.MEDIA_DST,
            'CONFIG_DIR': config.CONFIG_DIR,
        }
        cmd = """
mkdir -p "%(HTML_DST)s/"
mkdir -p "%(CORE_DST)s/modules"
mkdir -p "%(MEDIA_DST)s/modules"
mkdir -p "%(CONFIG_DIR)s"
rsync -av "%(REPO_DIR)s/cleep/" "%(CORE_DST)s/" --exclude "/tests/" --exclude "modules" --exclude "*__pycache__*" --delete --exclude "*.pyc" --keep-dirlinks
rsync -av "%(REPO_DIR)s/html/" "%(HTML_DST)s/" --delete --exclude "js/modules/" --exclude "*node_modules*"
rsync -av "%(REPO_DIR)s/bin/cleep" "%(BIN_DST)s/cleep"
rsync -av "%(REPO_DIR)s/medias/sounds" "%(MEDIA_DST)s/sounds/" --delete
    """ % variables
        self.logger.debug('Coresync cmd: %s' % cmd)
        resp = c.command(cmd, 15)
        self.logger.debug('Coresync stdout:\n%s' % '\n'.join(resp['stdout']))
        if resp['stderr']:
            self.logger.debug('Coresync stderr:\n%s' % '\n'.join(resp['stderr']))
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while sync core content: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        return True

    def module_sync(self, module_name):
        """ 
        Copy specified module content to valid execution location
        """
        if not os.path.exists(os.path.join(config.MODULES_SRC, module_name)):
            self.logger.error('Module "%s" doesn\'t exist [%s]' % (module_name, os.path.join(config.MODULES_SRC, module_name)))
            return False
    
        if not os.path.exists(os.path.join(config.MODULES_DST, module_name)):
            os.makedirs(os.path.join(config.MODULES_DST, module_name))

        mod_backend_src = os.path.join(config.MODULES_SRC, module_name, 'backend/')
        mod_backend_dst = os.path.join(config.MODULES_DST, module_name)
        mod_frontend_src = os.path.join(config.MODULES_SRC, module_name, 'frontend/')
        mod_frontend_dst = os.path.join(config.MODULES_HTML_DST, module_name)
        mod_scripts_src = os.path.join(config.MODULES_SRC, module_name, 'scripts/')
        mod_scripts_dst = os.path.join(config.MODULES_SCRIPTS_DST, module_name)

        c = Console()
        cmd = """ 
if [ -d "%(BACKEND_SRC)s" ]; then
    /bin/mkdir -p "%(BACKEND_DST)s"
    rsync -av "%(BACKEND_SRC)s" "%(BACKEND_DST)s" --delete --exclude "*.pyc" --exclude "*__pycache__*"
fi
if [ -d "%(FRONTEND_SRC)s" ]; then
    /bin/mkdir -p "%(FRONTEND_DST)s"
    rsync -av "%(FRONTEND_SRC)s" "%(FRONTEND_DST)s" --delete --exclude "*node_modules*"
fi
if [ -d "%(SCRIPTS_SRC)s" ]; then
    /bin/mkdir -p "%(SCRIPTS_DST)s"
    rsync -av "%(SCRIPTS_SRC)s" "%(SCRIPTS_DST)s" --delete --exclude "*__pycache__*"
fi
    """ % { 
            'BACKEND_SRC': mod_backend_src, 'BACKEND_DST': mod_backend_dst,
            'FRONTEND_SRC': mod_frontend_src, 'FRONTEND_DST': mod_frontend_dst,
            'SCRIPTS_SRC': mod_scripts_src, 'SCRIPTS_DST': mod_scripts_dst
        }
        self.logger.debug('Modsync cmd: %s' % cmd)
        resp = c.command(cmd, 15) 

        self.logger.debug('Modsync stdout:\n%s' % '\n'.join(resp['stdout']))
        if resp['stderr']:
            self.logger.debug('Modsync stderr:\n%s' % '\n'.join(resp['stderr']))
        if resp['error'] or resp[u'killed']:
            self.logger.error(u'Error occured while sync module content: %s' % (u'killed' if resp[u'killed'] else resp[u'stderr']))
            return False

        return True

    def module_run_install_scripts(self, module_name):
        """
        Run module installation scripts
        """
        if not os.path.exists(os.path.join(config.MODULES_SRC, module_name)):
            self.logger.error('Module "%s" doesn\'t exist [%s]' % (module_name, os.path.join(config.MODULES_SRC, module_name)))
            return False

        preinst_script = os.path.join(config.MODULES_SCRIPTS_DST, module_name, "preinst.sh")
        postinst_script = os.path.join(config.MODULES_SCRIPTS_DST, module_name, "postinst.sh")
        console = Console()

        if os.path.exists(preinst_script):
            self.logger.info('Running %s scripts', preinst_script)
            resp = console.command(preinst_script, timeout=300)
            if resp["returncode"] != 0:
                self.logger.error('Error running %s [%s]: %s', preinst_script, resp["returncode"], ''.join(resp["stderr"]))
                return False

        if os.path.exists(postinst_script):
            self.logger.info('Running %s scripts', postinst_script)
            resp = console.command(postinst_script, timeout=300)
            if resp["returncode"] != 0:
                self.logger.error('Error running %s [%s]: %s', postinst_script, resp["returncode"], ''.join(resp["stderr"]))
                return False

        return True
