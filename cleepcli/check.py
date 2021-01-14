#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from .console import Console
import logging
from . import config
from . import tools as Tools
import importlib
from cleep.common import CATEGORIES
import re
import inspect
import glob
import copy
import json

class Check():
    """
    Handle module check:
        - check backend: variables, function
        - check frontend: config, desc.json, image directive
        - run pylint on backend
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def check_backend(self, module_name):
        """
        Check backend

        Args:
            module_name (string): module name to check

        Returns:
            dict: backend informations::

            {
                errors (list): list of errors
                warnings (list): list of warnings
                metadata (dict): module metadata
                files (dict): collection of files::
                    {
                        module (dict): main module informations
                        events (dict): events informations
                        formatters (dict): formatters informations
                        drivers (dict): drivers informations
                    }
            }

        """
        if not os.path.exists(os.path.join(config.MODULES_DST, module_name)):
            raise Exception('Module "%s" does not exist' % module_name)

        # get module instance
        try:
            module_ = importlib.import_module('cleep.modules.%s.%s' % (module_name, module_name))
            class_name = next((item for item in dir(module_) if item.lower() == module_name.lower()), None)
            class_ = getattr(module_, class_name or '', None)
        except Exception as e:
            self.logger.exception('Unable to load application "%s". Please check your code' % module_name)
            raise Exception('Unable to load application "%s". Please check your code' % module_name) from e
        if not class_:
            raise Exception('Main class was not found for app "%s". Application class must have the same name than app name' % module_name)

        # build metadata and list of files
        metadata = self.__build_metadata(class_)
        files = self.__build_files_list(class_)

        return {
            'errors': metadata['errors'] + files['errors'],
            'warnings': metadata['warnings'] + files['warnings'],
            'metadata': metadata['metadata'],
            'files': {
                'module': files['module'],
                'events': files['events'],
                'drivers': files['drivers'],
                'formatters': files['formatters'],
                'libs': files['libs'],
            }
        }
        
    def __build_files_list(self, class_):
        """
        Build module list of files

        Args:
            class_ (Class): loaded module class

        Returns:
            dict: list of modules files::

            {
                errors (list): list of errors
                warnings (list): list of warnings
                module (dict): file infos for main module
                events (list): list of events infos
                formatters (list): list or formatters infos
                drivers (list): list of drivers infos
                libs (list): list of libs
            }
                
        """
        errors = []
        warnings = []

        # get all application files
        all_files = self.__get_backend_files(class_)
        self.logger.debug('All files: %s' % all_files)

        # analyse files
        events = self.__get_files_for_kind(all_files['files'], {'endswith': 'event', 'class': 'Event'})
        errors += events['errors']
        warnings += events['warnings']
        drivers = self.__get_files_for_kind(all_files['files'], {'endswith': 'driver', 'class': 'Driver'})
        errors += drivers['errors']
        warnings += drivers['warnings']
        formatters = self.__get_files_for_kind(all_files['files'], {'endswith': 'formatter', 'class': 'ProfileFormatter'})
        errors += formatters['errors']
        warnings += formatters['warnings']

        # get libs
        found_files = ([e['fullpath'] for e in events['files']] + 
                       [f['fullpath'] for f in formatters['files']] +
                       [d['fullpath'] for d in drivers['files']])
        self.logger.debug('Found files: %s' % found_files)
        libs = [f for f in all_files['files'] if f['fullpath'] not in found_files]

        # check __init__.py
        if not self.__has_init_py(all_files['initpy'], all_files['folders']):
            errors.append('Some __init__.py files are missing in root folder or sub folders')

        return {
            'errors': errors,
            'warnings': warnings,
            'module': all_files['module'],
            'libs': sorted(libs, key=lambda k: k['fullpath']),
            'events': sorted(events['files'], key=lambda k: k['fullpath']),
            'formatters': sorted(formatters['files'], key=lambda k: k['fullpath']),
            'drivers': sorted(drivers['files'], key=lambda k: k['fullpath']),
        }

    def __has_init_py(self, initpy, folders):
        """
        Check if __init__.py files exists in all folders

        Args:
            initpy (list): list of existing __init__.py fullpaths
            folders (list): list of application folders

        Returns:
            bool: True if all __init__.py exists
        """
        return all([os.path.join(folder, '__init__.py') in initpy for folder in folders])

    def __get_files_for_kind(self, all_files, kind):
        """
        Return files infos according to specified type

        Args:
            all_files (list): list of files in module folder
            kind (dict): kind of files to search for::
            
                {
                    class (string): must be Event|ProfileFormatter|Driver
                    endswith (string): event|formatter|driver
                }

        Returns:
            list: list of files of requested kind
        """
        out = {
            'errors': [],
            'warnings': [],
            'files': []
        }

        for a_file in all_files:
            # drop useless files
            if not a_file['filename'].lower().endswith(kind['endswith'] + '.py'):
                continue

            # load file
            try:
                mod_name = a_file['filename'].replace('.py', '')
                parts = Tools.full_split_path(a_file['fullpath'])
                mod_ = importlib.import_module('cleep.modules.%s.%s' % (parts[-2], mod_name))
            except Exception as e:
                self.logger.exception('Error loading file "%s"' % a_file['fullpath'])
                out['errors'].append('Error loading file "%s". Please check file [%s]' % (
                    a_file['fullpath'], str(e)
                ))
                continue

            # check class name
            class_name = next((item for item in dir(mod_) if item.lower() == mod_name.lower()), None)
            if not class_name:
                out['errors'].append('Error loading file "%s": class name should have the same name than filename' % a_file['fullpath'])
                continue
            class_ = getattr(mod_, class_name)

            # check base class
            if not any([True for c in inspect.getmro(class_) if c.__name__ == kind['class']]):
                out['errors'].append('Error loading file "%s": class "%s" should inherit from "%s" due to its name. Please fix it' % (
                    a_file['fullpath'],
                    class_name,
                    kind['class'],
                ))
                continue

            out['files'].append({
                'fullpath': a_file['fullpath'],
                'filename': a_file['filename'],
                'path': a_file['path'],
                'classname': class_name,
            })

        return out

    def __get_backend_files(self, class_):
        """
        Get list of backend files

        Args:
            class_ (Class): loadde module class

        Returns:
            list: list of found files::

            {
                initpy (list): list of __init__.py fullpaths
                module (dict): main module infos::
                    {
                        fullpath (string): fullpath
                        filename (string): filename
                        path (string): path within module
                    },
                files (dict): other files infos::
                    [
                        {
                            fullpath (string): fullpath
                            filename (string): filename
                            path (string): path within module
                        },
                        ...
                    ],
                folders (list): list of module subfolders
            }

        """
        class_path = inspect.getfile(class_).replace('.pyc', '.py')
        module_path = class_path.rsplit('/',1)[0]

        fullpaths = glob.glob(module_path + '/**/*', recursive=True)
        out = {
            'module': {},
            'files': [],
            'initpy': [],
            'folders': [],
        }
        for fullpath in fullpaths:
            # drop useless files
            fileext = os.path.splitext(fullpath)[1]
            if '__pycache__' in fullpath:
                continue
            if any([True for f in ['.pylintrc', ] if fullpath.find(f) >= 0]):
                continue
            if fileext != '.py':
                continue

            if fullpath.endswith('__init__.py'):
                # handle __init__.py file
                out['initpy'].append(fullpath)
            elif fullpath == class_path:
                # handle main module
                out['module'] = {
                    'fullpath': fullpath,
                    'filename': os.path.split(fullpath)[1],
                    'path': fullpath.split('modules/')[1],
                }
            else:
                # handle other file
                out['files'].append({
                    'fullpath': fullpath,
                    'filename': os.path.split(fullpath)[1],
                    'path': fullpath.split('modules/')[1],
                })

            # add scanned folders
            folder = os.path.dirname(fullpath)
            if folder not in out['folders']:
                out['folders'].append(folder)

        return out

    def __build_metadata(self, class_):
        """
        Build module metadata from module constants

        Args:
            class_ (Class): loaded module class

        Returns:
            dict: metadata::

            {
                metadata (dict): list of module properties
                errors (list): list of errors
                warnings (list): list of warnings
            }

        """
        check = self.__check_backend_constants(class_)

        return {
            'metadata': {
                'author': getattr(class_, 'MODULE_AUTHOR', None),
                'description': getattr(class_, 'MODULE_DESCRIPTION', None),
                'longdescription': getattr(class_, 'MODULE_LONGDESCRIPTION', None),
                'category': getattr(class_, 'MODULE_CATEGORY', None),
                'deps': getattr(class_, 'MODULE_DEPS', []),
                'version': getattr(class_, 'MODULE_VERSION', None),
                'tags': getattr(class_, 'MODULE_TAGS', []),
                'country': getattr(class_, 'MODULE_COUNTRY', None),
                'urls': {
                    'info': getattr(class_, 'MODULE_URLINFO', None),
                    'help': getattr(class_, 'MODULE_URLHELP', None),
                    'site': getattr(class_, 'MODULE_URLSITE', None),
                    'bugs': getattr(class_, 'MODULE_URLBUGS', None),
                },
                'price': getattr(class_, 'MODULE_PRICE', None),
                'label': getattr(class_, 'MODULE_LABEL', class_.__name__),
            },
            'errors': check['errors'],
            'warnings': check['warnings'],
        }

    def __check_constant(self, constant):
        """
        Check specified constant

        Args:
            parameters (list): list of parameters to check::

                {
                    name (string): parameter name
                    type (type): parameter primitive type (str, bool...)
                    none (bool): True if parameter can be None
                    empty (bool): True if string value can be empty
                    value (any): parameter value
                    validator (function): validator function. Take value in parameter and must return bool
                    message (string): custom message to return instead of generic error
                },
                ...

        Returns:
            string: message in case of error or warning, None if nothing to report

        """
        # check None
        if ('none' not in constant or ('none' in constant and not constant['none'])) and constant['value'] is None:
            return 'Constant "%s" is missing' % constant['name']

        # check value
        if constant['value'] is None:
            # nothing else to check, constant value is allowed as None
            return None

        # check type
        if not isinstance(constant['value'], constant['type']):
            return constant['message'] if 'message' in constant else 'Constant "%s" has wrong type ("%s" instead of "%s")' % (
                constant['name'],
                type(constant['value']),
                constant['type'],
            )

        # use validator if provided
        if 'validator' in constant and not constant['validator'](constant['value']):
            return constant['message'] if 'message' in constant else 'Constant "%s" is invalid (specified="%s")' % (
                constant['name'],
                constant['value'],
            )

        # check empty
        if (('empty' not in constant or ('empty' in constant and not constant['empty'])) and
                getattr(constant['value'], '__len__', None) and
                len(constant['value']) == 0):
            return constant['message'] if 'message' in constant else 'Constant "%s" is empty (specified="%s")' % (
                constant['name'],
                constant['value'],
            )

        return None

    def __check_backend_constants(self, class_, full=False):
        """
        Check module constants

        Args:
            class_ (Class): loaded module class
            full (bool): full constants check (useful only on Cleep CI)

        Returns:
            dict: errors and warnings::

            {
                errors (list): list of errors
                warnings (list): list of warnings
            }

        """
        out = {
            'errors': [],
            'warnings': [],
        }

        # MODULE_AUTHOR
        msg = self.__check_constant({'name': 'MODULE_AUTHOR', 'type': str, 'value': getattr(class_, 'MODULE_AUTHOR', None)})
        if msg:
            out['errors'].append(msg)

        # MODULE_DESCRIPTION
        msg = self.__check_constant({'name': 'MODULE_DESCRIPTION', 'type': str, 'value': getattr(class_, 'MODULE_DESCRIPTION', None)})
        if msg:
            out['errors'].append(msg)

        # MODULE_LONGDESCRIPTION
        msg = self.__check_constant({'name': 'MODULE_LONGDESCRIPTION', 'type': str, 'value': getattr(class_, 'MODULE_LONGDESCRIPTION', None)})
        if msg:
            out['errors'].append(msg)

        # MODULE_CATEGORY
        msg = self.__check_constant({
            'name': 'MODULE_CATEGORY',
            'type': str,
            'value': getattr(class_, 'MODULE_CATEGORY', None),
            'validator': lambda val: val in CATEGORIES.ALL,
            'message': 'MODULE_CATEGORY must be filled with existing categories. See cleep.common.CATEGORIES'
        })
        if msg:
            out['errors'].append(msg)

        # MODULE_DEPS
        msg = self.__check_constant({'name': 'MODULE_DEPS', 'type': list, 'value': getattr(class_, 'MODULE_DEPS', None), 'empty': True})
        if msg:
            out['errors'].append(msg)

        # MODULE_VERSION
        msg = self.__check_constant({
            'name': 'MODULE_VERSION',
            'type': str,
            'value': getattr(class_, 'MODULE_VERSION', None),
            'validator': lambda val: re.compile(r'\d+\.\d+\.\d+').match(val),
            'message': 'MODULE_VERSION must follow semver rules https://semver.org/',
        })
        if msg:
            out['errors'].append(msg)

        # MODULE_TAGS
        msg = self.__check_constant({'name': 'MODULE_TAGS', 'type': list, 'value': getattr(class_, 'MODULE_TAGS', None)})
        if msg:
            out['warnings'].append(msg)

        # MODULE_URLINFO
        msg = self.__check_constant({'name': 'MODULE_URLINFO', 'type': str, 'value': getattr(class_, 'MODULE_URLINFO', None)})
        if msg:
            out['warnings'].append(msg)

        # MODULE_URLHELP
        msg = self.__check_constant({'name': 'MODULE_URLHELP', 'type': str, 'value': getattr(class_, 'MODULE_URLHELP', None)})
        if msg:
            out['warnings'].append(msg)

        # MODULE_URLSITE
        msg = self.__check_constant({'name': 'MODULE_URLSITE', 'type': str, 'value': getattr(class_, 'MODULE_URLSITE', None)})
        if msg:
            out['warnings'].append(msg)

        # MODULE_URLBUGS
        msg = self.__check_constant({'name': 'MODULE_URLBUGS', 'type': str, 'value': getattr(class_, 'MODULE_URLBUGS', None)})
        if msg:
            out['warnings'].append(msg)

        # MODULE_COUNTRY
        msg = self.__check_constant({
            'name': 'MODULE_URLCOUNTRY',
            'type': str,
            'value': getattr(class_, 'MODULE_COUNTRY', None),
            'none': True,
            'validator': lambda val: len(val) == 2,
            'message': 'Constant MODULE_COUNTRY must be ISO3166-2 compatible code https://fr.wikipedia.org/wiki/ISO_3166-2',
        })
        if msg:
            out['errors'].append(msg)

        # MODULE_PRICE
        msg = self.__check_constant({
            'name': 'MODULE_PRICE',
            'type': float,
            'value': getattr(class_, 'MODULE_LABEL', None),
            'none': True,
        })
        if msg:
            out['errors'].append(msg)

        # MODULE_LABEL
        msg = self.__check_constant({'name': 'MODULE_LABEL', 'type': str, 'value': getattr(class_, 'MODULE_LABEL', None), 'none': True})
        if msg:
            out['errors'].append(msg)

        return out

    def check_frontend(self, module_name):
        """
        Check frontend

        Args:
            module_name (string): module name to check

        Returns:
            dict: frontend informations::
            
            {
                errors (list): list of errors
                warnings (list): list of warnings
                files (list): files informations::
                    [
                        {
                            fullpath (string): file fullpath
                            filename (string): filename
                            path (string): module path
                            usage (string): file usage
                            extension (string): file extension
                        }
                        ...
                    ]
            }

        """
        out = {
            'errors': [],
            'warnings': [],
            'files': []
        }

        # get all files
        all_files = self.__get_frontend_files(module_name)
        
        # check desc.json
        desc_json_info = self.__get_desc_json(all_files)
        self.logger.debug('desc_json_info: %s' % desc_json_info)
        if not desc_json_info:
            out['errors'].append('desc.json file is missing. Please add it following Cleep recommandation')
        else:
            desc_json = self.__check_desc_json(desc_json_info)
            self.logger.debug('desc_json: %s' % desc_json)
            out['errors'] += desc_json['errors']
            out['warnings'] += desc_json['warnings']
        if not desc_json['content']:
            raise Exception('Invalid desc.json file. Please check content.')

        # give files usage according to desc.json
        if not out['errors']:
            all_checks = self.__check_frontend_files(module_name, all_files, desc_json)
            out['errors'] += all_checks['errors']
            out['warnings'] += all_checks['warnings']
            out['files'] = all_checks['files']

        return out

    def __check_frontend_files(self, module_name, all_files, desc_json):
        """
        Check frontend files

        Args:
            all_files (list): list of all frontend files
            desc_json (dict): desc.json analyze result

        Returns:
            dict: check results::

            {
                errors (list): list of errors
                warnings (list): list of warnings
                files (list): list of all files updated with usage info
            }

        """
        out = {
            'errors': [],
            'warnings': [],
            'files': copy.deepcopy(all_files['files']),
        }
        content = desc_json['content']
        config_files = []
        global_files = []
        res_files = []
        pages_files = []
        html_files = []
        js_files = []
        css_files = []

        # fill found files
        if 'global' in content:
            global_files += content['global']['js'] if 'js' in content['global'] else []
            js_files += content['global']['js'] if 'js' in content['global'] else []
            global_files += content['global']['html'] if 'html' in content['global'] else []
            html_files += content['global']['html'] if 'html' in content['global'] else []
            global_files += content['global']['css'] if 'css' in content['global'] else []
            css_files += content['global']['css'] if 'css' in content['global'] else []
        if 'config' in content:
            config_files += content['config']['js'] if 'js' in content['config'] else []
            js_files += content['config']['js'] if 'js' in content['config'] else []
            config_files += content['config']['html'] if 'html' in content['config'] else []
            html_files += content['config']['html'] if 'html' in content['config'] else []
            config_files += content['config']['css'] if 'css' in content['config'] else []
            css_files += content['config']['css'] if 'css' in content['config'] else []
        if 'pages' in content:
            for page in content['pages']:
                pages_files += content['pages'][page]['js'] if 'js' in content['pages'][page] else []
                js_files += content['pages'][page]['js'] if 'js' in content['pages'][page] else []
                pages_files += content['pages'][page]['html'] if 'html' in content['pages'][page] else []
                html_files += content['pages'][page]['html'] if 'html' in content['pages'][page] else []
                pages_files += content['pages'][page]['css'] if 'css' in content['pages'][page] else []
                css_files += content['pages'][page]['css'] if 'css' in content['pages'][page] else []
        if 'res' in content:
            res_files += content['res']

        # check files place
        for a_file in js_files:
            if os.path.splitext(a_file)[1] != '.js':
                out['warnings'].append('File "%s" should not be in "js" section. Please fix it' % a_file)
        for a_file in html_files:
            if os.path.splitext(a_file)[1] not in ('.html', '.htm'):
                out['warnings'].append('File "%s" should not be in "html" section. Please fix it' % a_file)
        for a_file in css_files:
            if os.path.splitext(a_file)[1] != '.css':
                out['warnings'].append('File "%s" should not be in "css" section. Please fix it' % a_file)
        for a_file in res_files:
            if os.path.splitext(a_file)[1] not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                out['warnings'].append('File "%s" seems not to have a supported image format. Please convert it' % a_file)

        # give flags to files
        for a_file in out['files']:
            if a_file['filename'] in global_files:
                a_file['usage'] = 'GLOBAL'
            elif a_file['filename'] in config_files:
                a_file['usage'] = 'CONFIG'
            elif a_file['filename'] in pages_files:
                a_file['usage'] = 'PAGES'
            elif a_file['filename'] in res_files:
                a_file['usage'] = 'RES'
            elif a_file['filename'] == 'desc.json':
                a_file['usage'] = 'CORE'
            else:
                out['warnings'].append('File "%s" is unused' % a_file['path'])
                a_file['usage'] = 'UNUSED'

        # search for missing files
        paths = [item['path'].replace(module_name + '/', '') for item in all_files['files']]
        self.logger.debug('paths: %s' % paths)
        for a_file in global_files:
            a_file not in paths and out['errors'].append('File "%s" specified in desc.json "global" section is missing' % a_file)
        for a_file in config_files:
            a_file not in paths and out['errors'].append('File "%s" specified in desc.json "config" section is missing' % a_file)
        for a_file in res_files:
            a_file not in paths and out['errors'].append('File "%s" specified in desc.json "res" section is missing' % a_file)
        for a_file in pages_files:
            a_file not in paths and out['errors'].append('File "%s" specified in desc.json "pages" section is missing' % a_file)

        return out

    def __check_desc_json(self, desc_json_info):
        """
        Check desc.json content

        Args:
            desc_json_info: desc.json file info

        Returns:
            dict: check results::

            {
                errors (list): list of errors
                warnings (list): list of warnings
            }

        """
        out = {
            'errors': [],
            'warnings': [],
            'content': None,
        }

        try:
            with open(desc_json_info['fullpath']) as json_file:
                content = json.load(json_file)
                out['content'] = content
        except:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.exception('Error loading desc.json:')
            out['errors'].append('Error loading "%s". Please check file content.' % desc_json['fullpath'])
            return out

        # check content
        if not all([key in list(content.keys()) for key in ('config', 'global', 'icon')]):
            out['errors'].append('Invalid desc.json content. At least one mandatory key is missing')

        # check global section
        if 'global' in content:
            if 'js' in content['global'] and not isinstance(content['global']['js'], list):
                out['errors'].append('Invalid global.js section: it must be an array')
            if 'html' in content['global'] and not isinstance(content['global']['html'], list):
                out['errors'].append('Invalid global.html section: it must be an array')
            if 'css' in content['global'] and not isinstance(content['global']['css'], list):
                out['errors'].append('Invalid global.css section: it must be an array')

        # check config section
        if 'config' in content:
            if 'js' in content['config'] and not isinstance(content['config']['js'], list):
                out['errors'].append('Invalid config.js section: it must be an array')
            if 'html' in content['config'] and not isinstance(content['config']['html'], list):
                out['errors'].append('Invalid config.html section: it must be an array')
            if 'css' in content['config'] and not isinstance(content['config']['css'], list):
                out['errors'].append('Invalid config.css section: it must be an array')

        # check res section
        if 'res' in content and not isinstance(content['res'], list):
            out['errors'].append('Invalid res section: it must be an array')

        # check pages section
        if 'pages' in content:
            for page in content['pages']:
                if 'js' in content['pages'][page] and not isinstance(content['pages'][page]['js'], list):
                    out['errors'].append('Invalid pages.%s.js section: it must be an array' % page)
                if 'html' in content['pages'][page] and not isinstance(content['pages'][page]['html'], list):
                    out['errors'].append('Invalid pages.%s.html section: it must be an array' % page)
                if 'css' in content['pages'][page] and not isinstance(content['pages'][page]['css'], list):
                    out['errors'].append('Invalid pages.%s.css section: it must be an array' % page)

        return out

    def __get_desc_json(self, all_files):
        """
        Get desc.json file

        Args:
            all_files (list): list of frontend files

        Returns:
            dict: desc.json file infos. None if file not found
        """
        self.logger.debug('all_files: %s' % all_files['files'])
        return next((a_file for a_file in all_files['files'] if a_file['filename'] == 'desc.json'), None)

    def __get_frontend_files(self, module_name):
        """
        Get list of frontend files

        Args:
            module_name (string): module name

        Returns:
            list: list of found files::

            {
                initpy (list): list of __init__.py fullpaths
                module (dict): main module infos::
                    {
                        fullpath (string): fullpath
                        filename (string): filename
                        path (string): path within module
                    },
                files (dict): other files infos::
                    [
                        {
                            fullpath (string): fullpath
                            filename (string): filename
                            path (string): path within module
                        },
                        ...
                    ],
                folders (list): list of module subfolders
            }

        """
        module_path = os.path.join(config.MODULES_HTML_DST, module_name)
        fullpaths = glob.glob(module_path + '/**/*', recursive=True)
        out = {
            'files': [],
        }
        for fullpath in fullpaths:
            # drop some files
            filename = os.path.split(fullpath)[1]
            if filename.startswith('.') or filename.startswith('~') or filename.endswith('.tmp'):
                continue

            # store file infos
            out['files'].append({
                'fullpath': fullpath,
                'filename': filename,
                'path': fullpath.split('modules/')[1],
                'extension': os.path.splitext(fullpath)[1],
            })

        return out

    def check_scripts(self, module_name):
        """
        Check scripts files

        Args:
            module_name (string): module name

        Returns:
            dict: scripts infos::

            {
                errors (list): list of errors
                warnings (list): list of warnings
                files (list): list of files::
                    [
                        {
                            fullpath (string): file fullpath
                            filename (string): filename
                            path (string): module path
                        }
                        ...
                    ]
            }

        """
        scripts_path = os.path.join(config.MODULES_SRC, module_name, 'scripts')
        fullpaths = glob.glob(scripts_path + '/**/*', recursive=True)
        out = {
            'errors': [],
            'warnings': [],
            'files': [],
        }
        for fullpath in fullpaths:
            # drop some files
            filename = os.path.split(fullpath)[1]
            if filename not in ('preinst.sh', 'postinst.sh', 'preuninst.sh', 'postuninst.sh'):
                out['warnings'].append('File "%s" in scripts folder won\'t be part of %s package' % (filename, module_name))
                continue

            # store file infos
            out['files'].append({
                'fullpath': fullpath,
                'filename': filename,
                'path': fullpath.split('modules/%s/' % module_name)[1],
            })

        return out


    def run_pylint(self):
        """
        Run pylint on backend. Add .pylintrc if file is missing
        """
        pass
