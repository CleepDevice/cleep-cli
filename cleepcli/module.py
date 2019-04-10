#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from .console import Console
import logging
from . import config
import shutil

class Module():
    """
    Module class
    """

    DESC_SKEL = """{
    "icon": "help-circle-outline",
    "global": {
        "js": ["%(MODULE_NAME)s.service.js"],
        "html": [],
        "css": []
    },
    "config": {
        "js": ["%(MODULE_NAME)s.config.js"],
        "html": ["%(MODULE_NAME)s.config.html"]
    }
}
    """
    ANGULAR_SERVICE_SKEL = """/**
 * %(MODULE_NAME_CAPITALIZED)s service
 * Handle %(MODULE_NAME)s application requests
 */
var %(MODULE_NAME)sService = function(\$q, \$rootScope, rpcService) {
    var self = this;

    /**
     * Catch x.x.x events
     */
    \$rootScope.\$on('x.x.x', function(event, uuid, params) {
    });
}
    
var RaspIot = angular.module('RaspIot');
RaspIot.service('%(MODULE_NAME)sService', ['\$q', '\$rootScope', 'rpcService', %(MODULE_NAME)sService]);
    """
    ANGULAR_CONTROLLER_SKEL = """/**
 * %(MODULE_NAME_CAPITALIZED)s config directive
 * Handle %(MODULE_NAME)s application configuration
 */
var %(MODULE_NAME)sConfigDirective = function(\$rootScope, %(MODULE_NAME)sService, raspiotService) {

    var %(MODULE_NAME)sConfigController = function() {
        var self = this;

        /**
         * Init controller
         */
        self.init = function() {
            // TODO
        };
    };

    var %(MODULE_NAME)sConfigLink = function(scope, element, attrs, controller) {
        controller.init();
    };

    return {
        templateUrl: '%(MODULE_NAME)s.config.html',
        replace: true,
        scope: true,
        controller: %(MODULE_NAME)sConfigController,
        controllerAs: '%(MODULE_NAME)sCtl',
        link: %(MODULE_NAME)sConfigLink
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('%(MODULE_NAME)sConfigDirective', ['\$rootScope', '%(MODULE_NAME)sService', 'raspiotService', %(MODULE_NAME)sConfigDirective]);
    """
    ANGULAR_CONTROLLER_TEMPLATE_SKEL = """<div layout="column" layout-padding ng-cloak>

    <md-list>
    </md-list>

</div>
    """
    PYTHON_MODULE_SKEL = """#!/usr/bin/env python
# -*- coding: utf-8 -*-

from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from raspiot.raspiot import RaspIotModule

class %(MODULE_NAME_CAPITALIZED)s(RaspIotModule):
    \\"\\"\\"
    %(MODULE_NAME_CAPITALIZED)s application
    \\"\\"\\"
    MODULE_AUTHOR = u'TODO'
    MODULE_VERSION = u'0.0.0'
    MODULE_DEPS = []
    MODULE_DESCRIPTION = u'TODO'
    MODULE_LONGDESCRIPTION = u'TODO'
    MODULE_TAGS = []
    MODULE_CATEGORY = u'TODO'
    MODULE_COUNTRY = None
    MODULE_URLINFO = None
    MODULE_URLHELP = None
    MODULE_URLSITE = None
    MODULE_URLBUGS = None

    MODULE_CONFIG_FILE = u'%(MODULE_NAME)s.conf'
    DEFAULT_CONFIG = {}

    def __init__(self, bootstrap, debug_enabled):
        \\"\\"\\"
        Constructor

        Params:
            bootstrap (dict): bootstrap objects
            debug_enabled: debug status
        \\"\\"\\"
        RaspIotModule.__init__(self, bootstrap, debug_enabled)

    def _configure(self):
        \\"\\"\\"
        Configure module
        \\"\\"\\"
        # launch here custom thread or action that takes time to process
        pass

    def _stop(self):
        \\"\\"\\"
        Stop module
        \\"\\"\\"
        # stop here your custom threads or close external connections
        pass

    def event_received(self, event):
        \\"\\"\\"
        Event received

        Params:
            event (MessageRequest): event data
        \\"\\"\\"
        # execute here actions when you receive an event:
        #  - on time event => cron task
        #  - on alert event => send email or push message
        #  - ...
        pass
    """

    def __init__(self):
        """
        Constructor
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    def create(self, module_name):
        """
        Create module skeleton

        Args:
            module_name (string): module name
        """
        path = os.path.join(config.MODULES_SRC, module_name)
        self.logger.info('Creating module "%s" in "%s"' % (module_name, path))
        
        if os.path.exists(path):
            self.logger.error('Module "%s" already exists in "%s"' % (module_name, path))
            return False

        templates = {
            'ANGULAR_SERVICE': self.ANGULAR_SERVICE_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'ANGULAR_CONTROLLER': self.ANGULAR_CONTROLLER_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'ANGULAR_CONTROLLER_TEMPLATE': self.ANGULAR_CONTROLLER_TEMPLATE_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'DESC': self.DESC_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()},
            'PYTHON_MODULE': self.PYTHON_MODULE_SKEL % {'MODULE_NAME': module_name, 'MODULE_NAME_CAPITALIZED': module_name.capitalize()}
        }

        c = Console()
        resp = c.command("""
/bin/mkdir -p %(MODULE_DIR)s/backend
/usr/bin/touch %(MODULE_DIR)s/backend/__init__.py
/bin/echo "%(PYTHON_MODULE)s" > %(MODULE_DIR)s/backend/%(MODULE_NAME)s.py
/bin/mkdir -p %(MODULE_DIR)s/frontend
/bin/echo "%(DESC)s" > %(MODULE_DIR)s/frontend/desc.json
/bin/echo "%(ANGULAR_SERVICE)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.service.js
/bin/echo "%(ANGULAR_CONTROLLER)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.config.js
/bin/echo "%(ANGULAR_CONTROLLER_TEMPLATE)s" > %(MODULE_DIR)s/frontend/%(MODULE_NAME)s.config.html
/bin/mkdir -p %(MODULE_DIR)s/tests
/usr/bin/touch %(MODULE_DIR)s/tests/__init__.py
        """ % {
            'MODULE_DIR': path,
            'MODULE_NAME': module_name,
            'DESC': templates['DESC'],
            'ANGULAR_SERVICE': templates['ANGULAR_SERVICE'],
            'ANGULAR_CONTROLLER': templates['ANGULAR_CONTROLLER'],
            'ANGULAR_CONTROLLER_TEMPLATE': templates['ANGULAR_CONTROLLER_TEMPLATE'],
            'PYTHON_MODULE': templates['PYTHON_MODULE']
        }, 10)
        if resp['error'] or resp['killed']:
            self.logger.error('Error occured while pulling repository: %s' % ('killed' if resp['killed'] else resp['stderr']))
            shutil.rmtree(path)
            return False
        
        return True

