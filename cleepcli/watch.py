#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import time
import logging
from threading import Thread, Lock
from . import config
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
)
import watchdog.events as events
from .cleepapi import CleepApi
from .file import File

_WATCHED_EVENT_TYPES = (EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED, EVENT_TYPE_MOVED)


def _is_under(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return path == root or path.startswith(root + os.sep)


def iter_watch_directories(root):
    """
    Yield directories to watch under root.

    Rejected directory names are not yielded and are not descended into, so
    inotify never watches them.
    """
    if not os.path.isdir(root):
        return
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in CleepHandler.REJECTED_DIRS
        ]
        yield dirpath


class _Batch:
    def __init__(self):
        self.core = False
        self.modules = set()
        self.frontend = False
        self.backend = False
        self.last = 0.0

    def pending(self):
        return self.core or bool(self.modules)

    def take(self):
        batch = _Batch()
        batch.core = self.core
        batch.modules = set(self.modules)
        batch.frontend = self.frontend
        batch.backend = self.backend
        self.core = False
        self.modules = set()
        self.frontend = False
        self.backend = False
        self.last = 0.0
        return batch


class ActionsExecutor(Thread):
    """
    Collect filesystem changes and run one sync plus one restart
    after writes have settled.
    """

    QUIET_PERIOD = 2.0
    POLL_INTERVAL = 0.25

    def __init__(self, rpc_url):
        Thread.__init__(self)
        Thread.daemon = True

        self.logger = logging.getLogger(self.__class__.__name__)
        self.running = True
        self.quiet_period = self.QUIET_PERIOD
        self.poll_interval = self.POLL_INTERVAL
        self._lock = Lock()
        self._batch = _Batch()
        self.file = File()
        self.cleep = CleepApi(rpc_url)

    def stop(self):
        """
        Stop process
        """
        self.running = False

    def note_change(self, module=None, core=False, frontend=False):
        """
        Remember a source change. The sync runs once writes stay quiet.
        """
        with self._lock:
            if module:
                self._batch.modules.add(module)
            if core:
                self._batch.core = True
            if frontend:
                self._batch.frontend = True
            else:
                self._batch.backend = True
            self._batch.last = time.monotonic()

    def _run_batch(self, batch):
        failed = False
        if batch.core:
            self.logger.info("Syncing core")
            if not self.file.core_sync():
                failed = True
        for module in sorted(batch.modules):
            self.logger.info('Syncing module "%s"', module)
            if not self.file.module_sync(module):
                failed = True
        if failed:
            self.logger.error("Sync failed, Cleep was not restarted")
            return
        if batch.backend:
            # Backend restart drops the UI connection. The page reloads on its own
            # once Cleep answers again, with the frontend files already synced.
            self.cleep.restart_backend()
        elif batch.frontend:
            self.cleep.restart_frontend()

    def run(self):
        """
        Wait until no new change arrived during the quiet period, then sync.
        """
        while self.running:
            try:
                time.sleep(self.poll_interval)
                with self._lock:
                    if not self._batch.pending():
                        continue
                    if time.monotonic() - self._batch.last < self.quiet_period:
                        continue
                    batch = self._batch.take()
                self._run_batch(batch)

            except Exception:
                self.logger.exception("Error during action execution:")


class CleepHandler(FileSystemEventHandler):
    """
    Watchdog handler for Cleep
    """

    REJECTED_FILENAMES = [
        "4913",  # vim furtive temp file to check user permissions
        ".gitignore",
    ]
    REJECTED_EXTENSIONS = [
        ".swp",  # vim
        ".swpx",  # vim
        ".swx",  # vim
        ".tmp",  # generic?
        ".offset",  # pygtail
        ".pyc",  # python compiled
        ".log",  # log file
    ]
    REJECTED_PREFIXES = [".", "~"]
    REJECTED_SUFFIXES = ["~"]
    REJECTED_DIRS = [
        ".git",
        ".vscode",
        ".editor",
        "__pycache__",
        "node_modules",
        "tests",
    ]

    def __init__(self, actions_executor):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.actions_executor = actions_executor
        self.observer = None
        self._watched = set()

    def _rejected_path(self, path):
        if not path:
            return False
        return any(part in self.REJECTED_DIRS for part in path.split(os.path.sep))

    def _created_directory(self, event):
        if not getattr(event, "is_directory", False):
            return None
        if event.event_type == events.EVENT_TYPE_CREATED:
            return event.src_path
        if event.event_type == events.EVENT_TYPE_MOVED:
            return getattr(event, "dest_path", None) or event.src_path
        return None

    def schedule_tree(self, root):
        """
        Watch root and every directory under it, except rejected names.
        """
        for directory in iter_watch_directories(root):
            self._watch_directory(directory)

    def _watch_directory(self, path):
        """
        Watch one directory. Rejected names and directories already watched are skipped.
        """
        if self.observer is None or not path or self._rejected_path(path):
            return
        real = os.path.abspath(path)
        if real in self._watched or not os.path.isdir(real):
            return
        self.observer.schedule(self, real, recursive=False)
        self._watched.add(real)

    def _module_name_from_path(self, path):
        prefix = config.MODULES_SRC.rstrip(os.sep) + os.sep
        if not path or not path.startswith(prefix):
            return None
        name = path[len(prefix):].split(os.sep, 1)[0]
        if not name or name in self.REJECTED_DIRS:
            return None
        return name

    def _event_path(self, event):
        """
        Path to evaluate for filters. Prefer the destination of a move (atomic save).
        """
        if event.event_type == EVENT_TYPE_MOVED and getattr(event, "dest_path", None):
            return event.dest_path
        return event.src_path

    def __is_event_dropped(self, event):
        """
        Analyse event and return True if event must be dropped
        Return:
            bool: True if event must be dropped
        """
        if not event:
            self.logger.debug(" Filtered: invalid event")
            return True

        # Directory create/move is handled in on_any_event before this filter
        if type(event) is events.DirModifiedEvent:
            self.logger.debug(" Filtered: DirModifiedEvent")
            return True

        if getattr(event, "is_directory", False):
            self.logger.debug(" Filtered: directory event")
            return True

        if event.event_type not in _WATCHED_EVENT_TYPES:
            self.logger.debug(" Filtered: not watched event type")
            return True

        path = self._event_path(event)

        # filter event on current script
        if path == ".%s" % __file__:
            self.logger.debug(" Filtered: event on current script")
            return True

        # filter root event
        if path == ".":
            self.logger.debug(" Filtered: root event")
            return True

        # filter invalid extension
        if os.path.splitext(path)[1] in self.REJECTED_EXTENSIONS:
            self.logger.debug(" Filtered: invalid extension")
            return True

        # filter by prefix (basename: watchdog reports absolute paths)
        basename = os.path.basename(path)
        for prefix in self.REJECTED_PREFIXES:
            if basename.startswith(prefix):
                self.logger.debug(" Filtered: source prefix")
                return True

        # filter by suffix
        for suffix in self.REJECTED_SUFFIXES:
            if path.endswith(suffix):
                self.logger.debug("Filtered: source suffix")
                return True

        # filter by filename
        for filename in self.REJECTED_FILENAMES:
            if path.endswith(filename):
                self.logger.debug(" Filtered: filename")
                return True

        # filter by dir
        if self._rejected_path(path):
            self.logger.debug(" Filtered: directory")
            return True

        self.logger.debug(" NotFiltered")
        return False

    def __change_on_module(self, event):
        """
        Change on module

        Args:
            event: watchdog event

        Returns:
            module name (string) or None if nothing found
        """
        pattern = r"^%s/(.*?)/(?:frontend|backend|scripts)/.*$" % (
            re.escape(config.MODULES_SRC)
        )
        # self.logger.debug('Module pattern: %s' % pattern)

        path = self._event_path(event)
        if path:
            res = re.findall(pattern, path)
            if res and len(res) > 0:
                return res[0]

        return None

    def __change_on_core(self, event):
        """
        Change on core

        Args:
            event: watchdog event

        Returns:
            True if change occurs in core, False otherwise
        """
        pattern_core = r"^(%s/(?!tests|modules)(.*\.py)|%s/.*)$" % (
            re.escape(config.CORE_SRC),
            re.escape(config.HTML_SRC),
        )
        pattern_bin = r"^%s/cleep" % (re.escape(config.BIN_SRC))
        # self.logger.debug('Core pattern: %s' % pattern_core)
        # self.logger.debug('Bin pattern: %s' % pattern_bin)

        path = self._event_path(event)
        if not path:
            return False
        if re.search(pattern_core, path):
            return True
        if re.search(pattern_bin, path):
            return True

        return False

    def __change_on_frontend(self, event):
        """
        Detect change on frontend

        Args:
            event: watchdog event

        Returns:
            True if change on frontend, False otherwise
        """
        pattern = r"^(%s/|%s/(?:.*?)/frontend/).*$" % (
            re.escape(config.HTML_SRC),
            re.escape(config.MODULES_SRC),
        )
        # self.logger.debug('Frontend pattern: %s' % pattern)

        path = self._event_path(event)
        if path and re.search(pattern, path):
            return True

        return False

    def _queue_change(self, event):
        frontend = self.__change_on_frontend(event)
        module = self.__change_on_module(event)
        core = module is None and self.__change_on_core(event)
        if module:
            self.logger.debug('  Change on module "%s"' % module)
            self.actions_executor.note_change(module=module, frontend=frontend)
        elif core:
            self.logger.debug("  Change on core")
            self.actions_executor.note_change(core=True, frontend=frontend)
        else:
            self.logger.debug("  Dropped due to useless change")

    def on_any_event(self, event):
        try:
            self.logger.debug("Event: %s" % event)
            created = self._created_directory(event)
            if created:
                self.schedule_tree(created)
                if self._rejected_path(created):
                    self.logger.debug(" Filtered: directory")
                    return
                module = self._module_name_from_path(created)
                if module:
                    frontend = self.__change_on_frontend(event)
                    self.logger.debug('  Change on module "%s"' % module)
                    self.actions_executor.note_change(module=module, frontend=frontend)
                    return
                if _is_under(created, config.CORE_SRC) or _is_under(
                    created, config.HTML_SRC
                ) or _is_under(created, config.BIN_SRC):
                    frontend = self.__change_on_frontend(event)
                    self.logger.debug("  Change on core")
                    self.actions_executor.note_change(core=True, frontend=frontend)
                return

            if self.__is_event_dropped(event):
                return
            self._queue_change(event)

        except Exception:
            self.logger.exception("Error occured during watcher event processing:")


class CleepWatchdog:
    """
    Cleep core and module watchdog
    """

    def __init__(self, rpc_url):
        """
        Constructor

        Args:
            rpc_url (str): Cleep RPC url
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.actions_executor = ActionsExecutor(rpc_url)

    def watch(self):
        """
        Start watchdog that monitors filesystem changes on Cleep sources
        """
        path = "%s/" % config.REPO_DIR
        self.actions_executor.start()

        if not os.path.exists(path):
            self.logger.error(
                'Please get Cleep sources using "cleep-cli getcore" command'
            )
            return False

        event_handler = CleepHandler(self.actions_executor)
        observer = Observer()
        event_handler.observer = observer
        scheduled = 0
        for root in (
            config.CORE_SRC,
            config.HTML_SRC,
            config.BIN_SRC,
            config.MODULES_SRC,
        ):
            before = len(event_handler._watched)
            event_handler.schedule_tree(root)
            scheduled += len(event_handler._watched) - before

        if not scheduled:
            self.logger.error(
                'Please get Cleep sources using "cleep-cli getcore" command'
            )
            return False

        self.logger.info('Cleep watchdog is running on "%s" (CTRL-C to stop)' % path)
        observer.start()
        try:
            while True:
                time.sleep(0.25)
        except KeyboardInterrupt:
            observer.stop()
            self.actions_executor.stop()
        observer.join()

        return True
