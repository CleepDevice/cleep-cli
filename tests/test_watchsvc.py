#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from unittest.mock import Mock, patch

from cleepcli.watchsvc import WatchService, WATCH_UNIT_DST, bundled_unit_path


def test_bundled_unit_path_exists():
    assert os.path.isfile(bundled_unit_path())


def test_install_copies_unit_and_reloads():
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    svc.is_active = Mock(return_value=False)

    with patch("cleepcli.watchsvc.shutil.copyfile") as copyfile, patch(
        "cleepcli.watchsvc.os.makedirs"
    ), patch("cleepcli.watchsvc.os.path.isfile", return_value=True), patch.object(
        svc, "_unit_content_changed", return_value=False
    ):
        assert svc.install() is True
        copyfile.assert_called_once()
        assert copyfile.call_args.args[1] == WATCH_UNIT_DST
        svc.console.command.assert_called_with(
            "/bin/systemctl daemon-reload", 60.0
        )


def test_install_does_not_restart_when_active_and_unit_unchanged():
    """developer ensure calls install on every Cleep start — must not bounce watch."""
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    svc.is_active = Mock(return_value=True)
    svc.restart = Mock(return_value=True)

    with patch("cleepcli.watchsvc.shutil.copyfile"), patch(
        "cleepcli.watchsvc.os.makedirs"
    ), patch("cleepcli.watchsvc.os.path.isfile", return_value=True), patch.object(
        svc, "_unit_content_changed", return_value=False
    ), patch.object(svc, "_cli_binary_newer_than_running", return_value=False):
        assert svc.install() is True
    svc.restart.assert_not_called()


def test_install_restarts_when_active_and_unit_changed():
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    svc.is_active = Mock(return_value=True)
    svc.restart = Mock(return_value=True)

    with patch("cleepcli.watchsvc.shutil.copyfile"), patch(
        "cleepcli.watchsvc.os.makedirs"
    ), patch("cleepcli.watchsvc.os.path.isfile", return_value=True), patch.object(
        svc, "_unit_content_changed", return_value=True
    ), patch.object(svc, "_cli_binary_newer_than_running", return_value=False):
        assert svc.install() is True
    svc.restart.assert_called_once_with()


def test_install_restarts_when_flag_and_active():
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    svc.is_active = Mock(return_value=True)
    svc.restart = Mock(return_value=True)

    with patch("cleepcli.watchsvc.shutil.copyfile"), patch(
        "cleepcli.watchsvc.os.makedirs"
    ), patch("cleepcli.watchsvc.os.path.isfile", return_value=True), patch.object(
        svc, "_unit_content_changed", return_value=False
    ), patch.object(svc, "_cli_binary_newer_than_running", return_value=False):
        assert svc.install(restart_if_active=True) is True
    svc.restart.assert_called_once_with()


def test_install_restarts_when_cli_binary_newer_than_running():
    """pip upgrade leaves a newer on-disk binary; install must bounce watch once."""
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    svc.is_active = Mock(return_value=True)
    svc.restart = Mock(return_value=True)

    with patch("cleepcli.watchsvc.shutil.copyfile"), patch(
        "cleepcli.watchsvc.os.makedirs"
    ), patch("cleepcli.watchsvc.os.path.isfile", return_value=True), patch.object(
        svc, "_unit_content_changed", return_value=False
    ), patch.object(svc, "_cli_binary_newer_than_running", return_value=True):
        assert svc.install() is True
    svc.restart.assert_called_once_with()


def test_cli_binary_newer_than_running_compares_mtime_to_service_start():
    svc = WatchService()
    svc.console = Mock()
    # service started at t=100s (100_000_000 us)
    svc.console.command.return_value = {
        "returncode": 0,
        "stdout": ["100000000"],
        "stderr": "",
    }

    with patch.object(WatchService, "_cli_executable_path", return_value="/usr/local/bin/cleep-cli"), patch(
        "cleepcli.watchsvc.os.path.isfile", return_value=True
    ), patch("cleepcli.watchsvc.os.path.getmtime", return_value=150.0):
        assert svc._cli_binary_newer_than_running() is True

    with patch.object(WatchService, "_cli_executable_path", return_value="/usr/local/bin/cleep-cli"), patch(
        "cleepcli.watchsvc.os.path.isfile", return_value=True
    ), patch("cleepcli.watchsvc.os.path.getmtime", return_value=50.0):
        assert svc._cli_binary_newer_than_running() is False


def test_enable_installs_when_missing():
    svc = WatchService()
    svc.install = Mock(return_value=True)
    svc.is_active = Mock(return_value=True)
    svc.console = Mock()
    svc.console.command.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

    with patch("cleepcli.watchsvc.os.path.isfile", return_value=False):
        assert svc.enable() is True
    svc.install.assert_called_once_with()


def test_status_not_installed():
    svc = WatchService()
    with patch("cleepcli.watchsvc.os.path.isfile", return_value=False):
        assert svc.status() == "not-installed"


def test_status_active():
    svc = WatchService()
    svc.console = Mock()
    svc.console.command.return_value = {
        "returncode": 0,
        "stdout": ["active"],
        "stderr": "",
    }
    with patch("cleepcli.watchsvc.os.path.isfile", return_value=True):
        assert svc.status() == "active"
