#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
from .console import EndlessConsole, Console, AdvancedConsole
import logging
from . import config
import importlib
import re
import datetime
import shutil

PRAGMA_NO_COVER_PATTERN = r'#\s*pragma\s*:\s*no\s+cover'


def coverage_report_to_dict(stdout):
    """
    Convert coverage report text to a dict with per-file stats and score.

    Args:
        stdout (string): coverage results

    Returns:
        dict: {'files': [...], 'score': float}
    """
    out = {
        'files': [],
        'score': 0.0,
    }

    c = AdvancedConsole()
    results = c.find_in_string(
        stdout,
        r'((?:/.*?)+\.py)\s+(\d+)\s+\d+\s+(\d+)%|^(TOTAL)\s+\d+\s+\d+\s+(\d+)%$',
    )
    for result in results:
        groups = list(filter(None, result[1]))
        if groups[0].startswith('TOTAL'):
            out['score'] = int(groups[1]) / 10
        else:
            out['files'].append({
                'file': groups[0],
                'statements': int(groups[1]),
                'coverage': int(groups[2]),
            })

    return out


def is_file_coverage_valid(coverage_info):
    """
    Check if a covered file respects Cleep test practices.

    Args:
        coverage_info (dict): one entry from coverage_report_to_dict()['files']

    Returns:
        bool: False if the file is fully uncovered or abuses ``pragma: no cover``
    """
    if coverage_info['file'].find('__init__.py') != -1:
        return True

    if coverage_info['statements'] == 0 and coverage_info['coverage'] == 100:
        logging.error('File "%s" fully uncovered by tests' % coverage_info['file'])
        return False

    with open(coverage_info['file']) as fdesc:
        lines = fdesc.readlines()
    lines_count = len(lines)
    max_pragma = max(int(lines_count / 150), 1)
    count_pragma = len(re.findall(PRAGMA_NO_COVER_PATTERN, '\n'.join(lines)))
    if count_pragma > max_pragma:
        logging.error(
            'Number of allowed "no cover" exceed max allowed (1 per 150 source lines) in "%s"'
            % coverage_info['file']
        )
        return False

    return True


class Test():
    """
    Handle test processes
    """
    COVERAGE_PATH = '/opt/cleep/.coverage'

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.__endless_command_running = False
        self.__endless_command_return_code = 0
        self.__module_version = None
        self.__stderr = []
        if not os.path.exists(self.COVERAGE_PATH):
            try:
                os.makedirs(self.COVERAGE_PATH)
            except OSError:
                pass

    def __coverage_to_dict(self, stdout):
        """
        Convert coverage results to dict

        Args:
            stdout (string): coverage results
        """
        return coverage_report_to_dict(stdout)

    def __reset_stds(self):
        self.__stderr.clear()

    def __quiet_console_callback(self, stdout, stderr):
        if stderr:
            self.__stderr.append(stderr)

    def __console_callback(self, stdout, stderr):
        if stdout and stdout.find('----------------------------------------------------------------------') < 0:
            self.logger.info("  |  " + stdout)
        if stderr and stderr.find('----------------------------------------------------------------------') < 0:
            self.logger.info("  | " + stderr)
        if stderr:
            self.__stderr.append(stderr)

    def __console_end_callback(self, return_code, killed):
        self.__endless_command_running = False
        self.__endless_command_return_code = return_code

    def __get_module_version(self, module_name):
        if self.__module_version:
            return self.__module_version

        try:
            module_ = importlib.import_module('cleep.modules.%s' % (module_name))
            app_filename = getattr(module_, 'APP_FILENAME', module_name)
            del module_
            module_ = importlib.import_module('cleep.modules.%s.%s' % (module_name, app_filename))
            class_name = next((item for item in dir(module_) if item.lower() == app_filename.lower()), None)
            module_class_ = getattr(module_, class_name or '', None)
            self.__module_version = module_class_.MODULE_VERSION
            return self.__module_version
        except:
            self.logger.exception('Unable to get module version. Is module valid?')
            return None

    def __get_coverage_errors_and_failures(self, test_filepath):
        """
        Parse coverage output to find errors and failures count

        Args:
            test_filepath (string): test_filepath

        Returns:
            tuple: errors and failures count::

                (errors, failures)

        """
        exception = ''
        errors = 0
        failures = 0
        notest = False

        # coverage output is stored in stderr
        pattern = r'^FAILED \(((?:failures=(?P<failures>\d+))?|(?:, )?|(?:errors=(?P<errors>\d+))?)*\)$'
        matches = re.finditer(pattern, '\n'.join(self.__stderr), re.MULTILINE)
        for matchNum, match in enumerate(matches, start=1):
            indexes = match.groupdict()
            errors = indexes['errors'] if indexes['errors'] else 0
            failures = indexes['failures'] if indexes['failures'] else 0

        if not os.path.exists(test_filepath):
            notest = 'no test, '
            exception = ''
        else:
            notest = ''
            exception = 'run error, ' if errors == 0 and failures == 0 else ''

        return (errors, failures, exception, notest)

    def __get_coverage_file(self, module_name, module_version):
        """
        Return coverage file

        Args:
            module_name (string): module name
            module_version (string): module version

        Returns:
            string: coverage file
        """
        cov_file = os.path.join(self.COVERAGE_PATH, '%s.%s.cov' % (module_name, module_version))
        self.logger.debug('Coverage file = %s' % cov_file)
        return cov_file

    def __get_module_tests_path(self, module_name):
        """
        Return module tests path

        Args:
            module_name (string): module name

        Returns:
            string: module tests path
        """
        return '%s/%s/tests' % (config.MODULES_SRC, module_name)

    def __get_module_root_path(self, module_name):
        """
        Return module application root path (parent of backend/ and tests/).

        Args:
            module_name (string): module name

        Returns:
            string: module root path
        """
        return os.path.join(config.MODULES_SRC, module_name)

    def __coverage_simple_command(self, path, coverage_command, coverage_options='', coverage_file=None, timeout=5.0, quiet=True):
        coverage_file = 'COVERAGE_FILE=%s ' % coverage_file if coverage_file else ''
        
        cmd = """
cd "%(path)s"
%(coverage_file)scoverage %(command)s %(options)s
        """ % {
            'coverage_file': coverage_file,
            'path': path,
            'command': coverage_command,
            'options': coverage_options,
        }
        self.logger.debug('Coverage cmd: %s', cmd)
        c = Console()
        res = c.command(cmd, timeout=timeout)
        if res['returncode'] != 0 or res['killed']:
            if len(res["stdout"]) == 0 or not res["stdout"][0].startswith("No data to"):
                self.logger.error('Error during command execution [%s] (killed: %s): %s - %s', res["returncode"], res["killed"], res["stdout"], res["stderr"])
            return False

        if not quiet and res.get('stderr'):
            self.logger.warning('Warning on stderr: %s', res.get('stderr'))

        return res

    def module_tests(self, module_name, display_coverage=False, copy_to=None, pattern=None):
        """
        Execute module unit tests and display process output on stdout

        Args:
            module_name (string): module name
            display_coverage (bool): display coverage report (default False)
            copy_to (str): copy coverage file to specified path
            pattern (str): run testcase that match pattern (no coverage)

        Returns:
            bool: True if process succeed, False otherwise
        """
        # checking module path
        path = os.path.join(config.MODULES_SRC, module_name, 'tests')
        if not os.path.exists(path):
            self.logger.error('Specified module "%s" does not exist' % (module_name))
            return False

        # create module coverage path
        module_version = self.__get_module_version(module_name)
        if module_version is None:
            return False

        self.logger.info('Running unit tests...')
        coverage_file_path = self.__get_coverage_file(module_name, module_version)
        module_root_path = self.__get_module_root_path(module_name)
        if pattern:
            cmd = self.__get_tests_cmd_with_pattern(module_root_path, pattern)
        else:
            cmd = self.__get_tests_cmd_with_coverage(module_root_path, coverage_file_path)
        self.logger.debug('Test cmd: %s' % cmd)
        self.__endless_command_running = True
        self.__reset_stds()
        c = EndlessConsole(cmd, self.__console_callback, self.__console_end_callback)
        c.start()

        while self.__endless_command_running:
            time.sleep(0.25)

        # display coverage report
        if display_coverage:
            self.logger.debug('Display coverage')
            self.logger.info(self.module_tests_coverage(module_name))

        # copy coverage file to standart location (in module tests directory) for coverage report tools
        if copy_to:
            if not os.path.isfile(coverage_file_path):
                self.logger.error('Coverage file missing: %s' % coverage_file_path)
                return False
            shutil.copyfile(coverage_file_path, os.path.join(copy_to, '.coverage'))

        self.logger.debug('Return code: %s' % self.__endless_command_return_code)
        if self.__endless_command_return_code!=0:
            return False

        return True

    def __get_tests_cmd_with_coverage(self, module_root_path, coverage_file_path):
        """
        Return cmdline to run full tests on module with coverage (pytest hybrid).

        App root is on PYTHONPATH so tests import ``backend.*`` without sys.path hacks.
        """
        return """
cd "%s"
PYTHONPATH=. COVERAGE_FILE=%s coverage run --omit="*/lib/python*/*","*/tests/*","test_*" --source=backend --concurrency=thread -m pytest tests
        """ % (module_root_path, coverage_file_path)

    def __get_tests_cmd_with_pattern(self, module_root_path, pattern):
        """
        Return cmdline to run tests matching specified pattern (no coverage).
        """
        return """
cd "%s"
PYTHONPATH=. python3 -m pytest tests -k "%s"
        """ % (module_root_path, pattern)

    def module_tests_coverage(self, module_name, missing=False, as_json=False, quiet=True):
        """
        Display module coverage

        Args:
            module_name (string): module name
            missing (bool): display missing statements (default False)
            as_json (bool): return results as json
            quiet (bool): display or not coverage.py warnings

        Returns:
            string or dict according to as_json option
        """
        # checking module path
        path = os.path.join(config.MODULES_SRC, module_name, 'tests')
        if not os.path.exists(path):
            raise Exception('Specified module "%s" does not exist' % (module_name))

        module_version = self.__get_module_version(module_name)
        if module_version is None:
            raise Exception('Module version not found')

        coverage_file = self.__get_coverage_file(module_name, module_version)
        if not os.path.exists(coverage_file):
            raise Exception('No coverage file found. Did tests run ?')

        report = self.__coverage_simple_command(
            self.__get_module_root_path(module_name),
            'report',
            '-m -i' if missing else '-i',
            coverage_file,
            quiet=quiet,
        )
        if not report:
            raise Exception('Error executing coverage report')

        stdout = '\n'.join(report['stdout'])
        if not as_json:
            return stdout
        return self.__coverage_to_dict(stdout)

    def __get_core_tests_path(self):
        """
        Return core tests path

        Returns:
            string: core tests path
        """
        return '%s/tests' % (config.CORE_SRC)

    def __get_core_repo_path(self):
        """
        Return core repository root (parent of the ``cleep`` package).

        Used as PYTHONPATH so tests can ``import cleep...`` without sys.path hacks.
        """
        return config.REPO_DIR

    def core_tests(self, display_coverage=False, display_test_output=False, xml=False, quiet=True, pattern=None):
        """
        Execute core unit tests and display process output on stdout

        Args:
            display_coverage (bool): display coverage report (default False)
            display_test_output (bool): display unit test output (default True)
            xml (bool): use xml coverage command instead of report command
            quiet (bool): display or not coverage.py warnings
            pattern (str): custom pattern to filter tests (pytest -k)

        Returns:
            bool: True if process succeed.
        """
        start = int(time.time())
        repo_dir = self.__get_core_repo_path()

        # clear previous results (run from repo root where .coverage is written)
        if self.__coverage_simple_command(repo_dir, 'erase') == False:
            self.logger.error('Unable to clear previous tests results')
            return False

        self.logger.info('Running core unit tests (pytest)...')
        pattern_opt = '-k "%s"' % pattern if pattern else ''
        verbosity = '-v' if display_test_output else '-q'
        cmd = """
cd "%(repo_dir)s"
PYTHONPATH=. coverage run --omit="*/lib/python*/*","*/tests/*","*test_*.py" --source=cleep --concurrency=gevent -m pytest %(verbosity)s cleep/tests %(pattern_opt)s
        """ % {
            'repo_dir': repo_dir,
            'verbosity': verbosity,
            'pattern_opt': pattern_opt,
        }
        self.logger.debug('Test cmd: %s' % cmd)
        self.__endless_command_running = True
        self.__reset_stds()
        console_callback = self.__console_callback if display_test_output else self.__quiet_console_callback
        c = EndlessConsole(cmd, console_callback, self.__console_end_callback)
        c.start()

        try:
            while self.__endless_command_running:
                time.sleep(0.25)
        except KeyboardInterrupt:
            self.logger.warning('Interrupted — stopping tests...')
            c.kill()
            while self.__endless_command_running:
                time.sleep(0.1)
            raise

        success = self.__endless_command_return_code == 0

        # coverage
        if display_coverage:
            coverage = self.core_tests_coverage(xml=xml, quiet=quiet)
            logging.info(coverage)

        duration = str(datetime.timedelta(seconds=(int(time.time()) - start)))
        self.logger.info('-' * 50)
        self.logger.info('Tests report:')
        self.logger.info('  Duration: %s' % duration)
        self.logger.info('  Result: %s' % ('OK' if success else 'FAILED'))
        self.logger.info('-' * 50)

        return success

    def core_tests_coverage(self, as_json=False, xml=False, quiet=True):
        """
        Get core test coverage last results

        Args:
            as_json (bool): return output as json
            xml (bool): use xml coverage command instead of report command
            quiet (bool): display or not coverage.py warnings

        Returns:
            string or dict according to as_json option
        """
        repo_dir = self.__get_core_repo_path()

        # report results (single pytest+coverage run; no combine needed)
        command = "xml" if xml else "report"
        res = self.__coverage_simple_command(repo_dir, command, "--ignore-errors", timeout=120.0, quiet=quiet)
        if res == False:
            raise Exception('Error generating coverage results')

        stdout = '\n'.join(res.get('stdout', []))
        if not as_json:
            return stdout
        return self.__coverage_to_dict(stdout)

