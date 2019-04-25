#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
from . import config
import urllib3
import json

class CleepApi():
    """
    Cleep api helper
    """

    COMMAND_URL = 'http://localhost/command'

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        self.http = urllib3.PoolManager()

    def restart_backend(self):
        """
        Send command to restart backend
        """
        self.logger.info('Restarting backend')
        data = {'to':'system', 'command':'restart', 'delay':0.0}
        self.__post(self.COMMAND_URL, data)

    def restart_frontend(self):
        """
        Send command to restart frontend
        """
        self.logger.info('Restarting frontend')
        data = {'to':'developer', 'command':'restart_frontend'}
        self.__post(self.COMMAND_URL, data)

    def __post(self, url, data):
        """
        Post data to specified url

        Args:
            url (string): request url
            data (dict): request data
        """
        status = None
        resp_data = None
        try:
            data_json = json.dumps(data).encode('utf-8')
            resp = self.http.request('POST', url, body=data_json, header={'Content-Type': 'application/json'})
            resp_data = json.loads(resp_raw.data.decode('utf-8'))
            self.logger.debug('Response[%s]: %s' % (resp.status, resp_data))
        except Exception as e:
            if self.logger.getEffectiveLevel()==logging.DEBUG:
                self.logger.exception('Error occured while requesting "%s"' % url)
            else:
                self.logger.error('Error occured while requesting "%s": %s' % (url, str(e)))
        return (status, resp_data)

