#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
from . import config
from .console import Console
import requests
import json
import urllib.parse

class CleepApi():
    """
    Cleep api helper
    """

    def __init__(self, rpc_url):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.command_url = urllib.parse.urljoin(rpc_url, "/command")

    def restart_backend(self):
        """
        Send command to restart backend
        """
        self.logger.info('Restarting backend')

        cmd = '/bin/systemctl restart cleep'
        c = Console()
        resp = c.command(cmd)
        self.logger.debug('Systemctl resp: %s' % resp)
        if resp['error'] or resp['killed']:
            self.logger.error('Error restarting cleep backend')
            return False

        return True

    def restart_frontend(self):
        """
        Send command to restart frontend
        """
        self.logger.info('Restarting frontend')
        data = {'to':'developer', 'command':'restart_frontend'}
        self.__post(self.command_url, data)

    def __post(self, url, data):
        """
        Post data to specified url

        Args:
            url (string): request url
            data (dict): request data
        """
        try:
            resp = requests.post(url, json=data, verify=False)
            resp_data = resp.json()
            self.logger.debug('Response[%s]: %s', resp.status_code, resp_data)
            return (resp.status_code, resp_data)
        except Exception as e:
            if self.logger.getEffectiveLevel()==logging.DEBUG:
                self.logger.exception('Error occured while requesting "%s"' % url)
            else:
                self.logger.error('Error occured while requesting "%s": %s' % (url, str(e)))

