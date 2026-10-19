#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import unittest

from cleepcli.console import Console, ON_POSIX

# Console uses logging.TRACE, installed by bin/cleep-cli at runtime
if not hasattr(logging, "TRACE"):
    level = logging.TRACE = logging.DEBUG - 5

    def log_logger(self, message, *args, **kwargs):
        if self.isEnabledFor(level):
            self._log(level, message, args, **kwargs)

    logging.getLoggerClass().trace = log_logger
    logging.addLevelName(level, "TRACE")


class ConsoleCommandTests(unittest.TestCase):
    def test_on_posix_is_defined(self):
        self.assertIsInstance(ON_POSIX, bool)

    def test_command_returns_success(self):
        result = Console().command("true", timeout=2.0)
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(result["killed"])
        self.assertFalse(result["error"])

    def test_command_returns_failure(self):
        result = Console().command("false", timeout=2.0)
        self.assertNotEqual(result["returncode"], 0)
        self.assertFalse(result["killed"])
        self.assertTrue(result["error"])

    def test_command_stderr_without_failure_is_not_error(self):
        result = Console().command("echo warn 1>&2; true", timeout=2.0)
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(result["error"])
        self.assertTrue(any("warn" in line for line in result["stderr"]))

    def test_command_timeout_sets_killed(self):
        result = Console().command("sleep 5", timeout=0.3)
        self.assertTrue(result["killed"])
        self.assertTrue(result["error"])
        self.assertNotEqual(result["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
