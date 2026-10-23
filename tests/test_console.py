#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from cleepcli.console import Console, ON_POSIX

# Console uses logging.TRACE, installed by bin/cleep-cli at runtime
if not hasattr(logging, "TRACE"):
    level = logging.TRACE = logging.DEBUG - 5

    def log_logger(self, message, *args, **kwargs):
        if self.isEnabledFor(level):
            self._log(level, message, args, **kwargs)

    logging.getLoggerClass().trace = log_logger
    logging.addLevelName(level, "TRACE")


def test_on_posix_is_defined():
    assert isinstance(ON_POSIX, bool)


def test_command_returns_success():
    result = Console().command("true", timeout=2.0)
    assert result["returncode"] == 0
    assert result["killed"] is False
    assert result["error"] is False


def test_command_returns_failure():
    result = Console().command("false", timeout=2.0)
    assert result["returncode"] != 0
    assert result["killed"] is False
    assert result["error"] is True


def test_command_stderr_without_failure_is_not_error():
    result = Console().command("echo warn 1>&2; true", timeout=2.0)
    assert result["returncode"] == 0
    assert result["error"] is False
    assert any("warn" in line for line in result["stderr"])


def test_command_timeout_sets_killed():
    result = Console().command("sleep 5", timeout=0.3)
    assert result["killed"] is True
    assert result["error"] is True
    assert result["returncode"] != 0
