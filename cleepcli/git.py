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

    def pull_mod(self, module, branch):
        """
        Pull module content

        Args:
            module (string): module name
            branch (str): branch name
        """
        self.logger.info('Pulling "%s" module repository...' % module)
        c = Console()
        module_path = os.path.join(config.MODULES_SRC, module)

        if branch:
            cmd = f'cd "{module_path}"; git checkout "{branch}"'
            self.logger.debug('cmd: %s' % cmd)
            resp = c.command(cmd, 60)
            self.logger.debug('Checkout resp: %s' % resp)
            if resp['returncode'] != 0:
                self.logger.error('Error occured while checking out "%s" mod "%s": %s', module, branch, 'killed' if resp['killed'] else resp['stderr'])
                return False

        cmd = f'cd "{module_path}"; git pull -q'
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60)
        self.logger.debug('Pull resp: %s' % resp)
        if resp['returncode'] != 0:
            self.logger.error('Error occured while pulling "%s" mod repository: %s', module, 'killed' if resp['killed'] else resp['stderr'])
            return False

        self.logger.info('Done')
        return True

    def clone_mod(self, module, branch=None):
        """
        Clone core content from official repository

        Args:
            module (string): module name
            branch (str): branch name
        """
        self.logger.info('Cloning "%s" module repository...' % module)
        c = Console()
        url = config.MODULES_REPO_URL[module]
        module_path = os.path.join(config.MODULES_SRC, module)
        cmd = f'git clone -q "{url}" "{module_path}"'
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, timeout=60)
        self.logger.debug('Clone resp: %s' % resp)
        if resp['returncode'] != 0:
            self.logger.error('Error occured while cloning "%s" mod repository: %s' % (module, 'killed' if resp['killed'] else resp['stderr']))
            return False

        if branch:
            cmd = f'cd "{module_path}" && git checkout "{branch}"'
            self.logger.debug('cmd: %s' % cmd)
            resp = c.command(cmd, timeout=60)
            self.logger.debug('Checkout resp: %s' % resp)
            if resp['returncode'] != 0:
                self.logger.error('Error occured while checking out "%s" mod "%s": %s', module, branch, 'killed' if resp['killed'] else resp['stderr'])
                return False


        self.logger.info('Done')
        return True

