# -*- coding: utf-8 -*-

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from cleepcli.pico import Pico, PicoError
import cleepcli.config as config


class PicoSdkTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = self._tmpdir.name
        self.sdk_dir = os.path.join(self.root, "pico-sdk")
        self.meta = os.path.join(self.root, "pico-sdk.json")
        self._patchers = [
            patch.object(config, "PICO_SDK_DIR", self.sdk_dir),
            patch.object(config, "PICO_SDK_META", self.meta),
        ]
        for patcher in self._patchers:
            patcher.start()
        self.pico = Pico()

    def tearDown(self):
        for patcher in self._patchers:
            patcher.stop()
        self._tmpdir.cleanup()

    def test_sdk_info_not_installed(self):
        with patch.object(self.pico, "_toolchain_ok", return_value=True):
            with patch.object(self.pico, "_disk_free_bytes", return_value=2 * 1024 * 1024 * 1024):
                info = self.pico.sdk_info()
        self.assertFalse(info["installed"])
        self.assertTrue(info["toolchain_ok"])
        self.assertTrue(info["disk_ok"])
        self.assertEqual(info["disk_required_bytes"], Pico.DISK_FREE_TOOLCHAIN_OK_BYTES)

    def test_ensure_disk_space_raises(self):
        with patch.object(self.pico, "_toolchain_ok", return_value=True):
            with patch.object(self.pico, "_disk_free_bytes", return_value=10 * 1024 * 1024):
                with self.assertRaises(PicoError) as ctx:
                    self.pico._ensure_disk_space()
        self.assertIn("Not enough free disk space", str(ctx.exception))

    def test_arm_lib_ok_rejects_echoed_name(self):
        with patch("cleepcli.pico.shutil.which", return_value="/usr/bin/arm-none-eabi-gcc"):
            with patch("cleepcli.pico.subprocess.check_output", return_value="libc.a\n"):
                with patch("cleepcli.pico.os.path.isfile", return_value=False):
                    self.assertFalse(self.pico._arm_lib_ok("libc.a"))

    def test_arm_lib_ok_accepts_realpath(self):
        with patch("cleepcli.pico.shutil.which", return_value="/usr/bin/arm-none-eabi-gcc"):
            with patch(
                "cleepcli.pico.subprocess.check_output",
                return_value="/usr/lib/arm-none-eabi/newlib/libc.a\n",
            ):
                with patch("cleepcli.pico.os.path.isfile", return_value=True):
                    self.assertTrue(self.pico._arm_lib_ok("libc.a"))

    def test_sdk_uninstall_removes_meta(self):
        os.makedirs(self.sdk_dir)
        with open(self.meta, "w", encoding="utf-8") as handle:
            json.dump({"installed": True}, handle)
        with patch.object(self.pico, "_toolchain_ok", return_value=False):
            info = self.pico.sdk_uninstall()
        self.assertFalse(os.path.exists(self.sdk_dir))
        self.assertFalse(os.path.isfile(self.meta))
        self.assertFalse(info["installed"])

    def test_require_version_rejects_empty(self):
        with self.assertRaises(PicoError):
            self.pico._require_version("")
        with self.assertRaises(PicoError):
            self.pico._require_version("   ")

    @patch.object(Pico, "_run_streamed")
    @patch.object(Pico, "_ensure_toolchain")
    @patch.object(Pico, "_ensure_disk_space")
    def test_sdk_install_clones(self, _disk, _toolchain, streamed_mock):
        def _streamed(args, error_prefix, shell=False):
            if isinstance(args, list) and args[0:2] == ["git", "clone"]:
                self.assertEqual(args[args.index("--branch") + 1], "2.1.1")
                os.makedirs(os.path.join(self.sdk_dir, ".git"), exist_ok=True)

        streamed_mock.side_effect = _streamed
        if os.path.exists(self.sdk_dir):
            import shutil

            shutil.rmtree(self.sdk_dir)

        with patch.object(self.pico, "_git_revision", return_value="deadbee"):
            with patch.object(self.pico, "_git_describe", return_value="2.1.1"):
                with patch.object(self.pico, "_toolchain_ok", return_value=True):
                    meta = self.pico.sdk_install("2.1.1")
        self.assertTrue(meta["installed"])
        self.assertEqual(meta["requested_version"], "2.1.1")
        self.assertTrue(os.path.isfile(self.meta))
        self.assertGreaterEqual(streamed_mock.call_count, 2)

    def test_status_empty_firmwares(self):
        modules = os.path.join(self.root, "modules")
        os.makedirs(os.path.join(modules, "demo"))
        with patch.object(config, "MODULES_SRC", modules):
            with patch.object(self.pico, "sdk_info", return_value={"installed": False}):
                status = self.pico.status("demo")
        self.assertTrue(status["uf2_ready"])
        self.assertEqual(status["count"], 0)

    def test_build_requires_sdk(self):
        modules = os.path.join(self.root, "modules")
        os.makedirs(os.path.join(modules, "demo", "firmwares"))
        with patch.object(config, "MODULES_SRC", modules):
            with patch.object(
                self.pico, "sdk_info", return_value={"installed": False, "toolchain_ok": True}
            ):
                with self.assertRaises(PicoError) as ctx:
                    self.pico.build_firmware("demo")
        self.assertIn("not installed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
