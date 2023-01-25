#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from .console import Console
import logging
from . import config

class Git():
    """
    Git commands
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def pull_core(self):
        """
        Pull core content
        """
        self.logger.info('Pulling core repository...')
        c = Console()
        cmd = 'cd "%s"; git pull -q' % config.REPO_DIR
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60)
        self.logger.debug('Pull resp: %s' % resp)
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while pulling repository: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        if not os.path.exists(os.path.join(config.REPO_DIR, 'modules')):
            os.mkdir(os.path.join(config.REPO_DIR, 'modules'))

        self.logger.info('Done')
        return True

    def clone_core(self):
        """
        Clone core content from official repository
        """
        # clone repo
        self.logger.info('Cloning core repository...')
        c = Console()
        url = config.REPO_URL
        cmd = 'git clone -q "%s" "%s"' % (url, config.REPO_DIR)
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60)
        self.logger.debug('Clone resp: %s' % resp)
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while cloning repository: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False
        
        if not os.path.exists(os.path.join(config.REPO_DIR, 'modules')):
            os.mkdir(os.path.join(config.REPO_DIR, 'modules'))

        self.logger.info('Done')
        return True

    def pull_mod(self, module):
        """
        Pull module content

        Args:
            module (string): module name
        """
        self.logger.info('Pulling "%s" module repository...' % module)
        c = Console()
        module_path = os.path.join(config.MODULES_SRC, module)
        cmd = 'cd "%s"; git pull -q' % (module_path)
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60)
        self.logger.debug('Pull resp: %s' % resp)
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while pulling "%s" mod repository: %s' % (module, 'killed' if resp['killed'] else resp['stderr']))
            return False

        self.logger.info('Done')
        return True

    def clone_mod(self, module):
        """
        Clone core content from official repository

        Args:
            module (string): module name
        """
        self.logger.info('Cloning "%s" module repository...' % module)
        c = Console()
        url = config.MODULES_REPO_URL[module]
        module_path = os.path.join(config.MODULES_SRC, module)
        cmd = 'git clone -q "%s" "%s"' % (url, module_path)
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60)
        self.logger.debug('Clone resp: %s' % resp)
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while cloning "%s" mod repository: %s' % (module, 'killed' if resp['killed'] else resp['stderr']))
            return False
        
        self.logger.info('Done')
        return True

