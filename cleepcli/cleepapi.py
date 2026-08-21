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

requests.packages.urllib3.disable_warnings()

# Cleep 0.1+ serves HTTPS by default; older versions listen on HTTP only.
DEFAULT_RPC_URLS = (
    'https://127.0.0.1:443',
    'http://127.0.0.1:80',
)


def resolve_rpc_url(urls=None, timeout=3.0):
    """
    Return the first reachable Cleep RPC base URL.

    Tries HTTPS first (Cleep default), then HTTP. Self-signed certificates
    are accepted. A candidate is considered reachable as soon as a TCP/TLS
    session is established (any HTTP status).

    Args:
        urls (tuple): candidate base URLs
        timeout (float): per-candidate timeout in seconds

    Returns:
        str: reachable base URL (no trailing slash)

    Raises:
        Exception: if none of the candidates respond
    """
    logger = logging.getLogger('CleepApi')
    candidates = urls or DEFAULT_RPC_URLS
    last_error = None
    for base in candidates:
        health_url = urllib.parse.urljoin(base.rstrip('/') + '/', 'health')
        try:
            logger.debug('Probing Cleep RPC %s', health_url)
            requests.get(health_url, timeout=timeout, verify=False)
            logger.info('Using Cleep RPC %s', base)
            return base.rstrip('/')
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.SSLError) as error:
            logger.debug('Cleep RPC not reachable at %s: %s', base, error)
            last_error = error

    raise Exception('Unable to reach Cleep RPC (tried %s): %s' % (', '.join(candidates), last_error))


class CleepApi():
    """
    Cleep api helper
    """

    def __init__(self, rpc_url):
        self.logger = logging.getLogger(self.__class__.__name__)

        if not rpc_url:
            try:
                rpc_url = resolve_rpc_url()
            except Exception:
                rpc_url = DEFAULT_RPC_URLS[0]
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
