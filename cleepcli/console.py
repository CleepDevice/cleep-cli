#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
from threading import Timer, Thread
try: # pragma: no cover
    from Queue import Queue, Empty
except ImportError: # pragma: no cover
    from queue import Queue, Empty  # python 3.x
import os
import signal
import logging
import re

ON_POSIX = 'posix' in sys.builtin_module_names

class EndlessConsole(Thread):
    """
    Helper class to execute long command line (system update...)
    This kind of console doesn't kill command line after timeout. It just let command running
    until end of it or if user explicitely requests to stop (or kill) it.

    This class implements thread and is non blocking unless you use join function after starting it::

        c = EndlessConsole(mycmd, myclb, myendclb)
        c.join()

    Notes:
        Subprocess output async reading copied from https://stackoverflow.com/a/4896288
    """

    def __init__(self, command, callback, callback_end=None):
        """
        Constructor

        Args:
            command (string): command to execute
            callback (function): callback when message is received (the function will be called with 2 arguments: stdout (string) and stderr (string))
            callback_end (function): callback when process is terminated (the function will be called with 2 arguments: return code (string) and killed (bool))
        """
        Thread.__init__(self, daemon=True)

        # members
        self.command = command
        self.callback = callback
        self.callback_end = callback_end
        self.logger = logging.getLogger(self.__class__.__name__)
        # self.logger.setLevel(logging.DEBUG)
        self.running = True
        self.killed = False
        self.__start_time = 0
        self.__stdout_queue = Queue()
        self.__stderr_queue = Queue()
        self.__stdout_thread = None
        self.__stderr_thread = None

    def __del__(self):
        """
        Destructor
        """
        self.__stop()

    def __enqueue_output(self, output, queue):
        for line in iter(output.readline, b''):
            if not self.running:
                break
            queue.put(line.decode('utf-8').rstrip())
        try:
            output.close()
        except: # pragma: no cover
            pass

    def get_start_time(self):
        """
        Return process start time

        Returns:
            float: start timestamp (with milliseconds)
        """
        return self.__start_time

    def __stop(self):
        """
        Stop command line execution
        """
        self.running = False

    def stop(self):
        """
        Kill alias
        """
        self.kill()

    def kill(self):
        """
        Stop command line execution
        """
        self.logger.debug(u'Process killed manually')
        self.killed = True
        self.__stop()

    def __send_stds(self):
        """
        Read queues and send outputs if available

        Returns:
            True if something sent, False otherwise
        """
        if not self.callback:
            return False

        stdout = None
        stderr = None

        try:
            stdout = self.__stdout_queue.get_nowait()
        except Empty:
            pass
        except: # pragma: no cover
            self.logger.exception(u'Error getting stdout queue')

        try:
            stderr = self.__stderr_queue.get_nowait()
        except Empty:
            pass
        except: # pragma: no cover
            self.logger.exception(u'Error getting stderr queue')

        if stdout is not None or stderr is not None:
            try:
                self.callback(stdout, stderr)
            except:
                self.logger.exception(u'Exception occured during EndlessCommand callback:')
            return True

        return False

    def run(self):
        """
        Console process
        """
        # launch command
        return_code = None
        self.__start_time = time.time()
        p = subprocess.Popen(self.command, shell=True, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=ON_POSIX, preexec_fn=os.setsid)
        pid = p.pid
        self.logger.trace(u'PID=%d' % pid)

        if self.callback:
            # async stdout reading
            self.__stdout_thread = Thread(target=self.__enqueue_output, args=(p.stdout, self.__stdout_queue), daemon=True)
            self.__stdout_thread.start()

            # async stderr reading
            self.__stderr_thread = Thread(target=self.__enqueue_output, args=(p.stderr, self.__stderr_queue), daemon=True)
            self.__stderr_thread.start()

        # wait for end of command line
        while self.running:
            # check process status
            p.poll()

            # read outputs and trigger callback
            self.__send_stds()

            # check end of command
            if p.returncode is not None:
                return_code = p.returncode
                self.logger.debug(u'Process is terminated with return code %s' % p.returncode)
                break
            
            # pause
            time.sleep(0.25)

        # purge queues
        self.logger.trace('Purging outputs...')
        count = 0
        while self.__send_stds() or count<=5:
            self.logger.trace(' purging...')
            count += 1
            time.sleep(0.05)
        self.logger.trace('Purge completed')

        # make sure all stds are closed
        try:
            p.stdout.close()
        except:
            pass
        try:
            p.stderr.close()
        except:
            pass

        # make sure process (and child processes) is really killed
        if self.killed and pid!=1:
            try:
                if ON_POSIX:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                else: # pragma: no cover
                    p.kill()
            except: # pragma: no cover
                pass

        # process is over
        self.running = False

        # stop callback
        if self.callback_end:
            self.logger.trace('Call end callback')
            try:
                self.callback_end(return_code, self.killed)
            except:
                self.logger.exception(u'Exception occured during EndlessCommand end callback:')


class Console():
    """
    Helper class to execute command lines.
    You can execute command right now using command method or after a certain amount of time using command_delayed
    """
    def __init__(self):
        """
        Constructor
        """
        # members
        self.timer = None
        self.__callback = None
        self.encoding = sys.getfilesystemencoding()
        self.last_return_code = None
        self.logger = logging.getLogger(self.__class__.__name__)
        # self.logger.setLevel(logging.DEBUG)

    def __del__(self):
        """
        Destroy console object
        """
        if self.timer: # pragma: no cover
            self.timer.cancel()

    def __process_lines(self, lines):
        """
        Remove end of line char for given lines and convert lines to unicode
        
        Args:
            lines (list): list of lines
        
        Results:
            list: input list of lines with eol removed
        """
        return [line.decode('utf-8').rstrip() for line in lines]

    def get_last_return_code(self):
        """
        DEPRECATED: use returncode from command result
        Return last executed command return code

        Returns:
            int: return code (can be None)
        """
        return self.last_return_code

    def command(self, command, timeout=2.0):
        """
        Execute specified command line with auto kill after timeout
        
        Args:
            command (string): command to execute
            timeout (float): wait timeout before killing process and return command result

        Returns:
            dict: result of command::

                {
                    returncode (int): command return code
                    error (bool): True if error occured,
                    killed (bool): True if command was killed,
                    stdout (list): command line output
                    stderr (list): command line error
                }

        """
        self.logger.trace('Launch command "%s"' % command)
        # check params
        if timeout is None or timeout<=0.0:
            raise Exception(u'Timeout is mandatory and must be greater than 0')

        # launch command
        p = subprocess.Popen(command, shell=True, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=ON_POSIX, preexec_fn=os.setsid)
        pid = p.pid

        # wait for end of command line
        done = False
        start = time.time()
        killed = False
        return_code = None
        while not done:
            # check if command has finished
            p.poll()
            if p.returncode is not None:
                # command terminated
                self.logger.trace('Command terminated with returncode %s' % p.returncode)
                return_code = p.returncode
                self.last_return_code = return_code
                done = True
                break
            
            # check timeout
            if time.time()>(start + timeout):
                # timeout is over, kill command
                pgid = os.getpgid(pid)
                self.logger.debug('Timeout over, kill command for PID=%s PGID=%s' % (pid, pgid))
                try:
                    if ON_POSIX:
                        os.killpg(pgid, signal.SIGKILL)
                    else: # pragma: no cover
                        p.kill()
                except: # pragma: no cover
                    pass
                killed = True
                break

            # pause
            time.sleep(0.125)
       
        # prepare result
        result = {
            u'returncode': return_code,
            u'error': False,
            u'killed': killed,
            u'stdout': [],
            u'stderr': []
        }
        if not killed:
            result[u'stderr'] = self.__process_lines(p.stderr.readlines())
            result[u'error'] = True if len(result['stderr'])>0 else False
            result[u'stdout'] = self.__process_lines(p.stdout.readlines())
        self.logger.trace('Result: %s' % result)

        # make sure all stds are closed
        try:
            p.stdout.close()
        except:
            pass
        try:
            p.stderr.close()
        except:
            pass

        # trigger callback (used for delayed command)
        if self.__callback:
            self.__callback(result)

        return result

    def command_delayed(self, command, delay, timeout=2.0, callback=None):
        """
        Execute specified command line after specified delay

        Args:
            command (string): command to execute
            delay (int): time to wait before executing command (milliseconds)
            timeout (float): timeout before killing command
            callback (function): function called when command is over. Callback will received command result as single function parameter

        Notes:
            See command function to have more details
        """
        self.__callback = callback
        self.timer = Timer(delay, self.command, [command, timeout])
        self.timer.start()


class AdvancedConsole(Console):
    """
    Create console with advanced feature like find function to match pattern on stdout
    """
    def __init__(self):
        """
        Constructor
        """
        Console.__init__(self)

    def find(self, command, pattern, options=re.UNICODE | re.MULTILINE, timeout=2.0):
        """
        Find all pattern matches in command stdout. Found order is preserved

        Args:
            command (string): command to execute
            pattern (string): search pattern
            options (flag): regexp flags (see https://docs.python.org/2/library/re.html#module-contents)
            timeout (float): timeout before killing command

        Returns:
            list: list of matches::

                [
                    (group (string), matches in group (tuple)),
                    ...
                ]

        """
        results = []

        # execute command
        res = self.command(command, timeout)
        if self.get_last_return_code()!=0:
            # command failed
            return []

        # parse command output
        content = u'\n'.join(res[u'stdout'])
        return self.find_in_string(content, pattern, options)

    def find_in_string(self, string, pattern, options=re.UNICODE | re.MULTILINE):
        """
        Find all pattern matches in specified string. Found order is respected.

        Args:
            string (string): string to search in
            pattern (string): search pattern
            options (flag): regexp flags (see https://docs.python.org/2/library/re.html#module-contents)

        Returns:
            list: list of matches::

                [
                    (group (string), subgroups (tuple)),
                    ...
                ]

        """
        results = []
        matches = re.finditer(pattern, string, options)

        for _, match in enumerate(matches):
            group = match.group().strip()
            if len(group)>0 and len(match.groups())>0:
                results.append((group, match.groups()))

        return results

