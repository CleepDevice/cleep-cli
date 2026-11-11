#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile

from unittest.mock import Mock, patch

from cleepcli import config
from cleepcli.file import File


def test_list_modules_sorted():
    repo = tempfile.mkdtemp()
    try:
        modules = os.path.join(repo, "modules")
        os.makedirs(os.path.join(modules, "zeta"))
        os.makedirs(os.path.join(modules, "alpha"))
        os.makedirs(os.path.join(modules, ".hidden"))
        open(os.path.join(modules, "file.txt"), "w", encoding="utf-8").close()

        with patch.object(config, "MODULES_SRC", modules):
            assert File().list_modules() == ["alpha", "zeta"]
    finally:
        shutil.rmtree(repo)


def test_sync_all_runs_core_then_modules():
    f = File()
    f.core_sync = Mock(return_value=True)
    f.module_sync = Mock(return_value=True)
    f.list_modules = Mock(return_value=["audio", "developer"])

    assert f.sync_all() is True
    f.core_sync.assert_called_once_with()
    assert f.module_sync.call_args_list[0].args[0] == "audio"
    assert f.module_sync.call_args_list[1].args[0] == "developer"


def test_sync_all_stops_on_core_failure():
    f = File()
    f.core_sync = Mock(return_value=False)
    f.module_sync = Mock(return_value=True)
    f.list_modules = Mock(return_value=["audio"])

    assert f.sync_all() is False
    f.module_sync.assert_not_called()


def test_watch_catch_up_calls_sync_all():
    from cleepcli.watch import CleepWatchdog

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ), patch(
        "cleepcli.watch.time.sleep", side_effect=KeyboardInterrupt
    ):
        file_cls.return_value.sync_all.return_value = True
        handler = handler_cls.return_value
        handler._watched = {"/tmp"}
        handler.schedule_all = Mock()

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=True)
        assert watchdog.watch() is True
        file_cls.return_value.sync_all.assert_called_once_with()


def test_watch_skip_catch_up():
    from cleepcli.watch import CleepWatchdog

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ), patch(
        "cleepcli.watch.time.sleep", side_effect=KeyboardInterrupt
    ):
        handler = handler_cls.return_value
        handler._watched = {"/tmp"}
        handler.schedule_all = Mock()

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=False)
        assert watchdog.watch() is True
        file_cls.return_value.sync_all.assert_not_called()
