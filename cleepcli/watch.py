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
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
)
import watchdog.events as events
from .cleepapi import CleepApi
from .file import File

_WATCHED_EVENT_TYPES = (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
)


def _is_under(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return path == root or path.startswith(root + os.sep)


# One observer.schedule() = one inotify instance. Keep that count low
# (kernel default is often 128) by using recursive watches on a few roots.
MODULE_CONTENT_DIRS = ("backend", "frontend", "scripts")


def iter_watch_roots():
    """
    Yield (path, recursive) pairs to schedule on the observer.

    Core/html/bin are watched recursively. Modules watch only backend,
    frontend and scripts so .git under each app is never registered.
    """
    for root in (config.CORE_SRC, config.HTML_SRC, config.BIN_SRC):
        if os.path.isdir(root):
            yield root, True

    if not os.path.isdir(config.MODULES_SRC):
        return

    yield config.MODULES_SRC, False
    try:
        names = sorted(os.listdir(config.MODULES_SRC))
    except OSError:
        return
    for name in names:
        if name in CleepHandler.REJECTED_DIRS:
            continue
        module_path = os.path.join(config.MODULES_SRC, name)
        if not os.path.isdir(module_path):
            continue
        # Non-recursive: see backend/frontend/scripts appear without watching .git
        yield module_path, False
        for sub in MODULE_CONTENT_DIRS:
            content = os.path.join(module_path, sub)
            if os.path.isdir(content):
                yield content, True


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

    def note_change(self, module=None, core=False, frontend=False, backend=False):
        """
        Remember a source change. The sync runs once writes stay quiet.

        Scripts-only edits set neither frontend nor backend: files are synced
        and Cleep is left running (install scripts are not re-run on watch).
        """
        with self._lock:
            if module:
                self._batch.modules.add(module)
            if core:
                self._batch.core = True
            if frontend:
                self._batch.frontend = True
            if backend:
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

    def schedule_all(self):
        """
        Install the few recursive watches needed for core and module sources.
        """
        for path, recursive in iter_watch_roots():
            self._schedule(path, recursive=recursive)

    def _schedule(self, path, recursive=True):
        """
        Watch path once. Rejected names and duplicates are skipped.
        """
        if self.observer is None or not path or self._rejected_path(path):
            return False
        real = os.path.abspath(path)
        if real in self._watched or not os.path.isdir(real):
            return False
        self.observer.schedule(self, real, recursive=recursive)
        self._watched.add(real)
        return True

    def _schedule_module(self, module_path):
        """
        Watch a module root (non-recursive) and its content dirs. Never watches .git.
        """
        if not module_path or not os.path.isdir(module_path):
            return
        if os.path.basename(module_path) in self.REJECTED_DIRS:
            return
        self._schedule(module_path, recursive=False)
        for sub in MODULE_CONTENT_DIRS:
            self._schedule(os.path.join(module_path, sub), recursive=True)

    def _maybe_schedule_new_path(self, path):
        """
        Add watches when a new module or module content dir appears.

        Core/html/bin are already recursive, so new dirs there need no schedule.
        """
        if not path or self._rejected_path(path):
            return
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        modules_root = os.path.abspath(config.MODULES_SRC)
        if os.path.abspath(parent) == modules_root:
            self._schedule_module(path)
            return
        if name in MODULE_CONTENT_DIRS and os.path.abspath(os.path.dirname(parent)) == modules_root:
            self._schedule(path, recursive=True)

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
        pattern = r"^%s/(.*?)/(?:frontend|backend|scripts)(?:/.*)?$" % (
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
        pattern = r"^(%s/|%s/(?:.*?)/frontend(?:/)?).*$" % (
            re.escape(config.HTML_SRC),
            re.escape(config.MODULES_SRC),
        )
        # self.logger.debug('Frontend pattern: %s' % pattern)

        path = self._event_path(event)
        if path and re.search(pattern, path):
            return True

        return False

    def __change_on_scripts(self, event):
        """
        Detect change on module install scripts
        """
        pattern = r"^%s/(?:.*?)/scripts(?:/.*)?$" % (re.escape(config.MODULES_SRC))
        path = self._event_path(event)
        return bool(path and re.search(pattern, path))

    def _queue_change(self, event):
        frontend = self.__change_on_frontend(event)
        scripts = self.__change_on_scripts(event)
        module = self.__change_on_module(event)
        core = module is None and self.__change_on_core(event)
        # Scripts are synced for the next install; they do not reload Cleep.
        backend = not frontend and not scripts
        if module:
            self.logger.debug('  Change on module "%s"' % module)
            self.actions_executor.note_change(
                module=module, frontend=frontend, backend=backend
            )
        elif core:
            self.logger.debug("  Change on core")
            self.actions_executor.note_change(
                core=True, frontend=frontend, backend=backend
            )
        else:
            self.logger.debug("  Dropped due to useless change")

    def on_any_event(self, event):
        try:
            self.logger.debug("Event: %s" % event)
            created = self._created_directory(event)
            if created:
                if self._rejected_path(created):
                    self.logger.debug(" Filtered: directory")
                    return
                self._maybe_schedule_new_path(created)
                # New module root: only schedule watches; wait for content files
                modules_root = os.path.abspath(config.MODULES_SRC)
                if os.path.abspath(os.path.dirname(created)) == modules_root:
                    return
                if self.__change_on_module(event):
                    self._queue_change(event)
                elif _is_under(created, config.CORE_SRC) or _is_under(
                    created, config.HTML_SRC
                ) or _is_under(created, config.BIN_SRC):
                    frontend = self.__change_on_frontend(event)
                    self.actions_executor.note_change(
                        core=True,
                        frontend=frontend,
                        backend=not frontend,
                    )
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
        try:
            event_handler.schedule_all()
        except OSError as error:
            self.logger.error(
                "Unable to start filesystem watches (%s). "
                "Check fs.inotify.max_user_instances / max_user_watches",
                error,
            )
            self.actions_executor.stop()
            return False

        if not event_handler._watched:
            self.logger.error(
                'Please get Cleep sources using "cleep-cli getcore" command'
            )
            self.actions_executor.stop()
            return False

        self.logger.info(
            'Cleep watchdog is running on "%s" (%d watches, CTRL-C to stop)'
            % (path, len(event_handler._watched))
        )
        try:
            observer.start()
        except OSError as error:
            self.logger.error(
                "Unable to start filesystem watches (%s). "
                "Check fs.inotify.max_user_instances / max_user_watches",
                error,
            )
            self.actions_executor.stop()
            return False
        try:
            while True:
                time.sleep(0.25)
        except KeyboardInterrupt:
            observer.stop()
            self.actions_executor.stop()
        observer.join()

        return True
