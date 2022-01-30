#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import zipfile
import os
import glob
import re
import requests
import time
from . import config
from .console import Console
from .check import Check
import subprocess

class Ci():
    """
    Continuous Integration helpers
    """

    CLEEP_COMMAND_URL = 'http://127.0.0.1/command'
    CLEEP_CONFIG_URL = 'http://127.0.0.1/config'
    TESTS_REQUIREMENTS_TXT = 'tests/requirements.txt'

    def __init__(self):
        """
        Constructor
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    def mod_install_source(self, package_path, no_compatibility_check=False):
        """
        Install module package (zip archive) sources

        Args:
            package_path (string): package path
            no_compatitiblity_check (bool): do not check module compatibility (but only deps compat)

        Raises:
            Exception if error occured
        """
        # init
        (_, module_name, module_version) = os.path.basename(package_path).split('_')
        module_version = module_version.replace('.zip', '')[1:]
        self.logger.debug('Installing application %s v%s...' % (module_name, module_version))

        # perform some checkings
        if not module_version:
            raise Exception('Invalid package filename')
        if not re.match('\d+\.\d+\.\d+', module_version):
            raise Exception('Invalid package filename')
        console = Console()
        resp = console.command('file --keep-going --mime-type "%s"' % package_path)
        if resp['returncode'] != 0:
            raise Exception('Unable to check file validity')
        filetype = resp['stdout'][0].split(': ')[1].strip()
        self.logger.debug('Filetype=%s' % filetype)
        if filetype != 'application/zip\\012- application/octet-stream':
            raise Exception('Invalid application package file')

        # search for tests requirements.txt file
        has_tests_requirements = False
        with zipfile.ZipFile(package_path, 'r') as zp:
            for zfile in zp.infolist():
                if zfile.filename == self.TESTS_REQUIREMENTS_TXT:
                    zp.extract('tests/requirements.txt', path='/tmp')
                    has_tests_requirements = True
                    break

        try:
            # start cleep (non blocking)
            self.logger.info('Starting Cleep...')
            cleep_proc = subprocess.Popen(['cleep', '--noro'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(15)
            self.logger.info('Done')

            # make sure to have latest modules.json version
            self.logger.info('Updating applications list in Cleep')
            resp = requests.post(self.CLEEP_COMMAND_URL, json={
                'command': 'check_modules_updates',
                'to': 'update',
            })
            resp.raise_for_status()
            resp_json = resp.json()
            if resp_json['error']:
                raise Exception('Check_modules_updates command failed: %s' % resp_json)

            # install module in cleep (it will also install deps)
            self.logger.info('Installing "%s" application in Cleep' % module_name)
            resp = requests.post(self.CLEEP_COMMAND_URL, json={
                'command': 'install_module',
                'to': 'update',
                'params': {
                    'module_name': module_name,
                    'package': package_path,
                    'no_compatibility_check': no_compatibility_check,
                }
            })
            resp.raise_for_status()
            resp_json = resp.json()
            if resp_json['error']:
                raise Exception('Install_module command failed: %s' % resp_json)

            # wait until end of installation
            self.logger.info('Waiting end of application installation')
            while True:
                time.sleep(1.0)
                resp = requests.post(self.CLEEP_COMMAND_URL, json={
                    'command': 'get_modules_updates',
                    'to': 'update'
                })
                resp.raise_for_status()
                resp_json = resp.json()
                if resp_json['error']:
                    raise Exception('Get_modules_updates command failed')
                module_updates = resp_json['data'].get(module_name)
                self.logger.debug('Updates: %s' % module_updates)
                if not module_updates:
                    raise Exception('No "%s" application info in updates' % module_name)
                if module_updates['processing'] == False:
                    if module_updates['update']['failed']:
                        raise Exception('Application "%s" installation failed' % module_name)
                    break

            # restart cleep
            self.logger.info('Restarting cleep...')
            cleep_proc.kill()
            cleep_proc = subprocess.Popen(['cleep', '--noro'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(15)
            self.logger.info('Done')

            # check module is installed and running
            self.logger.info('Checking application is installed')
            resp = requests.post(self.CLEEP_CONFIG_URL)
            resp.raise_for_status()
            resp_json = resp.json()
            module_config = resp_json['modules'].get(module_name)
            if not module_config or not module_config.get('started'):
                self.logger.error('Found application config: %s' % module_config)
                raise Exception('Application "%s" installation failed' % module_name)
            self.logger.info('Application and its dependencies successfully installed')

            # install requirements.txt for tests
            if has_tests_requirements:
                self.logger.info('Install tests python dependencies')
                resp = console.command('python3 -m pip install --trusted-host pypi.org -r "%s"' % os.path.join('/tmp', self.TESTS_REQUIREMENTS_TXT), 900)
                self.logger.debug('Resp: %s' % resp)
                if resp['returncode'] != 0:
                    self.logger.error('Error installing tests requirements.txt: %s' , resp)
                    raise Exception('Error installing tests requirements.txt (killed=%s)' % resp['killed'])


        finally:
            if cleep_proc:
                cleep_proc.kill()

    def mod_check(self, module_name):
        """
        Perform some checkings (see check.py file) for continuous integration

        Args:
            module_name (string): module name

        Raises:
            Exception if error occured
        """
        check = Check()

        check.check_backend(module_name)
        check.check_frontend(module_name)
        check.check_scripts(module_name)
        check.check_tests(module_name)

