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
# Local commands (frontend restart, docs, CI) use this socket so they
# stay available when TCP requires the Cleep password.
LOCAL_SOCKET_PATH = '/run/cleep/rpc.sock'


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


def local_socket_available(path=None):
    """
    Return True when the local Cleep RPC socket exists.
    """
    return os.path.exists(path or LOCAL_SOCKET_PATH)


def _http_path(url):
    """
    Return the path and query of an RPC URL.
    """
    parts = urllib.parse.urlsplit(url)
    path = parts.path or '/'
    if parts.query:
        path += '?' + parts.query
    return path


def _read_http_response(sock):
    """
    Read one HTTP/1.1 response from a socket.

    Returns:
        tuple: status code (int), body (bytes)
    """
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    if b'\r\n\r\n' not in data:
        raise Exception('Incomplete HTTP response from local socket')

    header_blob, rest = data.split(b'\r\n\r\n', 1)
    lines = header_blob.split(b'\r\n')
    status_code = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        if b':' not in line:
            continue
        name, value = line.split(b':', 1)
        headers[name.decode('ascii').lower()] = value.strip().decode('ascii')

    if headers.get('transfer-encoding', '').lower() == 'chunked':
        body = _read_chunked(sock, rest)
    elif 'content-length' in headers:
        length = int(headers['content-length'])
        while len(rest) < length:
            chunk = sock.recv(4096)
            if not chunk:
                break
            rest += chunk
        body = rest[:length]
    else:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            rest += chunk
        body = rest
    return status_code, body


def _read_chunked(sock, pending):
    """
    Decode a chunked HTTP body.
    """
    data = pending
    body = b''
    while True:
        while b'\r\n' not in data:
            chunk = sock.recv(4096)
            if not chunk:
                return body
            data += chunk
        size_line, data = data.split(b'\r\n', 1)
        size = int(size_line.split(b';', 1)[0], 16)
        if size == 0:
            return body
        while len(data) < size + 2:
            chunk = sock.recv(4096)
            if not chunk:
                return body
            data += chunk
        body += data[:size]
        data = data[size + 2:]


def request_over_local_socket(method, url, json_body=None, timeout=30.0, path=None):
    """
    Send one HTTP request through the local Cleep Unix socket.

    Args:
        method (str): HTTP method
        url (str): request URL, used for the path when path is omitted
        json_body (dict): JSON body for POST
        timeout (float): socket timeout in seconds
        path (str): socket path

    Returns:
        requests.Response
    """
    import socket
    from requests import Response

    socket_path = path or LOCAL_SOCKET_PATH
    http_path = _http_path(url)
    body = b''
    headers = [
        '%s %s HTTP/1.1' % (method, http_path),
        'Host: localhost',
        'Accept: application/json',
        'Connection: close',
    ]
    if json_body is not None:
        body = json.dumps(json_body).encode('utf-8')
        headers.append('Content-Type: application/json')
        headers.append('Content-Length: %s' % len(body))
    raw = ('\r\n'.join(headers) + '\r\n\r\n').encode('ascii') + body

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(socket_path)
        sock.sendall(raw)
        status_code, payload = _read_http_response(sock)
    finally:
        sock.close()

    response = Response()
    response.status_code = status_code
    response._content = payload
    response.url = 'http://localhost' + http_path
    response.encoding = 'utf-8'
    return response


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
        # Maximum wait. systemctl returns as soon as the service has restarted.
        resp = c.command(cmd, timeout=60)
        self.logger.debug('Systemctl resp: %s' % resp)
        if resp['killed'] or resp['returncode'] != 0:
            self.logger.error('Error restarting cleep backend')
            return False

        return True

    def restart_frontend(self):
        """
        Send command to restart frontend
        """
        self.logger.info('Restarting frontend')
        data = {'to':'developer', 'command':'restart_frontend'}
        result = self.__post(self.command_url, data)
        if not result or result[0] != 200:
            self.logger.error('Error restarting cleep frontend')
            return False
        return True

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
            raise Exception("Unable to call cleep %s endpoint" % url)
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
            if local_socket_available():
                resp = request_over_local_socket('POST', url, json_body=data)
            else:
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
            if local_socket_available():
                resp = request_over_local_socket('GET', url)
            else:
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
