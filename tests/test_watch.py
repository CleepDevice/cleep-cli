#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock

from watchdog.events import DirCreatedEvent, FileModifiedEvent, FileMovedEvent
from watchdog.observers import Observer

from cleepcli import config
from cleepcli.watch import ActionsExecutor, CleepHandler, iter_watch_directories


class IterWatchDirectoriesTests(unittest.TestCase):
    def test_skips_rejected_directories(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, ".git", "objects", "ab"))
            os.makedirs(os.path.join(root, "pkg", "__pycache__"))
            os.makedirs(os.path.join(root, "pkg", "tests"))
            os.makedirs(os.path.join(root, "pkg", "node_modules", "lib"))
            os.makedirs(os.path.join(root, "pkg", "backend"))
            watched = set(iter_watch_directories(root))
        finally:
            shutil.rmtree(root)

        self.assertIn(root, watched)
        self.assertIn(os.path.join(root, "pkg"), watched)
        self.assertIn(os.path.join(root, "pkg", "backend"), watched)
        self.assertFalse(any(".git" in path.split(os.sep) for path in watched))
        self.assertFalse(any("__pycache__" in path.split(os.sep) for path in watched))
        self.assertFalse(any("tests" in path.split(os.sep) for path in watched))
        self.assertFalse(any("node_modules" in path.split(os.sep) for path in watched))


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.executor = Mock()
        self.handler = CleepHandler(self.executor)

    def test_git_file_is_ignored(self):
        path = os.path.join(
            config.MODULES_SRC, "cleepbus.tangb", ".git", "objects", "ab", "deadbeef"
        )
        self.handler.on_any_event(FileModifiedEvent(path))
        self.executor.note_change.assert_not_called()

    def test_tests_file_is_ignored(self):
        path = os.path.join(config.CORE_SRC, "libs", "tests", "test_rpcserver.py")
        self.handler.on_any_event(FileModifiedEvent(path))
        self.executor.note_change.assert_not_called()

    def test_core_file_is_queued(self):
        path = os.path.join(config.CORE_SRC, "rpcserver.py")
        self.handler.on_any_event(FileModifiedEvent(path))
        self.executor.note_change.assert_called_once_with(core=True, frontend=False)

    def test_atomic_save_move_is_queued(self):
        src = os.path.join(config.CORE_SRC, ".rpcserver.py.tmp")
        dest = os.path.join(config.CORE_SRC, "rpcserver.py")
        self.handler.on_any_event(FileMovedEvent(src, dest))
        self.executor.note_change.assert_called_once_with(core=True, frontend=False)

    def test_created_git_directory_is_not_watched(self):
        self.handler.observer = Mock()
        path = os.path.join(config.MODULES_SRC, "cleepbus.tangb", ".git")
        self.handler.on_any_event(DirCreatedEvent(path))
        self.handler.observer.schedule.assert_not_called()
        self.executor.note_change.assert_not_called()

    def test_directory_is_scheduled_once(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "pkg"))
            self.handler.observer = Mock()
            self.handler.schedule_tree(root)
            self.handler.schedule_tree(root)
            self.assertEqual(self.handler.observer.schedule.call_count, 2)
        finally:
            shutil.rmtree(root)

    def test_created_core_directory_is_queued(self):
        self.handler.observer = Mock()
        path = os.path.join(config.CORE_SRC, "libs", "newpkg")
        self.handler.on_any_event(DirCreatedEvent(path))
        self.executor.note_change.assert_called_once_with(core=True, frontend=False)


class QuietPeriodTests(unittest.TestCase):
    def _executor(self):
        executor = ActionsExecutor("https://127.0.0.1:443")
        executor.file = Mock()
        executor.file.core_sync.return_value = True
        executor.file.module_sync.return_value = True
        executor.cleep = Mock()
        executor.quiet_period = 0.2
        executor.poll_interval = 0.05
        return executor

    def _wait_until(self, predicate, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def test_burst_runs_one_sync_and_one_restart(self):
        executor = self._executor()
        executor.start()
        try:
            for _ in range(5):
                executor.note_change(core=True, frontend=False)
                time.sleep(0.02)
            self.assertTrue(self._wait_until(lambda: executor.file.core_sync.call_count >= 1))
            time.sleep(0.4)
            self.assertEqual(executor.file.core_sync.call_count, 1)
            executor.cleep.restart_backend.assert_called_once()
            executor.cleep.restart_frontend.assert_not_called()
        finally:
            executor.stop()
            executor.join(timeout=2)

    def test_failed_sync_does_not_restart(self):
        executor = self._executor()
        executor.file.core_sync.return_value = False
        executor.start()
        try:
            executor.note_change(core=True, frontend=False)
            self.assertTrue(self._wait_until(lambda: executor.file.core_sync.call_count >= 1))
            time.sleep(0.4)
            executor.cleep.restart_backend.assert_not_called()
            executor.cleep.restart_frontend.assert_not_called()
        finally:
            executor.stop()
            executor.join(timeout=2)

    def test_frontend_only_refreshes_the_ui(self):
        executor = self._executor()
        executor.start()
        try:
            executor.note_change(module="audio", frontend=True)
            self.assertTrue(self._wait_until(lambda: executor.file.module_sync.call_count >= 1))
            time.sleep(0.4)
            executor.cleep.restart_backend.assert_not_called()
            executor.cleep.restart_frontend.assert_called_once()
        finally:
            executor.stop()
            executor.join(timeout=2)

    def test_core_and_modules_restart_once(self):
        executor = self._executor()
        executor.start()
        try:
            executor.note_change(core=True, frontend=False)
            executor.note_change(module="network", frontend=False)
            executor.note_change(module="audio", frontend=True)
            self.assertTrue(self._wait_until(lambda: executor.file.core_sync.call_count >= 1))
            time.sleep(0.4)
            self.assertEqual(executor.file.core_sync.call_count, 1)
            self.assertEqual(executor.file.module_sync.call_count, 2)
            executor.cleep.restart_backend.assert_called_once()
            executor.cleep.restart_frontend.assert_not_called()
        finally:
            executor.stop()
            executor.join(timeout=2)


class InotifyTests(unittest.TestCase):
    def test_git_objects_are_not_watched(self):
        root = tempfile.mkdtemp()
        observer = Observer()
        try:
            git_dir = os.path.join(root, ".git", "objects", "ab")
            os.makedirs(git_dir)
            os.makedirs(os.path.join(root, "pkg"))
            executor = Mock()
            handler = CleepHandler(executor)
            seen = []

            def record(event):
                seen.append(event.src_path)

            handler.on_any_event = record
            for directory in iter_watch_directories(root):
                observer.schedule(handler, directory, recursive=False)
            observer.start()
            time.sleep(0.2)
            with open(os.path.join(git_dir, "deadbeef"), "w", encoding="utf-8") as handle:
                handle.write("x")
            with open(os.path.join(root, "pkg", "a.py"), "w", encoding="utf-8") as handle:
                handle.write("x")
            time.sleep(0.5)
        finally:
            observer.stop()
            observer.join(timeout=2)
            shutil.rmtree(root)

        self.assertTrue(any(path.endswith("a.py") for path in seen))
        self.assertFalse(any(".git" in path.split(os.sep) for path in seen))


if __name__ == "__main__":
    unittest.main()
