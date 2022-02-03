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
    CLEEP_HEALTH_URL = 'http://127.0.0.1/health'
    TESTS_REQUIREMENTS_TXT = 'tests/requirements.txt'
    EXTRACT_DIR = '/tmp/extract'
    APP_FILENAME_PATTERN = 'APP_FILENAME=[\'"](.*)[\'"]'

    def __init__(self):
        """
        Constructor
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    def mod_check_package(self, package_path):
        """
        Check specified package content

        Args:
            package_path (string): package path
            
        Returns:
            dict: package informations::

            {
                module_name (str): module name
                module_version (str): module version
                has_tests_requirements (bool): True if tests/requirements.txt exists
            }

        Raises:
            Exception if something bad detected
        """
        self.logger.info('Checking application package "%s"' % package_path)
        (_, module_name, module_version) = os.path.basename(package_path).split('_')
        module_version = module_version.replace('.zip', '')[1:]

        # check raw file
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

        # check package structure
        has_tests_requirements = False
        checks = {
            'dir_backend': False,
            'dir_frontend': False,
            'dir_tests': False,
            'file_module_json': False,
            'file_desc_json': False,
            'file_module_py': False,
            'file_backend_init_py': False,
            'file_tests_init_py': False,
        }
        with zipfile.ZipFile(package_path, 'r') as zp:
            for zfile in zp.infolist():
                if zfile.filename.startswith('backend/modules/%s' % module_name):
                    checks['dir_backend'] = True
                if zfile.filename.startswith('frontend/js/modules/%s' % module_name):
                    checks['dir_frontend'] = True
                if zfile.filename.startswith('tests'):
                    checks['dir_tests'] = True
                if zfile.filename == 'backend/modules/%s/%s.py' % (module_name, module_name):
                    checks['file_module_py'] = True
                if zfile.filename == 'frontend/js/modules/%s/desc.json' % module_name:
                    checks['file_desc_json'] = True
                if zfile.filename == 'module.json':
                    checks['file_module_json'] = True
                if zfile.filename == self.TESTS_REQUIREMENTS_TXT:
                    has_tests_requirements = True
                if zfile.filename == 'backend/modules/%s/__init__.py' % module_name:
                    checks['file_backend_init_py'] = True
                if zfile.filename == 'tests/__init__.py':
                    checks['file_tests_init_py'] = True

            # special case for custom main module filename
            if checks['file_backend_init_py'] and not checks['file_module_py']:
                content = zp.read('backend/modules/%s/__init__.py' % module_name).decode('utf8').strip()
                matches = re.findall(self.APP_FILENAME_PATTERN, content)
                if len(matches) == 1 and 'backend/modules/%s/%s.py' % (module_name, matches[0]) in zp.namelist():
                    checks['file_module_py'] = True

        self.logger.debug('Checks results: %s' % checks)
        if not all(checks.values()):
            raise Exception('Invalid package structure. Make sure to build it with developer application')

        return {
            'module_name': module_name,
            'module_version': module_version,
            'has_test_requirements': has_tests_requirements,
        }

    def mod_install_source(self, package_path, package_infos, no_compatibility_check=False):
        """
        Install module package (zip archive) sources

        Args:
            package_path (string): package path
            package_infos (dict): infos returned by mod_check_package function
            no_compatitiblity_check (bool): do not check module compatibility (but only deps compat)

        Raises:
            Exception if error occured
        """
        module_name, module_version, has_tests_requirements = package_infos.values()
        self.logger.info('Installing application %s v%s...' % (module_name, module_version))

        try:
            # start cleep (non blocking)
            self.logger.info('  Starting Cleep...')
            cleep_proc = subprocess.Popen(['cleep', '--noro'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(15)

            # make sure to have latest modules.json version
            self.logger.info('  Updating applications list in Cleep')
            resp = requests.post(self.CLEEP_COMMAND_URL, json={
                'command': 'check_modules_updates',
                'to': 'update',
            })
            resp.raise_for_status()
            resp_json = resp.json()
            if resp_json['error']:
                raise Exception('Check_modules_updates command failed: %s' % resp_json)

            # update "update" module to enjoy bug fixes
            self.logger.info('  Updating "update" application...')
            resp = requests.post(self.CLEEP_COMMAND_URL, json={
                'command': 'update_module',
                'to': 'update',
                'params': {
                    'module_name': 'update',
                }
            })
            resp.raise_for_status()
            resp_json = resp.json()
            self.logger.debug('Update "update" resp: %s' % resp_json)
            if resp_json['error']:
                raise Exception('Updating app "update" failed: %s' % resp_json)
            if resp_json['data']:
                self.__wait_for_cleep_process('update')
                self.logger.info('  Restarting cleep...')
                cleep_proc.kill()
                cleep_proc = subprocess.Popen(['cleep', '--noro'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(15)

            # install module in cleep (it will also install deps)
            self.logger.info('  Installing "%s" application in Cleep' % module_name)
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
                raise Exception('Installing "%s" app failed: %s' % (module_name, resp_json))
            self.__wait_for_cleep_process(module_name)

            # restart cleep
            self.logger.info('  Restarting cleep...')
            cleep_proc.kill()
            cleep_proc = subprocess.Popen(['cleep', '--noro'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(15)

            # check module is installed and running
            self.logger.info('  Checking application is installed...')
            resp = requests.get(self.CLEEP_HEALTH_URL)
            self.logger.info('Health response: %s', resp.json())
            resp.raise_for_status()
            self.logger.info('Application and its dependencies successfully installed')

            # install requirements.txt for tests
            if has_tests_requirements:
                self.logger.info('Installing tests python dependencies...')
                console = Console()
                requirements_txt_path = os.path.join(config.MODULES_SRC, module_name, self.TESTS_REQUIREMENTS_TXT)
                self.logger.debug('Tests requirements.txt path "%s"', requirements_txt_path)
                resp = console.command('python3 -m pip install --trusted-host pypi.org -r "%s"' % requirements_txt_path, 900)
                self.logger.debug('Resp: %s' % resp)
                if resp['returncode'] != 0:
                    self.logger.error('Error installing tests requirements.txt: %s' , resp)
                    raise Exception('Error installing tests requirements.txt (killed=%s)' % resp['killed'])

        finally:
            if cleep_proc:
                cleep_proc.kill()

    def __wait_for_cleep_process(self, module_name):
        """
        Wait for end of current Cleep process (install, update...)
        """
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
                raise Exception('No "%s" application info in updates data' % module_name)
            if module_updates['processing'] == False:
                if module_updates['update']['failed']:
                    raise Exception('Application "%s" installation failed' % module_name)
                break

    def mod_extract_sources(self, package_path, package_infos):
        """
        Extract module package (zip archive) in dev directory

        Args:
            package_path (string): package path
            package_infos (dict): infos returned by mod_check_package function

        Raises:
            Exception if error occured
        """
        module_name, module_version, _ = package_infos.values()

        # unzip content
        self.logger.info('Extracting archive "%s" to "%s"' % (package_path, self.EXTRACT_DIR))
        with zipfile.ZipFile(package_path, 'r') as package:
            package.extractall(self.EXTRACT_DIR)

        # install sources
        os.makedirs(os.path.join(config.MODULES_SRC, module_name), exist_ok=True)
        for filepath in glob.glob(self.EXTRACT_DIR + '/**/*.*', recursive=True):
            if filepath.startswith(os.path.join(self.EXTRACT_DIR, 'frontend')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'frontend/js/modules/%s' % module_name), os.path.join(config.MODULES_SRC, module_name, 'frontend'))
                self.logger.debug(' -> frontend: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'backend')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'backend/modules/%s' % module_name), os.path.join(config.MODULES_SRC, module_name, 'backend'))
                self.logger.debug(' -> backend: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'tests')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'tests'), os.path.join(config.MODULES_SRC, module_name, 'tests'))
                self.logger.debug(' -> tests: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'scripts')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'scripts'), os.path.join(config.MODULES_SRC, module_name, 'scripts'))
                self.logger.debug(' -> scripts: %s' % dest)
            else:
                dest = filepath.replace(self.EXTRACT_DIR, os.path.join(config.MODULES_SRC, module_name))
                self.logger.debug(' -> other: %s' % dest)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.rename(filepath, dest)

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

