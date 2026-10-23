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
        variables['MODULES_DST'] = config.MODULES_DST
        cmd = """
set -e
mkdir -p "%(HTML_DST)s/"
mkdir -p "%(CORE_DST)s"
mkdir -p "%(MODULES_DST)s"
mkdir -p "%(MEDIA_DST)s/modules"
mkdir -p "%(CONFIG_DIR)s"
# Python imports cleep.modules from CORE_DST/modules; it must point at the live apps tree
if [ -e "%(CORE_DST)s/modules" ] && [ ! -L "%(CORE_DST)s/modules" ]; then
    rm -rf "%(CORE_DST)s/modules"
fi
ln -sfn "%(MODULES_DST)s" "%(CORE_DST)s/modules"
rsync -av "%(REPO_DIR)s/cleep/" "%(CORE_DST)s/" --exclude "/tests/" --exclude "modules" --exclude "*__pycache__*" --delete --exclude "*.pyc" --keep-dirlinks
rsync -av "%(REPO_DIR)s/html/" "%(HTML_DST)s/" --delete --exclude "js/modules/" --exclude "*node_modules*"
rsync -av "%(REPO_DIR)s/bin/cleep" "%(BIN_DST)s/cleep"
rsync -av "%(REPO_DIR)s/medias/sounds" "%(MEDIA_DST)s/sounds/" --delete
    """ % variables
        self.logger.debug('Coresync cmd: %s' % cmd)
        resp = c.command(cmd, 120)
        self.logger.debug('Coresync stdout:\n%s' % '\n'.join(resp['stdout']))
        if resp['stderr']:
            self.logger.debug('Coresync stderr:\n%s' % '\n'.join(resp['stderr']))
        if resp['killed'] or resp['returncode'] != 0:
            self.logger.error('Error occured while sync core content: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        return True

    def module_sync(self, module_name, backend=True, frontend=True, scripts=True):
        """
        Copy specified module content to valid execution location

        Args:
            module_name (str): module folder name under MODULES_SRC
            backend (bool): sync backend/ when True
            frontend (bool): sync frontend/ when True
            scripts (bool): sync scripts/ when True
        """
        if not os.path.exists(os.path.join(config.MODULES_SRC, module_name)):
            self.logger.error('Module "%s" doesn\'t exist [%s]' % (module_name, os.path.join(config.MODULES_SRC, module_name)))
            return False

        mod_backend_src = os.path.join(config.MODULES_SRC, module_name, 'backend/')
        mod_backend_dst = os.path.join(config.MODULES_DST, module_name)
        mod_frontend_src = os.path.join(config.MODULES_SRC, module_name, 'frontend/')
        mod_frontend_dst = os.path.join(config.MODULES_HTML_DST, module_name)
        mod_scripts_src = os.path.join(config.MODULES_SRC, module_name, 'scripts/')
        mod_scripts_dst = os.path.join(config.MODULES_SCRIPTS_DST, module_name)

        parts = []
        if backend:
            parts.append("""
if [ -d "%(BACKEND_SRC)s" ]; then
    /bin/mkdir -p "%(BACKEND_DST)s"
    rsync -av "%(BACKEND_SRC)s" "%(BACKEND_DST)s" --delete --exclude "*.pyc" --exclude "*__pycache__*"
fi
""" % {'BACKEND_SRC': mod_backend_src, 'BACKEND_DST': mod_backend_dst})
        if frontend:
            parts.append("""
if [ -d "%(FRONTEND_SRC)s" ]; then
    /bin/mkdir -p "%(FRONTEND_DST)s"
    rsync -av "%(FRONTEND_SRC)s" "%(FRONTEND_DST)s" --delete --exclude "*node_modules*"
fi
""" % {'FRONTEND_SRC': mod_frontend_src, 'FRONTEND_DST': mod_frontend_dst})
        if scripts:
            parts.append("""
if [ -d "%(SCRIPTS_SRC)s" ]; then
    /bin/mkdir -p "%(SCRIPTS_DST)s"
    rsync -av "%(SCRIPTS_SRC)s" "%(SCRIPTS_DST)s" --delete --exclude "*__pycache__*"
fi
""" % {'SCRIPTS_SRC': mod_scripts_src, 'SCRIPTS_DST': mod_scripts_dst})

        if not parts:
            return True

        c = Console()
        cmd = "set -e\n" + "\n".join(parts)
        self.logger.debug('Modsync cmd: %s' % cmd)
        resp = c.command(cmd, 120)

        self.logger.debug('Modsync stdout:\n%s' % '\n'.join(resp['stdout']))
        if resp['stderr']:
            self.logger.debug('Modsync stderr:\n%s' % '\n'.join(resp['stderr']))
        if resp['killed'] or resp['returncode'] != 0:
            self.logger.error('Error occured while sync module content: %s' % ('killed' if resp['killed'] else resp['stderr']))
            return False

        return True

    def module_run_phase_manifest(self, module_name, phase):
        """
        Run one declarative phase manifest from the synced scripts directory.

        Args:
            module_name (str): module name
            phase (str): preinst or postinst
        """
        if not os.path.exists(os.path.join(config.MODULES_SRC, module_name)):
            self.logger.error(
                'Module "%s" doesn\'t exist [%s]'
                % (module_name, os.path.join(config.MODULES_SRC, module_name))
            )
            return False

        scripts_dir = os.path.join(config.MODULES_SCRIPTS_DST, module_name)
        manifest_path = os.path.join(scripts_dir, "%s.json" % phase)
        if not os.path.exists(manifest_path):
            return True

        try:
            from cleep.core import CleepModule
            from cleep.modules.update.install.install_app_manifest import (
                InstallManifest,
                MODE_INSTALL,
            )
            from cleep.libs.internals.cleepfilesystem import CleepFilesystem
        except ImportError:
            self.logger.error(
                "Unable to import InstallManifest; is Cleep update module installed?"
            )
            return False

        self.logger.info("Running %s", manifest_path)
        try:
            data = InstallManifest.load(manifest_path)
            # Dev sync: filesystem may be unrestricted; paths still needed for bin/chmod
            fs = CleepFilesystem()
            runner = InstallManifest(
                module_name,
                CleepModule.app_paths_for(module_name),
                fs,
                logger=self.logger,
            )
            runner.run(data, mode=MODE_INSTALL)
            return True
        except Exception as exc:
            self.logger.error("Error running %s: %s", manifest_path, exc)
            return False

    def module_run_install_scripts(self, module_name):
        """
        Run module installation manifests (preinst then postinst)
        """
        return self.module_run_phase_manifest(
            module_name, "preinst"
        ) and self.module_run_phase_manifest(module_name, "postinst")
