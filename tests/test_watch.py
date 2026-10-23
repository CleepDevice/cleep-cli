#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import time

import pytest
from unittest.mock import Mock, patch
from watchdog.events import (
    DirCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)
from watchdog.observers import Observer

from cleepcli import config
from cleepcli.watch import ActionsExecutor, CleepHandler, iter_watch_roots


def test_skips_module_git_and_watches_content_dirs():
    repo = tempfile.mkdtemp()
    try:
        core = os.path.join(repo, "cleep")
        html = os.path.join(repo, "html")
        bin_dir = os.path.join(repo, "bin")
        modules = os.path.join(repo, "modules")
        os.makedirs(os.path.join(core, "libs"))
        os.makedirs(html)
        os.makedirs(bin_dir)
        os.makedirs(os.path.join(modules, "audio", ".git", "objects", "ab"))
        os.makedirs(os.path.join(modules, "audio", "backend"))
        os.makedirs(os.path.join(modules, "audio", "frontend"))
        os.makedirs(os.path.join(modules, "audio", "tests"))

        with patch.object(config, "CORE_SRC", core), patch.object(
            config, "HTML_SRC", html
        ), patch.object(config, "BIN_SRC", bin_dir), patch.object(
            config, "MODULES_SRC", modules
        ):
            roots = list(iter_watch_roots())
    finally:
        shutil.rmtree(repo)

    paths = {path for path, _recursive in roots}
    recursive = {path: recursive for path, recursive in roots}
    assert core in paths
    assert recursive[core] is True
    assert html in paths
    assert bin_dir in paths
    assert modules in paths
    assert recursive[modules] is False
    assert os.path.join(modules, "audio") in paths
    assert recursive[os.path.join(modules, "audio")] is False
    assert os.path.join(modules, "audio", "backend") in paths
    assert os.path.join(modules, "audio", "frontend") in paths
    assert recursive[os.path.join(modules, "audio", "backend")] is True
    assert not any(".git" in path.split(os.sep) for path in paths)
    assert not any(path.endswith(os.path.join("audio", "tests")) for path in paths)
    # 3 core trees + modules root + module root + 2 content dirs
    assert len(roots) == 7


@pytest.fixture
def handler():
    executor = Mock()
    return CleepHandler(executor), executor


def test_git_file_is_ignored(handler):
    h, executor = handler
    path = os.path.join(
        config.MODULES_SRC, "cleepbus.tangb", ".git", "objects", "ab", "deadbeef"
    )
    h.on_any_event(FileModifiedEvent(path))
    executor.note_change.assert_not_called()


def test_tests_file_is_ignored(handler):
    h, executor = handler
    path = os.path.join(config.CORE_SRC, "libs", "tests", "test_rpcserver.py")
    h.on_any_event(FileModifiedEvent(path))
    executor.note_change.assert_not_called()


def test_core_file_is_queued(handler):
    h, executor = handler
    path = os.path.join(config.CORE_SRC, "rpcserver.py")
    h.on_any_event(FileModifiedEvent(path))
    executor.note_change.assert_called_once_with(
        core=True, frontend=False, backend=True
    )


def test_atomic_save_move_is_queued(handler):
    h, executor = handler
    src = os.path.join(config.CORE_SRC, ".rpcserver.py.tmp")
    dest = os.path.join(config.CORE_SRC, "rpcserver.py")
    h.on_any_event(FileMovedEvent(src, dest))
    executor.note_change.assert_called_once_with(
        core=True, frontend=False, backend=True
    )


def test_module_file_delete_is_queued(handler):
    h, executor = handler
    path = os.path.join(config.MODULES_SRC, "audio", "backend", "audio.py")
    h.on_any_event(FileDeletedEvent(path))
    executor.note_change.assert_called_once_with(
        module="audio", frontend=False, backend=True
    )


def test_module_scripts_do_not_restart_backend(handler):
    h, executor = handler
    path = os.path.join(config.MODULES_SRC, "audio", "scripts", "postinst.sh")
    h.on_any_event(FileModifiedEvent(path))
    executor.note_change.assert_called_once_with(
        module="audio", frontend=False, backend=False
    )


def test_module_frontend_is_queued(handler):
    h, executor = handler
    path = os.path.join(config.MODULES_SRC, "audio", "frontend", "desc.json")
    h.on_any_event(FileModifiedEvent(path))
    executor.note_change.assert_called_once_with(
        module="audio", frontend=True, backend=False
    )


def test_created_git_directory_is_not_watched(handler):
    h, executor = handler
    h.observer = Mock()
    path = os.path.join(config.MODULES_SRC, "cleepbus.tangb", ".git")
    h.on_any_event(DirCreatedEvent(path))
    h.observer.schedule.assert_not_called()
    executor.note_change.assert_not_called()


def test_schedule_all_is_idempotent(handler):
    h, _executor = handler
    repo = tempfile.mkdtemp()
    try:
        core = os.path.join(repo, "cleep")
        html = os.path.join(repo, "html")
        bin_dir = os.path.join(repo, "bin")
        modules = os.path.join(repo, "modules")
        os.makedirs(core)
        os.makedirs(html)
        os.makedirs(bin_dir)
        os.makedirs(os.path.join(modules, "audio", "backend"))
        h.observer = Mock()
        with patch.object(config, "CORE_SRC", core), patch.object(
            config, "HTML_SRC", html
        ), patch.object(config, "BIN_SRC", bin_dir), patch.object(
            config, "MODULES_SRC", modules
        ):
            h.schedule_all()
            first = h.observer.schedule.call_count
            h.schedule_all()
            assert h.observer.schedule.call_count == first
            assert first < 20
    finally:
        shutil.rmtree(repo)


def test_created_module_backend_is_scheduled(handler):
    h, executor = handler
    h.observer = Mock()
    path = os.path.join(config.MODULES_SRC, "audio", "backend")
    with patch("os.path.isdir", return_value=True):
        h.on_any_event(DirCreatedEvent(path))
    h.observer.schedule.assert_called_once()
    args, kwargs = h.observer.schedule.call_args
    assert os.path.abspath(args[1]) == os.path.abspath(path)
    assert kwargs.get("recursive", args[2] if len(args) > 2 else False) is True
    executor.note_change.assert_called_once_with(
        module="audio", frontend=False, backend=True
    )


def test_created_core_directory_is_queued(handler):
    h, executor = handler
    h.observer = Mock()
    path = os.path.join(config.CORE_SRC, "libs", "newpkg")
    h.on_any_event(DirCreatedEvent(path))
    h.observer.schedule.assert_not_called()
    executor.note_change.assert_called_once_with(
        core=True, frontend=False, backend=True
    )


def _make_executor():
    executor = ActionsExecutor("https://127.0.0.1:443")
    executor.file = Mock()
    executor.file.core_sync.return_value = True
    executor.file.module_sync.return_value = True
    executor.cleep = Mock()
    executor.quiet_period = 0.2
    executor.poll_interval = 0.05
    return executor


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_burst_runs_one_sync_and_one_restart():
    executor = _make_executor()
    executor.start()
    try:
        for _ in range(5):
            executor.note_change(core=True, backend=True)
            time.sleep(0.02)
        assert _wait_until(lambda: executor.file.core_sync.call_count >= 1)
        time.sleep(0.4)
        assert executor.file.core_sync.call_count == 1
        executor.cleep.notify_sync_started.assert_called_once()
        executor.cleep.restart_backend.assert_called_once()
        executor.cleep.restart_frontend.assert_not_called()
        executor.cleep.notify_sync_done.assert_not_called()
    finally:
        executor.stop()
        executor.join(timeout=2)


def test_failed_sync_does_not_restart():
    executor = _make_executor()
    executor.file.core_sync.return_value = False
    executor.start()
    try:
        executor.note_change(core=True, backend=True)
        assert _wait_until(lambda: executor.file.core_sync.call_count >= 1)
        time.sleep(0.4)
        executor.cleep.restart_backend.assert_not_called()
        executor.cleep.restart_frontend.assert_not_called()
        executor.cleep.notify_sync_failed.assert_called_once()
    finally:
        executor.stop()
        executor.join(timeout=2)


def test_frontend_only_refreshes_the_ui():
    executor = _make_executor()
    executor.start()
    try:
        executor.note_change(module="audio", frontend=True)
        assert _wait_until(lambda: executor.file.module_sync.call_count >= 1)
        time.sleep(0.4)
        executor.cleep.notify_sync_started.assert_called_once()
        executor.cleep.restart_backend.assert_not_called()
        executor.cleep.restart_frontend.assert_called_once()
    finally:
        executor.stop()
        executor.join(timeout=2)


def test_scripts_only_does_not_restart():
    executor = _make_executor()
    executor.start()
    try:
        executor.note_change(module="audio")
        assert _wait_until(lambda: executor.file.module_sync.call_count >= 1)
        time.sleep(0.4)
        executor.cleep.restart_backend.assert_not_called()
        executor.cleep.restart_frontend.assert_not_called()
        executor.cleep.notify_sync_done.assert_called_once()
    finally:
        executor.stop()
        executor.join(timeout=2)


def test_core_and_modules_restart_once():
    executor = _make_executor()
    executor.start()
    try:
        executor.note_change(core=True, backend=True)
        executor.note_change(module="network", backend=True)
        executor.note_change(module="audio", frontend=True)
        assert _wait_until(lambda: executor.file.core_sync.call_count >= 1)
        time.sleep(0.4)
        assert executor.file.core_sync.call_count == 1
        assert executor.file.module_sync.call_count == 2
        executor.cleep.restart_backend.assert_called_once()
        executor.cleep.restart_frontend.assert_not_called()
    finally:
        executor.stop()
        executor.join(timeout=2)


def test_module_git_objects_are_not_watched():
    repo = tempfile.mkdtemp()
    observer = Observer()
    try:
        modules = os.path.join(repo, "modules")
        git_dir = os.path.join(modules, "audio", ".git", "objects", "ab")
        backend = os.path.join(modules, "audio", "backend")
        os.makedirs(git_dir)
        os.makedirs(backend)
        os.makedirs(os.path.join(repo, "cleep"))
        os.makedirs(os.path.join(repo, "html"))
        os.makedirs(os.path.join(repo, "bin"))

        executor = Mock()
        h = CleepHandler(executor)
        h.observer = observer
        seen = []

        def record(event):
            seen.append(getattr(event, "src_path", "") or "")

        h.on_any_event = record
        with patch.object(config, "CORE_SRC", os.path.join(repo, "cleep")), patch.object(
            config, "HTML_SRC", os.path.join(repo, "html")
        ), patch.object(config, "BIN_SRC", os.path.join(repo, "bin")), patch.object(
            config, "MODULES_SRC", modules
        ):
            h.schedule_all()
        observer.start()
        time.sleep(0.2)
        with open(os.path.join(git_dir, "deadbeef"), "w", encoding="utf-8") as handle:
            handle.write("x")
        with open(os.path.join(backend, "audio.py"), "w", encoding="utf-8") as handle:
            handle.write("x")
        time.sleep(0.5)
    finally:
        observer.stop()
        observer.join(timeout=2)
        shutil.rmtree(repo)

    assert any(path.endswith("audio.py") for path in seen)
    assert not any(".git" in path.split(os.sep) for path in seen)
