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

        if not rpc_url:
            rpc_url = 'http://0.0.0.0:80'
        self.logger.debug('RPC url: %s', rpc_url)

        self.command_url = urllib.parse.urljoin(rpc_url, "/command")
        self.get_doc_url = urllib.parse.urljoin(rpc_url, "/doc/")
        self.check_doc_url = urllib.parse.urljoin(rpc_url, "/doc/check/")

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

    def get_documentation(self, module_name):
        """
        Call endpoint to get documentation for specified application

        Args:
            module_name (str): module name

        Returns:
            dict: cleep command response
        """
        url = urllib.parse.urljoin(self.get_doc_url, module_name)

        (status_code, resp) = self.__get(url)

        if status_code != 200:
            raise Exception("Unable to call cleep %s endpoint" % url)
        if resp.get("error"):
            raise Exception(resp.get("message", "No error message"))
        return resp.get("data")

    def check_documentation(self, module_name):
        """
        Call endpoint to check documentation for specified application

        Args:
            module_name (str): module name

        Returns:
            dict: cleep command response
        """
        url = urllib.parse.urljoin(self.check_doc_url, module_name)

        (status_code, resp) = self.__get(url)

        if status_code != 200:
            raise Exception("Unable to call cleep %s endpoint", url)
        return resp

    def __post(self, url, data):
        """
        Post data to specified url

        Args:
            url (string): request url
            data (dict): request data

        Returns:
            tuple: post response::

                (status code (int), data (any))
        
            None: if error occured
        """
        try:
            self.logger.debug("POST url: %s", url)
            resp = requests.post(url, json=data, verify=False)
            resp_data = resp.json()
            self.logger.debug('Response[%s]: %s', resp.status_code, resp_data)
            return (resp.status_code, resp_data)
        except Exception as e:
            if self.logger.getEffectiveLevel()==logging.DEBUG:
                self.logger.exception('Error occured while requesting POST "%s"' % url)
            else:
                self.logger.error('Error occured while requesting POST "%s": %s' % (url, str(e)))

    def __get(self, url):
        """
        Get data to specified url

        Args:
            url (string): request url

        Returns:
            tuple: get response::

                (status code (int), data (any))

            None: if error occured
        """
        try:
            self.logger.debug("GET url: %s", url)
            resp = requests.get(url, verify=False)
            resp_data = resp.json()
            self.logger.debug('Response[%s]: %s', resp.status_code, resp_data)
            return (resp.status_code, resp_data)
        except Exception as e:
            if self.logger.getEffectiveLevel()==logging.DEBUG:
                self.logger.exception('Error occured while requesting GET "%s"' % url)
            else:
                self.logger.error('Error occured while requesting GET "%s": %s' % (url, str(e)))

        return (404, {})
