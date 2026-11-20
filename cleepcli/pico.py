# -*- coding: utf-8 -*-
"""
Raspberry Pi Pico SDK management and UF2 firmware builds for Cleep apps.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any

import cleepcli.config as config


class PicoError(Exception):
    """Pico SDK / build failure."""


class Pico:
    """
    Install / update the Pico SDK and compile app UF2 firmwares.
    """

    # Machine-readable step markers for developer UI progress (stdout).
    STEP_MARKER_PREFIX = "CLEEP_PICO_STEP:"
    INSTALL_STEPS = (
        ("toolchain", "Install apt toolchain (cmake, arm-none-eabi)"),
        ("clone", "Clone pico-sdk"),
        ("submodules", "Initialize pico-sdk submodules"),
        ("finalize", "Write SDK metadata"),
    )
    UPDATE_STEPS = (
        ("toolchain", "Check apt toolchain"),
        ("fetch", "Fetch latest pico-sdk"),
        ("reset", "Reset pico-sdk to origin/master"),
        ("submodules", "Update pico-sdk submodules"),
    )

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------ SDK

    def _emit(self, message: str) -> None:
        """Print a line to stdout (streamed by developer EndlessConsole)."""
        # print only: cleep-cli logging also uses stdout and would duplicate lines.
        print(message, flush=True)
        self.logger.debug("%s", message)

    def _emit_step(self, index: int, total: int, step_id: str, label: str) -> None:
        """Emit a progress marker + human-readable step header."""
        self._emit(
            "%s%s/%s:%s:%s"
            % (self.STEP_MARKER_PREFIX, index, total, step_id, label)
        )
        self._emit("=== [%s/%s] %s ===" % (index, total, label))

    def _run_streamed(
        self,
        args: list[str] | str,
        error_prefix: str | None = None,
        shell: bool = False,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """
        Run a command and stream combined stdout/stderr line by line.

        Args:
            args: argv list, or shell command string when shell=True
            error_prefix: message prefix on non-zero exit
            shell: pass command through the shell
            cwd: optional working directory
            env: optional environment (defaults to a copy of os.environ)
        """
        run_env = dict(env) if env is not None else os.environ.copy()
        run_env.setdefault("GIT_TERMINAL_PROMPT", "0")
        # Make apt less chatty about progress bars that redraw the same line.
        run_env.setdefault("DEBIAN_FRONTEND", "noninteractive")
        if isinstance(args, list):
            self.logger.debug("$ %s", " ".join(args))
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=shell,
            cwd=cwd,
            env=run_env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
        returncode = proc.wait()
        if returncode != 0:
            prefix = error_prefix or "Command failed"
            detail = args if isinstance(args, str) else " ".join(args)
            raise PicoError("%s (exit %s): %s" % (prefix, returncode, detail))

    def _toolchain_ok(self) -> bool:
        return bool(shutil.which("cmake") and shutil.which("arm-none-eabi-gcc"))

    def _git_revision(self, sdk_dir: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", sdk_dir, "rev-parse", "--short", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            return (result.stdout or "").strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    def _git_describe(self, sdk_dir: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", sdk_dir, "describe", "--tags", "--always"],
                check=True,
                capture_output=True,
                text=True,
            )
            return (result.stdout or "").strip()
        except (OSError, subprocess.CalledProcessError):
            return self._git_revision(sdk_dir)

    def _write_meta(self, **extra: Any) -> dict[str, Any]:
        sdk_dir = config.PICO_SDK_DIR
        installed = os.path.isdir(os.path.join(sdk_dir, ".git"))
        meta = {
            "installed": installed,
            "path": sdk_dir,
            "revision": self._git_revision(sdk_dir) if installed else "",
            "version": self._git_describe(sdk_dir) if installed else "",
            "updated_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "toolchain_ok": self._toolchain_ok(),
        }
        meta.update(extra)
        os.makedirs(os.path.dirname(config.PICO_SDK_META), exist_ok=True)
        with open(config.PICO_SDK_META, "w", encoding="utf-8") as handle:
            json.dump(meta, handle, indent=4, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        return meta

    def _load_meta(self) -> dict[str, Any]:
        if not os.path.isfile(config.PICO_SDK_META):
            installed = os.path.isdir(os.path.join(config.PICO_SDK_DIR, ".git"))
            return {
                "installed": installed,
                "path": config.PICO_SDK_DIR,
                "revision": self._git_revision(config.PICO_SDK_DIR) if installed else "",
                "version": self._git_describe(config.PICO_SDK_DIR) if installed else "",
                "updated_at": None,
                "toolchain_ok": self._toolchain_ok(),
            }
        try:
            with open(config.PICO_SDK_META, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("path", config.PICO_SDK_DIR)
        data["toolchain_ok"] = self._toolchain_ok()
        data["installed"] = bool(
            data.get("installed")
            or os.path.isdir(os.path.join(config.PICO_SDK_DIR, ".git"))
        )
        return data

    def _ensure_toolchain(self, *, emit_steps: bool = False, step_index: int = 1, step_total: int = 4) -> None:
        """
        Ensure cmake + arm-none-eabi-gcc are on PATH (apt install if needed).

        Args:
            emit_steps: print step markers / headers for UI progress
            step_index: 1-based step index when emit_steps
            step_total: total steps when emit_steps
        """
        label = self.INSTALL_STEPS[0][1]
        if emit_steps:
            self._emit_step(step_index, step_total, "toolchain", label)
        if self._toolchain_ok():
            self._emit("Toolchain already present (cmake, arm-none-eabi-gcc) — skipping apt.")
            return
        packages = " ".join(config.PICO_TOOLCHAIN_PACKAGES)
        self._emit("Installing Pico toolchain packages via apt: %s" % packages)
        self._emit("(This step alone can take several minutes on a Raspberry Pi.)")
        # No -qq: stream apt download/install lines to the developer console.
        cmd = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update && apt-get install -y %s" % packages
        )
        self._run_streamed(cmd, "Failed to install toolchain packages", shell=True)
        if not self._toolchain_ok():
            raise PicoError(
                "Toolchain still missing after apt install "
                "(need cmake and arm-none-eabi-gcc on PATH)"
            )
        self._emit("Toolchain install complete.")

    def sdk_info(self) -> dict[str, Any]:
        """Return SDK installation metadata."""
        return self._load_meta()

    def sdk_install(self) -> dict[str, Any]:
        """Install toolchain packages + clone pico-sdk with submodules."""
        total = len(self.INSTALL_STEPS)
        self._emit(
            "Pico SDK install started (often 10+ minutes on first run — "
            "apt toolchain + git clone + submodules)."
        )
        self._ensure_toolchain(emit_steps=True, step_index=1, step_total=total)

        sdk_dir = config.PICO_SDK_DIR
        if os.path.isdir(os.path.join(sdk_dir, ".git")):
            self._emit("Pico SDK already installed at %s — switching to update." % sdk_dir)
            return self.sdk_update()

        os.makedirs(os.path.dirname(sdk_dir), exist_ok=True)
        if os.path.exists(sdk_dir):
            shutil.rmtree(sdk_dir)

        self._emit_step(2, total, "clone", self.INSTALL_STEPS[1][1])
        self._emit("Cloning %s into %s" % (config.PICO_SDK_REPO, sdk_dir))
        self._run_streamed(
            [
                "git",
                "clone",
                "--progress",
                "--depth",
                "1",
                "--branch",
                "master",
                config.PICO_SDK_REPO,
                sdk_dir,
            ],
            "git clone failed",
        )

        self._emit_step(3, total, "submodules", self.INSTALL_STEPS[2][1])
        self._run_streamed(
            [
                "git",
                "-C",
                sdk_dir,
                "submodule",
                "update",
                "--init",
                "--progress",
            ],
            "git submodule update failed",
        )

        self._emit_step(4, total, "finalize", self.INSTALL_STEPS[3][1])
        meta = self._write_meta()
        self._emit(
            "Pico SDK installed (%s / %s)"
            % (meta.get("version"), meta.get("revision"))
        )
        self._emit(
            "%s%s/%s:done:Install complete"
            % (self.STEP_MARKER_PREFIX, total, total)
        )
        return meta

    def sdk_update(self) -> dict[str, Any]:
        """Pull latest pico-sdk and refresh submodules."""
        total = len(self.UPDATE_STEPS)
        self._emit("Pico SDK update started.")
        self._ensure_toolchain(emit_steps=True, step_index=1, step_total=total)

        sdk_dir = config.PICO_SDK_DIR
        if not os.path.isdir(os.path.join(sdk_dir, ".git")):
            return self.sdk_install()

        self._emit_step(2, total, "fetch", self.UPDATE_STEPS[1][1])
        self._run_streamed(
            ["git", "-C", sdk_dir, "fetch", "--progress", "--depth", "1", "origin", "master"],
            "SDK fetch failed",
        )

        self._emit_step(3, total, "reset", self.UPDATE_STEPS[2][1])
        self._run_streamed(
            ["git", "-C", sdk_dir, "reset", "--hard", "origin/master"],
            "SDK reset failed",
        )

        self._emit_step(4, total, "submodules", self.UPDATE_STEPS[3][1])
        self._run_streamed(
            [
                "git",
                "-C",
                sdk_dir,
                "submodule",
                "update",
                "--init",
                "--recursive",
                "--progress",
            ],
            "SDK submodule update failed",
        )

        meta = self._write_meta()
        self._emit(
            "Pico SDK updated (%s / %s)"
            % (meta.get("version"), meta.get("revision"))
        )
        self._emit(
            "%s%s/%s:done:Update complete"
            % (self.STEP_MARKER_PREFIX, total, total)
        )
        return meta

    def sdk_uninstall(self) -> dict[str, Any]:
        """Remove SDK tree and meta (keeps apt toolchain packages)."""
        sdk_dir = config.PICO_SDK_DIR
        if os.path.isdir(sdk_dir):
            shutil.rmtree(sdk_dir)
            self._emit("Removed %s" % sdk_dir)
        if os.path.isfile(config.PICO_SDK_META):
            os.remove(config.PICO_SDK_META)
        return {
            "installed": False,
            "path": sdk_dir,
            "revision": "",
            "version": "",
            "updated_at": None,
            "toolchain_ok": self._toolchain_ok(),
        }

    # --------------------------------------------------------------- build

    def _module_firmwares_dir(self, module_name: str) -> str:
        module_src = os.path.join(config.MODULES_SRC, module_name)
        if not os.path.isdir(module_src):
            raise PicoError('Module "%s" does not exist in %s' % (module_name, config.MODULES_SRC))
        return os.path.join(module_src, "firmwares")

    def status(self, module_name: str) -> dict[str, Any]:
        """UF2 readiness for all firmwares of a module."""
        from cleep.libs.internals.firmware_manifest import firmwares_uf2_readiness

        firmwares_dir = self._module_firmwares_dir(module_name)
        if not os.path.isdir(firmwares_dir):
            return {
                "module": module_name,
                "uf2_ready": True,
                "uf2_blocking": [],
                "items": [],
                "count": 0,
                "sdk": self.sdk_info(),
            }
        ready = firmwares_uf2_readiness(firmwares_dir)
        ready["module"] = module_name
        ready["sdk"] = self.sdk_info()
        return ready

    def _find_built_uf2(self, cmake_build_dir: str) -> str | None:
        candidates = []
        for root, _dirs, files in os.walk(cmake_build_dir):
            for filename in files:
                if filename.lower().endswith(".uf2"):
                    candidates.append(os.path.join(root, filename))
        if not candidates:
            return None
        candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        return candidates[0]

    def build_firmware(self, module_name: str, slug: str | None = None) -> dict[str, Any]:
        """
        Compile UF2 firmwares for a module (all uf2 kinds, or one slug).
        """
        from cleep.libs.internals.firmware_manifest import (
            KIND_UF2,
            FirmwareManifestError,
            build_dir_path,
            payload_uf2_path,
            pico_board_for_targets,
            scan_firmware_sources,
            write_build_stamp,
        )

        sdk = self.sdk_info()
        if not sdk.get("installed"):
            raise PicoError("Pico SDK is not installed — run: cleep-cli pico sdk install")
        if not sdk.get("toolchain_ok"):
            raise PicoError(
                "Pico toolchain missing — run: cleep-cli pico sdk install"
            )

        firmwares_dir = self._module_firmwares_dir(module_name)
        if not os.path.isdir(firmwares_dir):
            raise PicoError('No firmwares/ directory for module "%s"' % module_name)

        try:
            sources = scan_firmware_sources(firmwares_dir)
        except FirmwareManifestError as error:
            raise PicoError(str(error)) from error

        if slug:
            sources = [item for item in sources if item["slug"] == slug]
            if not sources:
                raise PicoError(
                    'Firmware slug "%s" not found under firmwares/' % slug
                )

        uf2_sources = [item for item in sources if item["data"]["kind"] == KIND_UF2]
        if not uf2_sources:
            raise PicoError("No uf2 firmwares to build")

        env = os.environ.copy()
        env["PICO_SDK_PATH"] = config.PICO_SDK_DIR
        sdk_import = os.path.join(
            config.PICO_SDK_DIR, "external", "pico_sdk_import.cmake"
        )
        if not os.path.isfile(sdk_import):
            raise PicoError("Missing pico_sdk_import.cmake at %s" % sdk_import)

        built = []
        for source in uf2_sources:
            source_dir = source["source_dir"]
            data = source["data"]
            board = pico_board_for_targets(data["targets"])
            if len(data["targets"]) > 1:
                self.logger.warning(
                    'Firmware "%s" has multiple targets %s — using PICO_BOARD=%s '
                    "(prefer one folder per board)",
                    source["slug"],
                    data["targets"],
                    board,
                )

            build_root = build_dir_path(source_dir)
            cmake_dir = os.path.join(build_root, "cmake")
            if os.path.isdir(cmake_dir):
                shutil.rmtree(cmake_dir)
            os.makedirs(cmake_dir, exist_ok=True)

            self.logger.info(
                'Building firmware "%s" (board=%s, version=%s)',
                source["slug"],
                board,
                data["version"],
            )
            configure = [
                "cmake",
                "-S",
                source_dir,
                "-B",
                cmake_dir,
                "-DPICO_SDK_PATH=%s" % config.PICO_SDK_DIR,
                "-DPICO_BOARD=%s" % board,
            ]
            self._run_streamed(configure, cwd=source_dir, env=env)
            self._run_streamed(
                ["cmake", "--build", cmake_dir, "--parallel"],
                cwd=source_dir,
                env=env,
            )

            uf2_path = self._find_built_uf2(cmake_dir)
            if not uf2_path:
                raise PicoError(
                    'No .uf2 produced for "%s" — ensure CMakeLists.txt calls '
                    "pico_add_extra_outputs(...)" % source["slug"]
                )

            dest = payload_uf2_path(source_dir)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(uf2_path, dest)
            stamp = write_build_stamp(
                source_dir,
                version=data["version"],
                sdk_revision=sdk.get("revision") or "",
            )
            self.logger.info('UF2 ready: %s', dest)
            built.append(
                {
                    "slug": source["slug"],
                    "board": board,
                    "version": data["version"],
                    "payload": dest,
                    "stamp": stamp,
                }
            )

        return {
            "module": module_name,
            "built": built,
            "count": len(built),
            "sdk": self.sdk_info(),
        }
