#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
from .console import EndlessConsole, Console
import logging
from . import config
import importlib
from datetime import datetime
from github import Github
from github.GithubException import BadCredentialsException, UnknownObjectException
from urllib.parse import quote
import base64
from .cleepapi import CleepApi
from .tools import is_cleep_running, get_cleep_url
from semver import Version
import requests

requests.packages.urllib3.disable_warnings()

class Docs():
    """
    Handle documentation processes
    @see https://samnicholls.net/2016/06/15/how-to-sphinx-readthedocs/
    """

    DOCS_TEMP_PATH = '/tmp/cleep-docs'
    DOCS_EXTRACT_PATH = '/tmp/docs'
    DOCS_ARCHIVE_NAME = 'cleep-core-docs.zip'
    DOCS_COMMIT_MESSAGE = 'Update doc Cleep v%(version)s'
    BASE_APP_DOC_URL = "https://raw.githubusercontent.com/CleepDevice/" + config.GITHUB_REPO_APP_DOCS + "/main/%(module_name)s/%(module_name)s.json"

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.__endless_command_running = False
        self.__endless_command_return_code = 0
        self.__module_version = None
        self.__module_author = None

    def __console_callback(self, stdout, stderr):
        self.logger.info((stdout if stdout is not None else '') + (stderr if stderr is not None else ''))

    def __console_end_callback(self, return_code, killed):
        self.__endless_command_running = False
        self.__endless_command_return_code = return_code

    def __get_module_data(self, module_name):
        """
        Return useful module data

        Returns:
            dict of data::

                {
                    version (string): module version
                    author (string): module author
                }

        """
        if self.__module_version:
            return {
                'version': self.__module_version,
                'author': self.__module_author
            }

        try:
            module_ = importlib.import_module('cleep.modules.%s' % (module_name))
            app_filename = getattr(module_, 'APP_FILENAME', module_name)
            del module_
            module_ = importlib.import_module('cleep.modules.%s.%s' % (module_name, app_filename))
            class_name = next((item for item in dir(module_) if item.lower() == app_filename.lower()), None)
            module_class_ = getattr(module_, class_name or '', None)
            self.__module_version = module_class_.MODULE_VERSION
            self.__module_author = module_class_.MODULE_AUTHOR

            return {
                'version': self.__module_version,
                'author': self.__module_author
            }
        except:
            self.logger.exception('Unable to get module infos. Is module valid?')
            return None

    def generate_module_api_docs(self, module_name, preview=False):
        """
        Generate module API documentation (sphinx one)

        Args:
            module_name (string): module name
            preview (bool): preview generated documentation as text directly on stdout
        """
        #checking module path
        path = os.path.join(config.MODULES_SRC, module_name, 'docs')
        if not os.path.exists(path):
            self.logger.error('Docs directory for module "%s" does not exist' % (module_name))
            return False

        module_data = self.__get_module_data(module_name)
        self.logger.debug('Module data: %s' % module_data)
        if module_data is None:
            return False

        today = datetime.today()

        self.logger.info('=> Generating documentation...')
        cmd = """
cd "%(DOCS_PATH)s"
/usr/bin/rm -rf "%(BUILD_DIR)s" "%(SOURCE_DIR)s"
/usr/local/bin/sphinx-apidoc -o "%(SOURCE_DIR)s/" "../backend"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Building html documentation..."
/usr/local/bin/sphinx-build -M html "." "%(BUILD_DIR)s" -D project="%(MODULE_NAME_CAPITALIZED)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Building singlehtml documentation..."
/usr/local/bin/sphinx-build -M singlehtml "." "%(BUILD_DIR)s" -D project="%(MODULE_NAME_CAPITALIZED)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Building xml documentation..."
/usr/local/bin/sphinx-build -M xml "." "%(BUILD_DIR)s" -D project="%(MODULE_NAME_CAPITALIZED)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Building text documentation..."
/usr/local/bin/sphinx-build -M text "." "%(BUILD_DIR)s" -D project="%(MODULE_NAME_CAPITALIZED)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Packaging html documentation..."
/usr/bin/find "%(BUILD_DIR)s/" -type f -print0 | xargs -0 sed -i "s/backend/%(MODULE_NAME)s/g"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
/usr/bin/find "%(BUILD_DIR)s/" -type f -print0 | xargs -0 sed -i "s/Backend/%(MODULE_NAME_CAPITALIZED)s/g"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
/usr/bin/find "%(BUILD_DIR)s/" -iname \*.* | for f in $(find . -name backend*); do mv $f $(echo "$f" | sed -r 's|backend|%(MODULE_NAME)s|g'); done
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
#/bin/tar -czvf "%(MODULE_NAME)s-docs.tar.gz" "%(BUILD_DIR)s/html" --transform='s/%(BUILD_DIR)s\//\//g' && ARCHIVE=`/usr/bin/realpath "%(MODULE_NAME)s-docs.tar.gz"` && echo "ARCHIVE=$ARCHIVE"
cd "_build"; /usr/bin/zip "../%(MODULE_NAME)s-docs.zip" -r "html"; cd ..
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
/bin/cp -a "%(BUILD_DIR)s/text/source/%(MODULE_NAME)s.txt" "%(MODULE_NAME)s-docs.txt"
/bin/cp -a "%(BUILD_DIR)s/xml/source/%(MODULE_NAME)s.xml" "%(MODULE_NAME)s-docs.xml"
%(DISPLAY_TEXT)s
        """ % {
            'DOCS_PATH': path,
            'SOURCE_DIR': 'source',
            'BUILD_DIR': '_build',
            'MODULE_NAME': module_name,
            'MODULE_NAME_CAPITALIZED': module_name.capitalize(),
            'YEAR': today.year,
            'AUTHOR': module_data['author'],
            'VERSION': module_data['version'],
            'DISPLAY_TEXT': 'echo; echo; echo "========== DOC PREVIEW =========="; echo; cat "%s-docs.txt"' % module_name if preview else '',
        }

        self.logger.debug('Docs cmd: %s' % cmd)
        self.__endless_command_running = True
        c = EndlessConsole(cmd, self.__console_callback, self.__console_end_callback)
        c.start()

        while self.__endless_command_running:
            time.sleep(0.25)

        self.logger.debug('Return code: %s' % self.__endless_command_return_code)
        if self.__endless_command_return_code!=0:
            return False

        return True

    def get_module_api_docs_archive_path(self, module_name):
        """
        Display module docs archive path if exists
        """
        # check module path
        docs_path = os.path.join(config.MODULES_SRC, module_name, 'docs')
        if not os.path.exists(docs_path):
            self.logger.error('Docs directory for module "%s" does not exist' % (module_name))
            return False

        zip_path = os.path.join(docs_path, '%s-docs.zip' % module_name)
        if not os.path.exists(zip_path):
            self.logger.error('There is no documentation archive generated for module "%s"' % (module_name))
            return False

        self.logger.info('DOC_ARCHIVE=%s' % zip_path)
        return True

    def generate_module_docs(self, module_name):
        """
        Generate module API documentation from sources

        Args:
            module_name (string): module name
        """
        if is_cleep_running():
            return self.__generate_module_docs_by_api_call(module_name)
        return self.__generate_module_docs_by_command_line(module_name)

    def __generate_module_docs_by_api_call(self, module_name):
        """
        Generate module docs by api call
        """
        self.logger.debug("Get module docs by api call")
        rpc_url = get_cleep_url()
        self.logger.info('Cleep RPC url: %s', rpc_url)
        cleepapi = CleepApi(rpc_url)
        return cleepapi.get_documentation(module_name)

    def __generate_module_docs_by_command_line(self, module_name):
        """
        Generate module docs by command line
        """
        self.logger.debug("Get module docs by command line")
        console = Console()
        resp = console.command(f"cleep --cidoc={module_name}")
        self.logger.debug("Resp: %s", resp)

        if resp["returncode"] != 0:
            self.logger.error("Unable to generate %s doc", module_name)
            raise Exception(f"Error occured generating {module_name} documentation")

        return json.loads(''.join(resp["stdout"]))

    def generate_core_docs(self, publish=False):
        """
        Generate core documentation
        """
        # check core path
        path = os.path.join(config.CORE_SRC, '../docs')
        self.logger.debug('Core docs path: %s' % path)
        if not os.path.exists(path):
            self.logger.error('Docs directory for core does not exist')
            return False

        today = datetime.today()

        self.logger.info('=> Generating documentation...')
        cmd = """
cd "%(DOCS_PATH)s"
echo "=> Generating documentation sources..."
/bin/rm -rf "%(BUILD_DIR)s" "%(SOURCE_DIR)s"
/usr/local/bin/sphinx-apidoc -t templates -o "%(SOURCE_DIR)s/" "../cleep" "../cleep/tests/**" "../cleep/modules/**"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
/bin/rm -f "%(CORE)s-docs.zip"
echo "=> Building html documentation..."
/usr/local/bin/sphinx-build -M html "." "%(BUILD_DIR)s" -D project="%(PROJECT)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
echo "=> Building xml documentation..."
/usr/local/bin/sphinx-build -M xml "." "%(BUILD_DIR)s" -D project="%(PROJECT)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
echo
# echo "=> Building text documentation..."
# /usr/local/bin/sphinx-build -M text "." "%(BUILD_DIR)s" -D project="%(PROJECT)s" -D copyright="%(YEAR)s %(AUTHOR)s" -D author="%(AUTHOR)s" -D version="%(VERSION)s" -D release="%(VERSION)s"
# if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
# echo
echo "=> Packaging html documentation..."
cd "_build"; /usr/bin/zip "../%(CORE)s-docs.zip" -r "html"; cd ..
if [ $? -ne 0 ]; then echo "Error occured"; exit 1; fi
# TODO /bin/cp -a "%(BUILD_DIR)s/xml/source/%(CORE)s.xml" "%(CORE)s-docs.xml"
        """ % {
            'DOCS_PATH': path,
            'SOURCE_DIR': 'source',
            'BUILD_DIR': '_build',
            'CORE': 'cleep-core',
            'PROJECT': config.DOCS_PROJECT_NAME,
            'YEAR': today.year,
            'AUTHOR': config.DOCS_AUTHOR,
            'VERSION': config.CORE_VERSION,
        }

        self.logger.debug('Docs cmd: %s' % cmd)
        self.__endless_command_running = True
        c = EndlessConsole(cmd, self.__console_callback, self.__console_end_callback)
        c.start()

        while self.__endless_command_running:
            time.sleep(0.25)

        self.logger.debug('Return code: %s' % self.__endless_command_return_code)
        if self.__endless_command_return_code!=0:
            return False

        # publish docs
        if publish:
            self.logger.info('=> Publishing documentation for Cleep v%s...', config.CORE_VERSION)
            return self.publish_core_docs()

        return True

    def publish_core_docs(self):
        """
        Publish core docs to github pages
        """
        c = Console()

        # check
        docs_archive_path = os.path.join(config.REPO_DIR, 'docs/', self.DOCS_ARCHIVE_NAME)
        if not os.path.exists(docs_archive_path):
            self.logger.error('Core has no docs archive generated (%s). Please run "cleep-cli coredocs" first' % docs_archive_path)
            return False

        # clone repo
        self.logger.debug('Cloning core repository...')
        repo = 'git@github.com:%s/%s.git' % (config.GITHUB_ORG, config.GITHUB_REPO_DOCS)
        cmd = 'rm -rf "%s"; git clone -q "%s" "%s"' % (self.DOCS_TEMP_PATH, repo, self.DOCS_TEMP_PATH)
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60) 
        self.logger.debug('Clone resp: %s' % resp)
        if resp['returncode'] != 0 or resp['killed']:
            self.logger.error('Error occured while cloning repository: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False
    
        # add docs
        self.logger.debug('Updating docs...')
        cmd = 'unzip "%s" -d "%s" && cp -fr %s %s' % (
            docs_archive_path,
            self.DOCS_EXTRACT_PATH,
            os.path.join(self.DOCS_EXTRACT_PATH, 'html', '*'),
            self.DOCS_TEMP_PATH,
        )
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60) 
        self.logger.debug('Unzip resp: %s' % resp)
        if resp['returncode'] != 0 or resp['killed']:
            self.logger.error('Error occured while unzipping core docs archive: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        # commit changes
        self.logger.debug('Commiting changes...')
        cmd = 'cd "%s" && git add . && git commit -m "%s" | true && git push | true' % (
            self.DOCS_TEMP_PATH,
            self.DOCS_COMMIT_MESSAGE % { 'version': config.CORE_VERSION },
        )
        self.logger.debug('cmd: %s' % cmd)
        resp = c.command(cmd, 60) 
        self.logger.debug('Commit resp: %s' % resp)
        if resp['returncode'] != 0 or resp['killed']:
            self.logger.error('Error occured while pushing changes: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        return True

    def publish_module_docs(self, module_name, module_version, github_token=None):
        """
        Publish application documentation on specified repo.
        It publish both a tagged version and a latest version

        Args:
            module_name (str): module name
            module_version (str): module version (semver)
            github_token (str): github access token

        Returns:
            bool: True if publication succeed, False otherwise
        """
        try:
            Version.parse(module_version)
        except ValueError as error:
            raise Exception(str(error))
        repo = self.__get_github_app_docs_repo(github_token)
        if repo is None:
            raise Exception("Unable to connect to app doc repository")

        documentation = self.generate_module_docs(module_name)

        try:
            # latest doc file
            latest_file_path = self.__get_app_doc_file_path(module_name)
            (_, file_sha) = self.__get_github_app_doc_file(latest_file_path, repo)
            latest_content = {
                "version": module_version,
                "doc": documentation,
            }
            self.__create_or_update_repo_doc_file(module_name, latest_file_path, latest_content, file_sha, repo)

            # version doc file
            version_file_path = self.__get_app_doc_file_path(module_name, module_version)
            (_, file_sha) = self.__get_github_app_doc_file(version_file_path, repo)
            self.__create_or_update_repo_doc_file(module_name, version_file_path, documentation, file_sha, repo)

            return True

        except Exception:
            self.logger.exception("Unable to update doc file in repo")
            return False

    def __create_or_update_repo_doc_file(self, module_name, file_path, file_content, file_sha, repo):
        """
        Process create or update file in repo according to file_sha value

        Args:
            module_name (str): module name
            file_path (str): github file path
            file_content (dict): file content
            file_sha (str): github file sha
            repo (Repository): Repository instance
        """
        update_commit_message = f"Update {module_name} doc"
        create_commit_message = f"Create {module_name} doc"
        if file_sha:
            repo.update_file(file_path, update_commit_message, json.dumps(file_content, indent=2), file_sha)
        else:
            repo.create_file(file_path, create_commit_message, json.dumps(file_content, indent=2))

    def __get_github_app_doc_file(self, file_path, repo):
        """
        Get app doc file from repo

        Args:
            file_path (str): file path
            repo (Repository): repository instance

        Returns:
            tuple: application documentation file content and file sha. Tuple of None if error occured::

                (
                    str: file content,
                    str: file sha (for update)
                )

        """
        try:
            file_content = repo.get_contents(file_path)
            return (base64.b64decode(file_content.content), file_content.sha)
        except UnknownObjectException:
            pass
        except Exception:
            self.logger.exception("Unable to get doc file from '%s'", file_path)

        return (None, None)

    def __get_github_app_docs_repo(self, github_token=None):
        """
        Create Github repository instance.

        Args:
            github_token (str): github repo access token

        Returns:
            Repository (object): repository instance or None if error occured
        """
        try:
            if not github_token:
                github_token = os.environ.get("GITHUB_ACCESS_TOKEN")
            if not github_token:
                github_token = os.environ.get("GITHUB_TOKEN")
            github = Github(github_token)
            repo = github.get_repo(f"{config.GITHUB_ORG}/{config.GITHUB_REPO_APP_DOCS}")

            return repo

        except BadCredentialsException:
            self.logger.exception("Invalid credentials")
            return None

        except Exception:
            self.logger.exception("Unable to open connection to app docs repo")
            return None

    def __get_app_doc_file_path(self, module_name, module_version=None):
        """
        Return application doc path

        Args:
            module_name (str): module name
            module_version (str): if specified append version to filename for historization

        Returns:
            str: path
        """
        version = '' if not module_version else f"_{module_version}"
        path = quote(f"{module_name}/{module_name}{version}.json")
        self.logger.debug("Github app doc file path: %s", path)
        return path

    def check_module_breaking_changes(self, module_name):
        """
        Check application documentation for breaking changes

        Args:
            module_name (str): module name

        Returns:
            dict: breaking changes::

            {
                errors (list): list of breaking changes,
                warnings (list): list of warnings,
            }

        """
        errors = []
        warnings = []
        new_doc = self.generate_module_docs(module_name)
        old_doc = self.__get_latest_app_doc_file_from_url(module_name)

        self.logger.debug("Old doc (from repo): %s", old_doc)
        self.logger.debug("New doc (from local): %s", new_doc)

        if old_doc is not None:
            self.__compare_doc_args(new_doc, old_doc, errors, warnings)
            self.__compare_doc_returns(new_doc, old_doc, errors, warnings)

        return {
            "errors": errors,
            "warnings": warnings,
        }

    def __compare_doc_args(self, new_doc, old_doc, errors, warnings):
        """
        Compare documentation arguments

        Args:
            new_doc (dict): new documentation
            old_doc (dict): old documentation (from repo)
            errors (list): list of errors to update
            warnings (list): list of warnings to update
        """
        for cmd_name in new_doc:
            self.logger.debug("Compare cmd args '%s'", cmd_name)
            if cmd_name not in old_doc:
                continue

            new_args = new_doc[cmd_name]["args"]
            old_args = old_doc[cmd_name]["args"]

            self.logger.debug("new_args: %s", new_args)
            self.logger.debug("old_args: %s", old_args)

            self.logger.debug(" -> args length: %s VS %s", len(new_args), len(old_args))
            if len(new_args) < len(old_args):
                errors.append(f"Command {cmd_name} has a parameter that was removed. This is not allowed.")
                continue

            if len(new_args) > len(old_args):
                error_found = False
                for index, new_arg in enumerate(new_args[len(old_args) - len(new_args):]):
                    if not new_arg["optional"]:
                        errors.append(f"Command {cmd_name} has new parameter {new_arg['name']} added in new version but has not default value. This will cause command call failure.")
                        error_found = True
                if error_found:
                    continue

            for index, new_arg in enumerate(new_args[:len(old_args)]):
                self.logger.debug(" -> new_arg at position %s: %s", index, new_arg)
                self.logger.debug(" -> arg position: %s VS %s", new_arg["name"], old_args[index]["name"])
                if new_arg["name"] != old_args[index]["name"]:
                    errors.append(f"Command {cmd_name} argument {new_arg['name']} order has changed. This could cause command call failure.")
                self.logger.debug(" -> arg type: %s VS %s", new_arg["type"], old_args[index]["type"])
                if new_arg["type"] != old_args[index]["type"]:
                    warnings.append(f"Command {cmd_name} argument {new_arg['name']} type is different from previous version ({old_args[index]['type']}). This could create command call failure.")
                self.logger.debug(" -> arg formats: %s VS %s", new_arg["formats"], old_args[index]["formats"])
                if new_arg["formats"] != old_args[index]["formats"]:
                    warnings.append(f"Command {cmd_name} argument {new_arg['name']} has formats updated from previous version. This could create command call failure.")

    def __compare_doc_returns(self, new_doc, old_doc, errors, warnings):
        """
        Compare documentation returns

        Args:
            new_doc (dict): new documentation
            old_doc (dict): old documentation (from repo)
            errors (list): list of errors to update
            warnings (list): list of warnings to update
        """
        for cmd_name in new_doc:
            self.logger.debug("Compare cmd returns '%s'", cmd_name)
            if cmd_name not in old_doc:
                continue

            new_returns = new_doc[cmd_name]["returns"]
            old_returns = old_doc[cmd_name]["returns"]

            self.logger.debug("new_returns: %s", new_returns)
            self.logger.debug("old_returns: %s", old_returns)

            for new_return in new_returns:
                found_old_returns = [old_return for old_return in old_returns if old_return["type"] == new_return["type"]]
                self.logger.debug(" -> found old returns: %s", found_old_returns)
                for found_old_return in found_old_returns:
                    if new_return["formats"] != found_old_return["formats"]:
                        warnings.append(f"Command {cmd_name} has formats updated from previous version. This could create called failure.")

            if len(old_returns) > len(new_returns):
                for old_return in old_returns:
                    found_new_returns = [new_return for new_return in new_returns if new_return["type"] == old_return["type"]]
                    self.logger.debug(" -> found new returns: %s", found_new_returns)
                    if len(found_new_returns) == 0:
                        warnings.append(f"Command {cmd_name} has return type {old_return['type']} removed from previous version. This could create error in caller.")

    def __get_latest_app_doc_file_from_url(self, module_name):
        """
        Get latest app doc file from github using url

        Args:
            module_name (str): module name

        Returns:
            str: application documentation file content
        """
        try:
            url = self.BASE_APP_DOC_URL % { "module_name": module_name }
            self.logger.debug("App doc url: %s", url)
            resp = requests.get(url, headers={"Content-Type": "application/json"})

            resp.raise_for_status()

            content = resp.json()
            self.logger.debug("App doc file response [%s]: %s", type(content), resp)

            return content["doc"]

        except Exception:
            if self.logger.getEffectiveLevel() == logging.DEBUG:
                self.logger.exception("Unable to get app doc file")
            return None
