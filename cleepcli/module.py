#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from .console import Console
import logging
from . import config
import shutil
import re

class Module():
    """
    Module class
    """

    GIT_IGNORE = """**/*.pyc
**/.coverage
**/.coveralls.yml
docs/*.zip
docs/*.txt
docs/*.xml
docs/source
docs/_build
.vscode
**/*.swp
"""
    CHANGELOG = """# Changelog

## [Unreleased]

### Added

- First release

"""
    DESC_SKEL = """{
    \\"icon\\": \\"help-circle-outline\\",
    \\"global\\": {
        \\"js\\": [\\"%(MODULE_NAME)s.service.js\\"],
        \\"html\\": [],
        \\"css\\": []
    },
    \\"config\\": {
        \\"js\\": [\\"%(MODULE_NAME)s.config.js\\"],
        \\"html\\": [\\"%(MODULE_NAME)s.config.html\\"],
        \\"css\\": []
    }
}
"""
    ANGULAR_SERVICE_SKEL = """/**
 * %(MODULE_NAME_CAPITALIZED)s Angular service.
 *
 * Singleton shared by all UI pieces of this app. Prefer storing shared state
 * and RPC helpers here (not in the config controller).
 *
 * rpcService.sendCommand(command, moduleName, params?) calls a public Python
 * method on the backend (same name, snake_case).
 */
angular
.module('Cleep')
.service('%(MODULE_NAME)sService', ['\$rootScope', 'rpcService',
function(\$rootScope, rpcService) {
    var self = this;

    /**
     * Sample RPC: no parameters.
     * Maps to backend.%(MODULE_NAME)s.%(MODULE_NAME_CAPITALIZED)s.execute_command().
     */
    self.executeCommand = function() {
        return rpcService.sendCommand('execute_command', '%(MODULE_NAME)s');
    };

    /**
     * Sample RPC: pass a value from the UI to the backend.
     * Maps to configure_value(value) on the Python module.
     */
    self.configureValue = function(value) {
        return rpcService.sendCommand('configure_value', '%(MODULE_NAME)s', {
            value: value,
        });
    };

    /**
     * Sample file upload. rpcService.upload posts the file then calls the
     * named Python handler with a temporary filepath on the device.
     */
    self.addFile = function(file) {
        return rpcService.upload('add_file', '%(MODULE_NAME)s', file);
    };

    /**
     * Optional: react to a bus event pushed to the UI.
     * Uncomment and replace the event name with one your backend emits.
     */
    /*\$rootScope.\$on('%(MODULE_NAME)s.something.happened', function(_event, uuid, params) {
        console.log('Event %(MODULE_NAME)s.something.happened', uuid, params);
    });*/
}]);"""
    ANGULAR_CONTROLLER_SKEL = """/**
 * %(MODULE_NAME_CAPITALIZED)s configuration page (Angular directive).
 *
 * Shown when the user opens this app in the market / installed apps UI.
 * If you do not need a config page, delete this file, the matching .html, and
 * remove them from frontend/desc.json.
 */
angular
.module('Cleep')
.directive('%(MODULE_NAME)sConfigComponent', ['\$rootScope', 'cleepService', 'toastService', '%(MODULE_NAME)sService',
function(\$rootScope, cleepService, toastService, %(MODULE_NAME)sService) {

    var %(MODULE_NAME)sConfigController = function() {
        var self = this;

        // Always bind the view to self.config: it stays in sync with the device.
        self.config = {};

        // Sample UI state for the starter widgets (replace with real fields).
        self.message = 'hello';
        self.checkbox = true;
        self.slider = 25;

        /**
         * Load persisted module config once the page is ready.
         */
        self.\$onInit = function() {
            cleepService.getModuleConfig('%(MODULE_NAME)s');
        };

        /**
         * Keep self.config aligned with cleepService whenever the backend
         * config changes (reloadModuleConfig, external updates, …).
         */
        \$rootScope.\$watch(function() {
            return cleepService.modules['%(MODULE_NAME)s']
                && cleepService.modules['%(MODULE_NAME)s'].config;
        }, function(newVal) {
            if (newVal && Object.keys(newVal).length) {
                Object.assign(self.config, newVal);
            }
        });

        /**
         * Sample: send the text field to the backend and refresh config.
         */
        self.setMessage = function() {
            %(MODULE_NAME)sService.configureValue(self.message)
                .then(function(response) {
                    if (response.error) {
                        toastService.error('Command failed: ' + response.message);
                        return;
                    }
                    toastService.success('Value saved');
                })
                .finally(function() {
                    cleepService.reloadModuleConfig('%(MODULE_NAME)s');
                });
        };

        /**
         * Sample: trigger a parameter-less backend command.
         */
        self.executeCommand = function() {
            %(MODULE_NAME)sService.executeCommand()
                .then(function(response) {
                    if (response.error) {
                        toastService.error('Command failed: ' + response.message);
                        return;
                    }
                    toastService.success('Command OK');
                })
                .finally(function() {
                    cleepService.reloadModuleConfig('%(MODULE_NAME)s');
                });
        };

        /**
         * Sample: checkbox change → backend.
         */
        self.updateCheckbox = function() {
            %(MODULE_NAME)sService.configureValue(self.checkbox)
                .finally(function() {
                    cleepService.reloadModuleConfig('%(MODULE_NAME)s');
                });
        };

        /**
         * Sample: slider change → backend (via config-slider cl-on-change).
         */
        self.setSlider = function() {
            %(MODULE_NAME)sService.configureValue(self.slider)
                .finally(function() {
                    cleepService.reloadModuleConfig('%(MODULE_NAME)s');
                });
        };

        /**
         * Sample: file chosen via config-file (cl-click passes { file }).
         */
        self.onFileSelected = function(file) {
            if (!file) {
                return;
            }
            %(MODULE_NAME)sService.addFile(file)
                .then(function(response) {
                    if (response.error) {
                        toastService.error('Upload failed: ' + response.message);
                        return;
                    }
                    toastService.success('File uploaded');
                });
        };
    };

    return {
        templateUrl: '%(MODULE_NAME)s.config.html',
        replace: true,
        scope: true,
        controller: %(MODULE_NAME)sConfigController,
        controllerAs: '%(MODULE_NAME)sCtl',
    };
}]);"""
    ANGULAR_CONTROLLER_TEMPLATE_SKEL = """<div layout=\\"column\\" layout-padding ng-cloak>

    <!--
      Starter config page using Cleep config-* components.
      Replace these samples with your real settings; remove unused rows.
      Icons: https://pictogrammers.com/library/mdi/
    -->

    <config-note
        cl-type=\\"info\\"
        cl-icon=\\"information\\"
        cl-note=\\"This page is a starter. Replace the sample controls below with your application settings.\\"
    ></config-note>

    <config-section cl-title=\\"Examples\\" cl-icon=\\"flask-outline\\"></config-section>

    <config-button
        cl-title=\\"Sample command\\"
        cl-subtitle=\\"Calls execute_command on the backend (no parameters)\\"
        cl-btn-label=\\"Run\\"
        cl-btn-icon=\\"play\\"
        cl-click=\\"%(MODULE_NAME)sCtl.executeCommand()\\"
    ></config-button>

    <config-text
        cl-title=\\"Sample text value\\"
        cl-subtitle=\\"Saved via configure_value on the backend\\"
        cl-model=\\"%(MODULE_NAME)sCtl.message\\"
        cl-btn-icon=\\"content-save\\"
        cl-btn-tooltip=\\"Save\\"
        cl-click=\\"%(MODULE_NAME)sCtl.setMessage()\\"
    ></config-text>

    <config-checkbox
        cl-title=\\"Sample checkbox\\"
        cl-subtitle=\\"Toggles a boolean sent with configure_value\\"
        cl-model=\\"%(MODULE_NAME)sCtl.checkbox\\"
        cl-click=\\"%(MODULE_NAME)sCtl.updateCheckbox()\\"
    ></config-checkbox>

    <config-slider
        cl-title=\\"Sample slider\\"
        cl-subtitle=\\"Number from 0 to 100\\"
        cl-model=\\"%(MODULE_NAME)sCtl.slider\\"
        cl-min=\\"0\\"
        cl-max=\\"100\\"
        cl-on-change=\\"%(MODULE_NAME)sCtl.setSlider()\\"
    ></config-slider>

    <config-file
        cl-title=\\"Sample file upload\\"
        cl-subtitle=\\"Uploads to add_file on the backend; move or delete the temp file there\\"
        cl-btn-label=\\"Choose file\\"
        cl-btn-icon=\\"upload\\"
        cl-click=\\"%(MODULE_NAME)sCtl.onFileSelected(file)\\"
    ></config-file>

</div>
"""
    PYTHON_MODULE_SKEL = """#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.exception import MissingParameter, InvalidParameter, CommandError
from cleep.core import %(BASE_CLASS)s
from cleep.common import CATEGORIES%(EXTRA_IMPORTS)s


class %(MODULE_NAME_CAPITALIZED)s(%(BASE_CLASS)s):
    \\"\\"\\"
    %(MODULE_NAME_CAPITALIZED)s application.

    Public methods (no leading underscore) are exposed as RPC commands that the
    frontend can call via rpcService.sendCommand / upload.
    \\"\\"\\"

    # --- Market / install metadata (shown in CleepDesktop & the device market) ---
    MODULE_AUTHOR = 'TODO'
    MODULE_VERSION = '0.0.0'  # semver; bump when you release
    MODULE_DEPS = %(MODULE_DEPS)s  # other Cleep apps required at runtime, e.g. ['gpio']
    MODULE_DESCRIPTION = %(MODULE_DESCRIPTION)s  # short one-line summary
    MODULE_LONGDESCRIPTION = %(MODULE_LONGDESCRIPTION)s  # longer description for the market page
    MODULE_TAGS = %(MODULE_TAGS)s  # keywords for market search
    MODULE_CATEGORY = CATEGORIES.%(MODULE_CATEGORY)s
    MODULE_URLINFO = None  # project / docs URL
    MODULE_URLHELP = None  # help / wiki URL
    MODULE_URLSITE = %(MODULE_URLSITE)s  # homepage / GitHub / service site
    MODULE_URLBUGS = None  # bug tracker

    # --- Persistent config (JSON file under the device config path) ---
    MODULE_CONFIG_FILE = '%(MODULE_NAME)s.conf'
    DEFAULT_CONFIG = {
        # Declare default keys here; they are created on first start and synced
        # to the frontend via getModuleConfig / reloadModuleConfig.
        # 'enabled': False,
    }
%(EXTRA_MEMBERS)s
    def __init__(self, bootstrap, debug_enabled):
        \\"\\"\\"
        Constructor. Keep it light: no blocking I/O, no bus commands yet.

        Args:
            bootstrap (dict): core bootstrap objects (logger helpers, events, …)
            debug_enabled (bool): True when debug logging was requested
        \\"\\"\\"
        %(BASE_CLASS)s.__init__(self, bootstrap, debug_enabled)

    def _configure(self):
        \\"\\"\\"
        Early setup while Cleep is still starting.

        Other apps are not ready: do not send_command() here. Use this for local
        state, timers preparation, reading files, etc.
        \\"\\"\\"
        pass

    def _on_start(self):
        \\"\\"\\"
        App is starting; the bus and other modules are available.

        Start background tasks and send_command() to peer apps from here.
        \\"\\"\\"
        pass

    def _on_stop(self):
        \\"\\"\\"
        App is stopping (uninstall, shutdown, or developer reload).

        Stop threads, close sockets, and release hardware here.
        \\"\\"\\"
        pass

    def on_event(self, event):
        \\"\\"\\"
        Bus event callback (every event your module is allowed to see).

        Typical uses: react to time/cron ticks, system alerts, device changes.

        Args:
            event (MessageRequest): event name + parameters from the bus
        \\"\\"\\"
        # if event['event'] == 'time.now':
        #     ...
        pass

    def execute_command(self):
        \\"\\"\\"
        Sample RPC command with no parameters (see frontend service).

        Returns:
            bool: True on success
        \\"\\"\\"
        self.logger.info('execute_command called')
        return True

    def configure_value(self, value):
        \\"\\"\\"
        Sample RPC command with a parameter from the frontend.

        Args:
            value (any): value sent by the UI (str, bool, number, …)
        \\"\\"\\"
        self.logger.info('configure_value called with value=%%r', value)
        # Example: persist it
        # self._set_config_field('example', value)

    def add_file(self, filepath):
        \\"\\"\\"
        Sample upload handler. ``filepath`` is a temporary path on the device.

        You must move the file to a permanent location or delete it when done.

        Args:
            filepath (str): path to the uploaded temporary file
        \\"\\"\\"
        self.logger.info('File uploaded: %%s', filepath)

    def _helper_for_subclasses(self):
        \\"\\"\\"
        Single leading underscore: not exposed as RPC, but usable by subclasses.
        \\"\\"\\"
        self.logger.debug('_helper_for_subclasses')

    def __private_helper(self):
        \\"\\"\\"
        Double leading underscore: name-mangled private helper (this class only).
        \\"\\"\\"
        self.logger.debug('__private_helper')
%(EXTRA_METHODS)s"""

    BASE_CLASS_CHOICES = (
        "CleepModule",
        "CleepResources",
        "CleepRenderer",
        "CleepExternalBus",
        "CleepRemoteAccessModule",
    )

    FIRMWARE_KINDS = ("uf2", "micropython")

    FIRMWARE_MANIFEST_SKEL = """{
  "schema_version": 1,
  "name": "%(MODULE_NAME_CAPITALIZED)s Pico",
  "app": "%(MODULE_NAME)s",
  "version": "0.0.1",
  "targets": ["pico"],
  "kind": "%(FIRMWARE_KIND)s",
  "description": "Companion firmware for %(MODULE_NAME)s"
}
"""

    FIRMWARE_CMAKE_SKEL = """cmake_minimum_required(VERSION 3.13)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(%(MODULE_NAME)s_fw C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(%(MODULE_NAME)s_fw
    main.c
)

target_link_libraries(%(MODULE_NAME)s_fw pico_stdlib)

pico_enable_stdio_usb(%(MODULE_NAME)s_fw 1)
pico_enable_stdio_uart(%(MODULE_NAME)s_fw 0)

pico_add_extra_outputs(%(MODULE_NAME)s_fw)
"""

    FIRMWARE_MAIN_C_SKEL = """#include "pico/stdlib.h"

int main() {
    stdio_init_all();
    const uint LED_PIN = PICO_DEFAULT_LED_PIN;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    while (true) {
        gpio_put(LED_PIN, 1);
        sleep_ms(250);
        gpio_put(LED_PIN, 0);
        sleep_ms(250);
    }
}
"""

    FIRMWARE_MAIN_PY_SKEL = """from machine import Pin
import time

led = Pin("LED", Pin.OUT)
while True:
    led.toggle()
    time.sleep(0.25)
"""

    TEST_DEFAULT = """#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from unittest.mock import Mock, patch

import pytest

from backend.%(MODULE_NAME)s import %(MODULE_NAME_CAPITALIZED)s
from cleep.exception import InvalidParameter, MissingParameter, CommandError, Unauthorized
from cleep.libs.tests.common import get_log_level

# Cleep requires tested application code.
#
# Run from the application root (parent of backend/ and tests/):
#   python3 -m pytest tests
#   python3 -m pytest tests -k test_get_module_config
# Or via cleep-cli / developer app:
#   cleep-cli modtests --module %(MODULE_NAME)s
#
# Import convention: from backend.%(MODULE_NAME)s import ... (no sys.path hacks).
# The cleep_session fixture comes from tests/conftest.py.
# Logging: DEBUG=1 / TRACE=1 / LOGLEVEL=... via get_log_level(); coverage runs stay quiet.

LOG_LEVEL = get_log_level()


@pytest.fixture(autouse=True)
def configure_logging():
    # Runs before every test in this module (pytest equivalent of setUp).
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%%(asctime)s %%(name)s:%%(lineno)d %%(levelname)s : %%(message)s',
    )


def _start_app(cleep_session, start=True):
    # Build an isolated app instance. With start=True the module is started
    # (configure + start). Use start=False to test _on_configure yourself.
    module = cleep_session.setup(%(MODULE_NAME_CAPITALIZED)s)
    if start:
        cleep_session.start_module(module)
    return module


def test_get_module_config(cleep_session):
    module = _start_app(cleep_session)

    config = module.get_module_config()

    assert isinstance(config, dict)


def test__configure(cleep_session):
    module = _start_app(cleep_session, start=False)
    # Add mocks here if needed, e.g.:
    # cleep_session.add_mock_command(cleep_session.make_mock_command('get_modules', data={}))

    module._configure()

    # Assert side effects (commands / events / return values):
    # cleep_session.assert_command_called('get_modules')
    # cleep_session.assert_event_called('system.device.delete')


def test_execute_command(cleep_session):
    module = _start_app(cleep_session)
    # Add mocks here if needed

    result = module.execute_command()

    assert result is True
    # cleep_session.assert_command_called_with('some_command', {'key': 'value'})
    # cleep_session.assert_event_called_with('some.event', {'key': 'value'})
"""
    CONFTEST_DEFAULT = """# -*- coding: utf-8 -*-
# Provides the cleep_session fixture for module tests.
pytest_plugins = ('cleep.libs.tests.fixtures',)
"""
    PYTEST_INI_DEFAULT = """[pytest]
pythonpath = .
testpaths = tests
python_files = test_*.py
markers =
    functional: real OS/device tests (CLEEP_FUNCTIONAL_TESTS / modtests --functional)
filterwarnings =
    ignore::DeprecationWarning:passlib.*
"""
    DOCS_CONF_PY = """# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.abspath('../'))

project = ''
copyright = ''
author = ''
version = ''
release = ''
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.githubpages',
    'sphinx.ext.napoleon',
]
source_suffix = '.rst'
master_doc = 'index'
language = None
exclude_patterns = [
    '_build',
    'Thumbs.db',
    '.DS_Store',
    '**/*.pyc',
]
add_module_names = False
pygments_style = None
html_static_path = [
    '_static',
]
html_css_files = [
    '_static/cleep.css',
]
html_theme = 'sphinx_rtd_theme'
todo_include_todos = True
html_theme_options = {
    'prev_next_buttons_location': None,
    'style_external_links': True,
    'style_nav_header_background': '#607d8b',
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 6,
    'includehidden': False,
}

def setup(app):
    app.add_css_file('cleep.css')
    """
    DOCS_INDEX_RST = """%(TITLE)s
%(LINE)s

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   source/modules

Indices and tables
==================

* :ref:\`genindex\`
* :ref:\`modindex\`
* :ref:\`search\`
    """
    DOCS_CLEEP_CSS = """.wy-nav-side {
    background: #90a4ae !important;
}
.wy-side-nav-search {
    background: #607d8b !important;
}
.rst-content dl:not(.docutils) dt {
    color: #d32f2f !important;
    background: #ffcdd2 !important;
    border-top: solid 3px #b71c1c !important;
 }
.rst-content dl:not(.docutils) dl dt {
    border: none !important;
    border-left: solid 3px #d32f2f !important;
    background: #eceff1 !important;
    color: #607d8b !important;
}
a:visited, a:hover {
    color: #d32f2f;
}
a {
    color: #000000;
}
a:visited.icon.icon-home, a.icon.icon-home {
    color: #FFFFFF !important;
}
a:hover.icon.icon-home {
    color: #d32f2f;
}
.wy-menu-vertical header,.wy-menu-vertical p.caption {
    color: #000000;
}
    """

    def __init__(self):
        """
        Constructor
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    def __base_class_extras(self, base_class):
        """
        Return skeleton extras for the selected core base class.
        """
        extras = {
            "CleepModule": {
                "extra_imports": "",
                "extra_members": "",
                "extra_methods": "",
            },
            "CleepResources": {
                "extra_imports": "",
                "extra_members": """
    # Exclusive peripherals claimed through CriticalResources.
    # Keys are catalogue names (see cleep.libs.internals.resource_catalog).
    # permanent=True: hold at boot (only one app may do this per resource).
    # permanent=False: acquire on demand with _need_resource / _need_resources.
    MODULE_RESOURCES = {
        # 'audio.playback': {'permanent': False},
    }
""",
                "extra_methods": """
    def _resource_acquired(self, resource_name):
        \\"\\"\\"
        Called when a requested resource was granted (compatibility hook).

        Prefer overriding _on_resource_granted(session) for session-aware apps.

        Args:
            resource_name (str): catalogue resource name
        \\"\\"\\"
        self.logger.info('Resource granted: %%s', resource_name)

    def _resource_needs_to_be_released(self, resource_name):
        \\"\\"\\"
        Called when another app needs a resource you hold, or after revoke.

        Stop using the peripheral and call _release_resource / _release_resource_session.

        Args:
            resource_name (str): catalogue resource name
        \\"\\"\\"
        self.logger.info('Resource must be released: %%s', resource_name)
""",
            },
            "CleepRenderer": {
                "extra_imports": ", RENDERERS",
                "extra_members": """
    # What kind of renderer this is (AUDIO, DISPLAY, HOMEAUTOMATION, …).
    RENDERER_TYPE = RENDERERS.UNKNOWN
    # Profile classes this app can render (from cleep profiles).
    RENDERER_PROFILES = []
""",
                "extra_methods": """
    def on_render(self, profile_name, profile_values):
        \\"\\"\\"
        Render a profile published on the bus (display text, play a sound, …).

        Args:
            profile_name (str): profile class name
            profile_values (dict): field values for that profile
        \\"\\"\\"
        self.logger.info('on_render %%s %%s', profile_name, profile_values)
""",
            },
            "CleepExternalBus": {
                "extra_imports": "",
                "extra_members": "",
                "extra_methods": """
    def _send_command_to_peer(
        self, command, to, peer_uuid, params=None, timeout=5.0, manual_response=None
    ):
        \\"\\"\\"
        Transport-specific: deliver a Cleep command to a remote peer.

        Use _get_peer_device_info() when you need uuid / auth / remote URLs to
        advertise on your bus. Must be implemented for peer RPC to work.

        Args:
            command (str): command name
            to (str): recipient module name (None to broadcast, no response)
            peer_uuid (str): target peer uuid
            params (dict|None): command parameters
            timeout (float): seconds to wait for a response
            manual_response (callable|None): filled by the bus when applicable
        \\"\\"\\"
        raise NotImplementedError('_send_command_to_peer must be implemented')

    def _send_event_to_peer(self, event_name, peer_uuid, params=None):
        \\"\\"\\"
        Transport-specific: push an event to a remote peer.

        Args:
            event_name (str): event name
            peer_uuid (str): target peer uuid
            params (dict|None): event parameters
        \\"\\"\\"
        raise NotImplementedError('_send_event_to_peer must be implemented')
""",
            },
            "CleepRemoteAccessModule": {
                "extra_imports": "",
                "extra_members": "",
                "extra_methods": """
    def get_remote_url_refresh(self):
        \\"\\"\\"
        Tell CleepDesktop how to re-resolve this app's public URL by itself.

        Return None when the provider cannot be queried from outside the device
        (no API / missing credentials). Otherwise return a descriptor payload
        (see CleepRemoteAccessModule in cleep.core).

        From _on_start, open your tunnel, publish the URL when ready
        (``register_remote_access_url``), and call ``_setup_lan_gateway()``.

        Returns:
            dict|None: refresh descriptor, or None if unsupported
        \\"\\"\\"
        return None
""",
            },
        }
        return extras.get(base_class, extras["CleepModule"])

    @staticmethod
    def _skel_str(value, default="TODO"):
        """Sanitize a free-text value for embedding as a single-quoted Python string."""
        text = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
        for char in ("\\", "'", '"', "`", "$"):
            text = text.replace(char, "")
        if not text:
            return "'%s'" % default
        return "'%s'" % text

    @staticmethod
    def _skel_url(value):
        """Sanitize a URL for MODULE_URLSITE (None when empty)."""
        text = str(value or "").strip()
        for char in ("\\", "'", '"', "`", "$", " "):
            text = text.replace(char, "")
        if not text:
            return "None"
        return "'%s'" % text

    def create(
        self,
        module_name,
        base_class="CleepModule",
        category="APPLICATION",
        tags=None,
        deps=None,
        description=None,
        long_description=None,
        url=None,
        firmware=None,
        with_firmware=False,
    ):
        """
        Create module skeleton

        Args:
            module_name (string): module name
            base_class (string): core base class (CleepModule, CleepRenderer, ...)
            category (string): CATEGORIES value
            tags (list): optional MODULE_TAGS values
            deps (list): optional MODULE_DEPS values (other Cleep apps)
            description (string): optional MODULE_DESCRIPTION
            long_description (string): optional MODULE_LONGDESCRIPTION
            url (string): optional MODULE_URLSITE (homepage / GitHub / service)
            firmware (string): optional firmware kind (``uf2`` or ``micropython``)
            with_firmware (bool): deprecated alias for ``firmware="uf2"``
        """
        module_name = re.sub('[^0-9a-zA-Z]+', '', module_name).lstrip('0123456789').lower()
        self.logger.debug('Module name to create: %s' % module_name)
        path = os.path.join(config.MODULES_SRC, module_name)
        self.logger.info('Creating module "%s" in "%s"' % (module_name, path))

        if base_class not in self.BASE_CLASS_CHOICES:
            self.logger.error('Unsupported base class "%s"' % base_class)
            return False
        category = (category or "APPLICATION").upper()
        from cleep.common import CATEGORIES
        if category not in CATEGORIES.ALL:
            self.logger.error('Unsupported category "%s"' % category)
            return False

        # Legacy bool flag from older callers / --firmware without kind.
        if firmware is None and with_firmware:
            firmware = "uf2"
        if firmware is not None:
            firmware = str(firmware).strip().lower()
            if firmware not in self.FIRMWARE_KINDS:
                self.logger.error('Unsupported firmware kind "%s"' % firmware)
                return False

        if os.path.exists(path):
            self.logger.error('Module "%s" already exists in "%s"' % (module_name, path))
            return False

        tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
        tags_repr = "[" + ", ".join("'%s'" % tag.replace("'", "") for tag in tags) + "]"
        deps_clean = []
        for dep in deps or []:
            dep_name = re.sub('[^0-9a-zA-Z]+', '', str(dep)).lstrip('0123456789').lower()
            if dep_name and dep_name != module_name and dep_name not in deps_clean:
                deps_clean.append(dep_name)
        deps_repr = "[" + ", ".join("'%s'" % dep for dep in deps_clean) + "]"
        description_repr = self._skel_str(description)
        long_description_repr = self._skel_str(long_description)
        url_repr = self._skel_url(url)
        extras = self.__base_class_extras(base_class)

        title = 'Welcome to %s\'s documentation!' % module_name.capitalize()
        templates = {
            'ANGULAR_SERVICE': self.ANGULAR_SERVICE_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'ANGULAR_CONTROLLER': self.ANGULAR_CONTROLLER_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'ANGULAR_CONTROLLER_TEMPLATE': self.ANGULAR_CONTROLLER_TEMPLATE_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'DESC': self.DESC_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'PYTHON_MODULE': self.PYTHON_MODULE_SKEL % {
                'MODULE_NAME': module_name,
                'MODULE_NAME_CAPITALIZED': module_name.capitalize(),
                'BASE_CLASS': base_class,
                'MODULE_TAGS': tags_repr,
                'MODULE_DEPS': deps_repr,
                'MODULE_DESCRIPTION': description_repr,
                'MODULE_LONGDESCRIPTION': long_description_repr,
                'MODULE_URLSITE': url_repr,
                'MODULE_CATEGORY': category,
                'EXTRA_IMPORTS': extras['extra_imports'],
                'EXTRA_MEMBERS': extras['extra_members'],
                'EXTRA_METHODS': extras['extra_methods'],
            },
            'TEST_DEFAULT': self.TEST_DEFAULT % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'CONFTEST_DEFAULT': self.CONFTEST_DEFAULT,
            'PYTEST_INI_DEFAULT': self.PYTEST_INI_DEFAULT,
            'DOCS_CONF_PY': self.DOCS_CONF_PY % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'DOCS_INDEX_RST': self.DOCS_INDEX_RST % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize(), 'TITLE': title, 'LINE': '='*len(title)},
            'DOCS_CLEEP_CSS': self.DOCS_CLEEP_CSS,
            'CHANGELOG': self.CHANGELOG,
            'GIT_IGNORE': self.GIT_IGNORE,
        }

        c = Console()
        resp = c.command("""
/bin/mkdir -p "%(MODULE_DIR)s/backend"
/usr/bin/touch "%(MODULE_DIR)s/backend/__init__.py"
/bin/echo "%(PYTHON_MODULE)s" > %(MODULE_DIR)s/backend/%(MODULE_NAME)s.py
/bin/mkdir -p "%(MODULE_DIR)s/frontend"
/bin/echo "%(DESC)s" > %(MODULE_DIR)s/frontend/desc.json
/bin/echo "%(ANGULAR_SERVICE)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.service.js
/bin/echo "%(ANGULAR_CONTROLLER)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.config.js
/bin/echo "%(ANGULAR_CONTROLLER_TEMPLATE)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.config.html
/bin/mkdir -p "%(MODULE_DIR)s/tests"
/bin/echo "from gevent import monkey" > "%(MODULE_DIR)s/tests/__init__.py"
/bin/echo "monkey.patch_all()" >> "%(MODULE_DIR)s/tests/__init__.py"
/bin/echo "%(TEST_DEFAULT)s" > %(MODULE_DIR)s/tests/test_%(MODULE_NAME)s.py
/bin/echo "%(CONFTEST_DEFAULT)s" > %(MODULE_DIR)s/tests/conftest.py
/bin/echo "%(PYTEST_INI_DEFAULT)s" > %(MODULE_DIR)s/pytest.ini
/bin/mkdir -p "%(MODULE_DIR)s/docs"
/bin/echo "%(DOCS_CONF_PY)s" > %(MODULE_DIR)s/docs/conf.py
/bin/echo "%(DOCS_INDEX_RST)s" > %(MODULE_DIR)s/docs/index.rst
/bin/mkdir -p "%(MODULE_DIR)s/docs/_static"
/bin/echo "%(DOCS_CLEEP_CSS)s" > %(MODULE_DIR)s/docs/_static/cleep.css
/bin/echo "%(CHANGELOG)s" > %(MODULE_DIR)s/CHANGELOG.md
/bin/echo "%(GIT_IGNORE)s" > %(MODULE_DIR)s/.gitignore
""" % {
            'MODULE_DIR': path,
            'MODULE_NAME': module_name,
            'DESC': templates['DESC'],
            'ANGULAR_SERVICE': templates['ANGULAR_SERVICE'],
            'ANGULAR_CONTROLLER': templates['ANGULAR_CONTROLLER'],
            'ANGULAR_CONTROLLER_TEMPLATE': templates['ANGULAR_CONTROLLER_TEMPLATE'],
            'PYTHON_MODULE': templates['PYTHON_MODULE'],
            'TEST_DEFAULT': templates['TEST_DEFAULT'],
            'CONFTEST_DEFAULT': templates['CONFTEST_DEFAULT'],
            'PYTEST_INI_DEFAULT': templates['PYTEST_INI_DEFAULT'],
            'DOCS_CONF_PY': templates['DOCS_CONF_PY'],
            'DOCS_INDEX_RST': templates['DOCS_INDEX_RST'],
            'DOCS_CLEEP_CSS': templates['DOCS_CLEEP_CSS'],
            'CHANGELOG': templates['CHANGELOG'],
            'GIT_IGNORE': templates['GIT_IGNORE'],
        }, 10)
        if resp['killed'] or resp['returncode'] != 0:
            self.logger.error('Error occured while creating application: %s' % ('killed' if resp['killed'] else resp['stderr']))
            shutil.rmtree(path)
            return False

        if firmware:
            if not self.__scaffold_firmware(c, path, module_name, firmware):
                shutil.rmtree(path)
                return False

        self.logger.info('Done')
        return True

    def __scaffold_firmware(self, console, module_path, module_name, firmware_kind):
        """
        Write firmwares/<module>/ skeleton for the given kind.

        Args:
            console (Console): command runner
            module_path (string): module root under MODULES_SRC
            module_name (string): module name
            firmware_kind (string): ``uf2`` or ``micropython``

        Returns:
            bool: True on success
        """
        fw_dir = os.path.join(module_path, "firmwares", module_name)
        fw_ctx = {
            "MODULE_NAME": module_name,
            "MODULE_NAME_CAPITALIZED": module_name.capitalize(),
            "FIRMWARE_KIND": firmware_kind,
        }
        # Single-quoted echoes: CMakeLists contains $ENV{...} that must not expand.
        if firmware_kind == "uf2":
            fw_cmd = """
/bin/mkdir -p "%(FW_DIR)s"
/bin/echo '%(MANIFEST)s' > "%(FW_DIR)s/firmware.manifest"
/bin/echo '%(CMAKE)s' > "%(FW_DIR)s/CMakeLists.txt"
/bin/echo '%(MAIN_C)s' > "%(FW_DIR)s/main.c"
""" % {
                "FW_DIR": fw_dir,
                "MANIFEST": (self.FIRMWARE_MANIFEST_SKEL % fw_ctx).replace("'", "'\\''"),
                "CMAKE": (self.FIRMWARE_CMAKE_SKEL % fw_ctx).replace("'", "'\\''"),
                "MAIN_C": self.FIRMWARE_MAIN_C_SKEL.replace("'", "'\\''"),
            }
        else:
            fw_cmd = """
/bin/mkdir -p "%(FW_DIR)s/files"
/bin/echo '%(MANIFEST)s' > "%(FW_DIR)s/firmware.manifest"
/bin/echo '%(MAIN_PY)s' > "%(FW_DIR)s/files/main.py"
""" % {
                "FW_DIR": fw_dir,
                "MANIFEST": (self.FIRMWARE_MANIFEST_SKEL % fw_ctx).replace("'", "'\\''"),
                "MAIN_PY": self.FIRMWARE_MAIN_PY_SKEL.replace("'", "'\\''"),
            }

        fw_resp = console.command(fw_cmd, 10)
        if fw_resp["killed"] or fw_resp["returncode"] != 0:
            self.logger.error(
                "Error creating firmware skeleton: %s",
                "killed" if fw_resp["killed"] else fw_resp["stderr"],
            )
            return False
        return True

    def delete(self, module_name):
        """
        Delete installed files for specified  module

        Args:
            module_name (string): module name
        """
        #build all module paths
        paths = [
            os.path.join(config.MODULES_DST, module_name),
            os.path.join(config.MODULES_HTML_DST, module_name),
            os.path.join(config.MODULES_SCRIPTS_DST, module_name),
        ]
        self.logger.info('Deleting module "%s" in "%s"' % (module_name, paths))
        
        deleted = False
        for path in paths:
            if os.path.exists(path):
                shutil.rmtree(path)
                self.logger.debug('Directory "%s" deleted' % path)
                deleted = True

        if not deleted:
            self.logger.info('Nothing has been deleted')

        return True

