#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Manage the durable cleep-watch systemd unit.

The unit runs ``cleep-cli watch`` outside of cleep.service so backend restarts
do not kill the watcher mid-sync.
"""

import logging
import os
import shutil

from .console import Console

WATCH_SERVICE = "cleep-watch.service"
WATCH_UNIT_DST = "/lib/systemd/system/%s" % WATCH_SERVICE


def bundled_unit_path():
    """
    Path to the unit file shipped inside the cleepcli package.

    Returns:
        str: absolute path to cleep-watch.service
    """
    return os.path.join(os.path.dirname(__file__), "systemd", WATCH_SERVICE)


class WatchService:
    """
    Install / enable / control cleep-watch.service via systemctl.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.console = Console()

    def _systemctl(self, *args, timeout=60.0):
        cmd = "/bin/systemctl " + " ".join(args)
        self.logger.debug("systemctl cmd: %s", cmd)
        return self.console.command(cmd, timeout)

    def _ok(self, resp):
        return not resp.get("killed") and resp.get("returncode", 1) == 0

    def _daemon_reload(self):
        return self._ok(self._systemctl("daemon-reload"))

    def _unit_content_changed(self, src):
        """
        Return True when bundled unit differs from the installed unit (or missing).
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            return True
        try:
            with open(src, "rb") as handle:
                new = handle.read()
            with open(WATCH_UNIT_DST, "rb") as handle:
                old = handle.read()
        except OSError:
            return True
        return new != old

    def install(self, restart_if_active=False):
        """
        Copy the bundled unit to systemd and reload the daemon.

        Args:
            restart_if_active (bool): when True, restart the unit if it is
                already running so a new cleep-cli binary/unit is picked up.
                Default False: developer ``ensure`` calls install on every
                Cleep start and must not bounce the watcher (catch-up would
                restart Cleep again).

        Returns:
            bool: True on success
        """
        src = bundled_unit_path()
        if not os.path.isfile(src):
            self.logger.error("Bundled unit not found: %s", src)
            return False
        unit_changed = self._unit_content_changed(src)
        was_active = self.is_active()
        try:
            os.makedirs(os.path.dirname(WATCH_UNIT_DST), exist_ok=True)
            shutil.copyfile(src, WATCH_UNIT_DST)
        except OSError as error:
            self.logger.error("Unable to install %s: %s", WATCH_UNIT_DST, error)
            return False
        if not self._daemon_reload():
            self.logger.error("systemctl daemon-reload failed after install")
            return False
        self.logger.info("Installed %s", WATCH_UNIT_DST)
        # Restart when asked (package upgrade) or when the unit file changed
        # while the service was already running.
        if was_active and (restart_if_active or unit_changed):
            self.logger.info(
                "Restarting %s to apply watcher changes", WATCH_SERVICE
            )
            return self.restart()
        return True

    def uninstall(self):
        """
        Disable the unit, remove the unit file, reload systemd.

        Returns:
            bool: True on success (missing unit is OK)
        """
        self.disable()
        try:
            if os.path.isfile(WATCH_UNIT_DST):
                os.remove(WATCH_UNIT_DST)
                self.logger.info("Removed %s", WATCH_UNIT_DST)
        except OSError as error:
            self.logger.error("Unable to remove %s: %s", WATCH_UNIT_DST, error)
            return False
        if not self._daemon_reload():
            self.logger.error("systemctl daemon-reload failed after uninstall")
            return False
        return True

    def enable(self):
        """
        Enable and start the unit (installs the unit file first if missing).

        Returns:
            bool: True on success
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            if not self.install():
                return False
        resp = self._systemctl("enable", "--now", WATCH_SERVICE)
        if not self._ok(resp):
            self.logger.error(
                "Unable to enable %s: %s %s",
                WATCH_SERVICE,
                resp.get("stdout"),
                resp.get("stderr"),
            )
            return False
        return self.is_active()

    def disable(self):
        """
        Disable and stop the unit.

        Returns:
            bool: True on success (or if unit was not installed)
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            return True
        resp = self._systemctl("disable", "--now", WATCH_SERVICE)
        if not self._ok(resp):
            # Unit may already be inactive/disabled
            self.logger.debug(
                "disable --now %s: %s %s",
                WATCH_SERVICE,
                resp.get("stdout"),
                resp.get("stderr"),
            )
        return True

    def start(self):
        """
        Start the unit (catch-up sync runs on ExecStart).

        Returns:
            bool: True on success
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            if not self.install():
                return False
        resp = self._systemctl("start", WATCH_SERVICE)
        if not self._ok(resp):
            self.logger.error(
                "Unable to start %s: %s %s",
                WATCH_SERVICE,
                resp.get("stdout"),
                resp.get("stderr"),
            )
            return False
        return True

    def stop(self):
        """
        Stop the unit.

        Returns:
            bool: True on success
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            return True
        resp = self._systemctl("stop", WATCH_SERVICE)
        if not self._ok(resp):
            self.logger.error(
                "Unable to stop %s: %s %s",
                WATCH_SERVICE,
                resp.get("stdout"),
                resp.get("stderr"),
            )
            return False
        return True

    def restart(self):
        """
        Restart the unit (re-runs catch-up sync on start).

        Returns:
            bool: True on success
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            return self.enable()
        resp = self._systemctl("restart", WATCH_SERVICE, timeout=180.0)
        if not self._ok(resp):
            self.logger.error(
                "Unable to restart %s: %s %s",
                WATCH_SERVICE,
                resp.get("stdout"),
                resp.get("stderr"),
            )
            return False
        return True

    def is_active(self):
        """
        Return True if the unit is active.
        """
        resp = self._systemctl("is-active", WATCH_SERVICE, timeout=5.0)
        active = "".join(resp.get("stdout") or []).strip()
        return active == "active"

    def status(self):
        """
        Print / return a short status string for the unit.

        Returns:
            str: systemctl is-active output (or "not-installed")
        """
        if not os.path.isfile(WATCH_UNIT_DST):
            return "not-installed"
        resp = self._systemctl("is-active", WATCH_SERVICE, timeout=5.0)
        return "".join(resp.get("stdout") or []).strip() or "unknown"
