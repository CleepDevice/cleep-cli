#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import zipfile
import os
import glob
import re
from . import config
from .console import Console
from .check import Check

class Ci():
    """
    Continuous Integration helpers
    """

    EXTRACT_DIR = '/root/extract'
    SOURCE_DIR = '/root/cleep/modules'

    def __init__(self):
        """
        Constructor
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    def mod_install_source(self, package_path):
        """
        Install module package (zip archive) sources

        Args:
            package_path (string): package path

        Raises:
            Exception if error occured
        """
        # init
        (_, module_name, module_version) = os.path.basename(package_path).split('_')
        module_version = module_version.replace('.zip', '')[1:]
        self.logger.debug('Installing application %s[%s]' % (module_name, module_version))

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
        
        # unzip content
        self.logger.debug('Extracting archive "%s" to "%s"' % (package_path, self.EXTRACT_DIR))
        with zipfile.ZipFile(package_path, 'r') as package:
            package.extractall(self.EXTRACT_DIR)

        # check structure
        if not os.path.exists(os.path.join(self.EXTRACT_DIR, 'backend/modules/%s' % module_name)):
            raise Exception('Invalid package structure')
        if not os.path.exists(os.path.join(self.EXTRACT_DIR, 'module.json')):
            raise Exception('Invalid package structure')

        # execute preinst script
        preinst_path = os.path.join(self.EXTRACT_DIR, 'scripts', 'preinst.sh')
        self.logger.debug('preinst.sh path "%s" exists? %s' % (preinst_path, os.path.exists(preinst_path)))
        if os.path.exists(preinst_path):
            self.logger.info('Execute "%s" script' % preinst_path)
            resp = console.command('chmod +x "%(script)s" && "%(script)s"' % { 'script': preinst_path }, 900)
            self.logger.debug('Resp: %s' % resp)
            if resp['returncode'] != 0:
                raise Exception('Preinst.sh script failed (timeout=%s): %s' % (resp['killed'], resp['stderr']))

        # install source
        os.makedirs(os.path.join(self.SOURCE_DIR, module_name), exist_ok=True)
        for filepath in glob.glob(self.EXTRACT_DIR + '/**/*.*', recursive=True):
            if filepath.startswith(os.path.join(self.EXTRACT_DIR, 'frontend')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'frontend/js/modules/%s' % module_name), os.path.join(self.SOURCE_DIR, module_name, 'frontend'))
                self.logger.debug(' -> frontend: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'backend')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'backend/modules/%s' % module_name), os.path.join(self.SOURCE_DIR, module_name, 'backend'))
                self.logger.debug(' -> backend: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'tests')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'tests'), os.path.join(self.SOURCE_DIR, module_name, 'tests'))
                self.logger.debug(' -> tests: %s' % dest)
            elif filepath.startswith(os.path.join(self.EXTRACT_DIR, 'scripts')):
                dest = filepath.replace(os.path.join(self.EXTRACT_DIR, 'scripts'), os.path.join(self.SOURCE_DIR, module_name, 'scripts'))
                self.logger.debug(' -> scripts: %s' % dest)
            else:
                dest = filepath.replace(self.EXTRACT_DIR, os.path.join(self.SOURCE_DIR, module_name))
                self.logger.debug(' -> other: %s' % dest)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.rename(filepath, dest)

        # execute postinst script
        postinst_path = os.path.join(self.SOURCE_DIR, module_name, 'scripts', 'postinst.sh')
        self.logger.debug('postinst.sh path "%s" exists? %s' % (postinst_path, os.path.exists(postinst_path)))
        if os.path.exists(postinst_path):
            self.logger.info('Execute "%s" script' % postinst_path)
            resp = console.command('chmod +x "%(script)s" && "%(script)s"' % { 'script': postinst_path }, 900)
            self.logger.debug('Resp: %s' % resp)
            if resp['returncode'] != 0:
                raise Exception('Postinst.sh script failed (timeout=%s): %s' % (resp['killed'], resp['stderr']))


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

