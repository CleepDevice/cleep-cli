#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
from . import config
import requests

class CleepApi():
    """
    Cleep api helper
    """

    COMMAND_URL = 'http://localhost/command'

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def restart_backend(self):
        """
        Send command to restart backend
        """
        self.logger.info('Restarting backend')
        resp = requests.post(self.COMMAND_URL, json={'to':'system', 'command':'restart', 'delay':0.0})
        self.logger.debug('Response[%s]: %s' % (resp.status_code, resp.json()))

    def restart_frontend(self):
        """
        Send command to restart frontend
        """
        self.logger.info('Restarting frontend')
        resp = requests.post(self.COMMAND_URL, json={'to':'developer', 'command':'restart_frontend'})
        self.logger.debug('Response[%s]: %s' % (resp.status_code, resp.json()))
        

