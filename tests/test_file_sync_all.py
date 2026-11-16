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


def _import_watch_with_fake_watchdog():
    """Import cleepcli.watch even when the watchdog package is unavailable."""
    import sys
    import types

    if "watchdog" not in sys.modules:
        watchdog_mod = types.ModuleType("watchdog")
        observers = types.ModuleType("watchdog.observers")
        events = types.ModuleType("watchdog.events")

        class _Observer:
            pass

        class _FileSystemEventHandler:
            pass

        observers.Observer = _Observer
        events.FileSystemEventHandler = _FileSystemEventHandler
        events.EVENT_TYPE_CREATED = "created"
        events.EVENT_TYPE_DELETED = "deleted"
        events.EVENT_TYPE_MODIFIED = "modified"
        events.EVENT_TYPE_MOVED = "moved"
        events.DirModifiedEvent = type("DirModifiedEvent", (), {})
        sys.modules["watchdog"] = watchdog_mod
        sys.modules["watchdog.observers"] = observers
        sys.modules["watchdog.events"] = events

    from cleepcli.watch import CleepWatchdog

    return CleepWatchdog


def test_watch_catch_up_calls_sync_all():
    CleepWatchdog = _import_watch_with_fake_watchdog()

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ) as executor_cls, patch(
        "cleepcli.watch.time.sleep", side_effect=KeyboardInterrupt
    ), patch(
        "cleepcli.watch.consume_skip_catchup_once", return_value=False
    ):
        file_cls.return_value.sync_all.return_value = True
        handler = handler_cls.return_value
        handler._watched = {"/tmp"}
        handler.schedule_all = Mock()
        executor = executor_cls.return_value
        executor.cleep.ensure_frontend_nocache = Mock(return_value=True)
        executor.cleep.restart_backend = Mock(return_value=True)

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=True)
        assert watchdog.watch() is True
        file_cls.return_value.sync_all.assert_called_once_with()
        executor.cleep.ensure_frontend_nocache.assert_called_once_with()
        executor.cleep.restart_backend.assert_called_once_with()
        executor.cleep.restart_frontend.assert_not_called()


def test_watch_catch_up_fails_when_backend_restart_fails():
    CleepWatchdog = _import_watch_with_fake_watchdog()

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ) as executor_cls, patch(
        "cleepcli.watch.consume_skip_catchup_once", return_value=False
    ):
        file_cls.return_value.sync_all.return_value = True
        handler_cls.return_value._watched = {"/tmp"}
        executor = executor_cls.return_value
        executor.cleep.ensure_frontend_nocache = Mock(return_value=True)
        executor.cleep.restart_backend = Mock(return_value=False)

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=True)
        assert watchdog.watch() is False
        executor.start.assert_not_called()


def test_watch_skip_catch_up():
    CleepWatchdog = _import_watch_with_fake_watchdog()

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ) as executor_cls, patch(
        "cleepcli.watch.time.sleep", side_effect=KeyboardInterrupt
    ), patch(
        "cleepcli.watch.consume_skip_catchup_once", return_value=False
    ):
        handler = handler_cls.return_value
        handler._watched = {"/tmp"}
        handler.schedule_all = Mock()
        executor = executor_cls.return_value
        executor.cleep.ensure_frontend_nocache = Mock()
        executor.cleep.restart_backend = Mock()
        executor.cleep.restart_frontend = Mock()

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=False)
        assert watchdog.watch() is True
        file_cls.return_value.sync_all.assert_not_called()
        executor.cleep.ensure_frontend_nocache.assert_not_called()
        executor.cleep.restart_backend.assert_not_called()
        executor.cleep.restart_frontend.assert_not_called()


def test_watch_consumes_skip_catchup_once_flag():
    CleepWatchdog = _import_watch_with_fake_watchdog()

    with patch("cleepcli.watch.File") as file_cls, patch(
        "cleepcli.watch.os.path.exists", return_value=True
    ), patch("cleepcli.watch.Observer"), patch(
        "cleepcli.watch.CleepHandler"
    ) as handler_cls, patch(
        "cleepcli.watch.ActionsExecutor"
    ) as executor_cls, patch(
        "cleepcli.watch.time.sleep", side_effect=KeyboardInterrupt
    ), patch(
        "cleepcli.watch.consume_skip_catchup_once", return_value=True
    ):
        handler = handler_cls.return_value
        handler._watched = {"/tmp"}
        handler.schedule_all = Mock()
        executor = executor_cls.return_value
        executor.cleep.ensure_frontend_nocache = Mock()
        executor.cleep.restart_backend = Mock()

        watchdog = CleepWatchdog("https://127.0.0.1:443", catch_up=True)
        assert watchdog.watch() is True
        file_cls.return_value.sync_all.assert_not_called()
        executor.cleep.restart_backend.assert_not_called()
