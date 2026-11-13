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
from cleepcli.console import Console


class PicoError(Exception):
    """Pico SDK / build failure."""


class Pico:
    """
    Install / update the Pico SDK and compile app UF2 firmwares.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------ SDK

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

    def _ensure_toolchain(self) -> None:
        if self._toolchain_ok():
            return
        packages = " ".join(config.PICO_TOOLCHAIN_PACKAGES)
        self.logger.info("Installing Pico toolchain packages: %s", packages)
        console = Console()
        cmd = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update -qq && apt-get install -y -qq %s" % packages
        )
        result = console.command(cmd, 600.0)
        if result.get("killed") or result.get("returncode") != 0:
            raise PicoError(
                "Failed to install toolchain packages: %s"
                % ("\n".join(result.get("stderr") or []) or "apt error")
            )
        if not self._toolchain_ok():
            raise PicoError(
                "Toolchain still missing after apt install "
                "(need cmake and arm-none-eabi-gcc on PATH)"
            )

    def sdk_info(self) -> dict[str, Any]:
        """Return SDK installation metadata."""
        return self._load_meta()

    def sdk_install(self) -> dict[str, Any]:
        """Install toolchain packages + clone pico-sdk with submodules."""
        self._ensure_toolchain()
        sdk_dir = config.PICO_SDK_DIR
        if os.path.isdir(os.path.join(sdk_dir, ".git")):
            self.logger.info("Pico SDK already installed at %s — updating", sdk_dir)
            return self.sdk_update()

        os.makedirs(os.path.dirname(sdk_dir), exist_ok=True)
        if os.path.exists(sdk_dir):
            shutil.rmtree(sdk_dir)

        self.logger.info("Cloning Pico SDK into %s", sdk_dir)
        clone = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "master",
                config.PICO_SDK_REPO,
                sdk_dir,
            ],
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            raise PicoError(
                "git clone failed: %s" % ((clone.stderr or clone.stdout or "").strip())
            )

        sub = subprocess.run(
            ["git", "-C", sdk_dir, "submodule", "update", "--init"],
            capture_output=True,
            text=True,
        )
        if sub.returncode != 0:
            raise PicoError(
                "git submodule update failed: %s"
                % ((sub.stderr or sub.stdout or "").strip())
            )

        meta = self._write_meta()
        self.logger.info(
            "Pico SDK installed (%s / %s)", meta.get("version"), meta.get("revision")
        )
        return meta

    def sdk_update(self) -> dict[str, Any]:
        """Pull latest pico-sdk and refresh submodules."""
        self._ensure_toolchain()
        sdk_dir = config.PICO_SDK_DIR
        if not os.path.isdir(os.path.join(sdk_dir, ".git")):
            return self.sdk_install()

        self.logger.info("Updating Pico SDK in %s", sdk_dir)
        for args in (
            ["git", "-C", sdk_dir, "fetch", "--depth", "1", "origin", "master"],
            ["git", "-C", sdk_dir, "reset", "--hard", "origin/master"],
            ["git", "-C", sdk_dir, "submodule", "update", "--init", "--recursive"],
        ):
            result = subprocess.run(args, capture_output=True, text=True)
            if result.returncode != 0:
                raise PicoError(
                    "SDK update failed (%s): %s"
                    % (
                        " ".join(args),
                        (result.stderr or result.stdout or "").strip(),
                    )
                )

        meta = self._write_meta()
        self.logger.info(
            "Pico SDK updated (%s / %s)", meta.get("version"), meta.get("revision")
        )
        return meta

    def sdk_uninstall(self) -> dict[str, Any]:
        """Remove SDK tree and meta (keeps apt toolchain packages)."""
        sdk_dir = config.PICO_SDK_DIR
        if os.path.isdir(sdk_dir):
            shutil.rmtree(sdk_dir)
            self.logger.info("Removed %s", sdk_dir)
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

    def _run_streamed(self, args: list[str], cwd: str, env: dict[str, str]) -> None:
        self.logger.info("$ %s", " ".join(args))
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            logging.info(line.rstrip("\n"))
        returncode = process.wait()
        if returncode != 0:
            raise PicoError("Command failed (%s): %s" % (returncode, " ".join(args)))

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
