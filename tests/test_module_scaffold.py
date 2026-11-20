#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleepcli.module import Module


def test_test_default_is_pytest_style():
    rendered = Module.TEST_DEFAULT % {
        "MODULE_NAME": "demo",
        "MODULE_NAME_CAPITALIZED": "Demo",
    }
    assert "import pytest" in rendered
    assert "def test_get_module_config(cleep_session):" in rendered
    assert "def test_my_function(cleep_session):" in rendered
    assert "get_log_level" in rendered
    assert "unittest.TestCase" not in rendered
    assert "hybrid" not in rendered.lower()


def test_conftest_default_exposes_cleep_session():
    assert "cleep.libs.tests.fixtures" in Module.CONFTEST_DEFAULT


def test_pytest_ini_default_sets_pythonpath():
    assert "pythonpath = ." in Module.PYTEST_INI_DEFAULT
    assert "testpaths = tests" in Module.PYTEST_INI_DEFAULT


def test_python_module_skel_accepts_module_deps():
    rendered = Module.PYTHON_MODULE_SKEL % {
        "MODULE_NAME": "demo",
        "MODULE_NAME_CAPITALIZED": "Demo",
        "BASE_CLASS": "CleepModule",
        "MODULE_TAGS": "['led']",
        "MODULE_DEPS": "['gpio', 'sensors']",
        "MODULE_DESCRIPTION": "'Short summary'",
        "MODULE_LONGDESCRIPTION": "'Longer market text'",
        "MODULE_URLSITE": "'https://example.com'",
        "MODULE_CATEGORY": "APPLICATION",
        "EXTRA_IMPORTS": "",
        "EXTRA_MEMBERS": "",
        "EXTRA_METHODS": "",
    }
    assert "MODULE_DEPS = ['gpio', 'sensors']" in rendered
    assert "MODULE_DESCRIPTION = 'Short summary'" in rendered
    assert "MODULE_LONGDESCRIPTION = 'Longer market text'" in rendered
    assert "MODULE_URLSITE = 'https://example.com'" in rendered


def test_skel_str_and_url_helpers():
    assert Module._skel_str("") == "'TODO'"
    assert Module._skel_str("Hello 'world'") == "'Hello world'"
    assert Module._skel_url("") == "None"
    assert Module._skel_url(" https://example.com ") == "'https://example.com'"


def test_firmware_manifest_skel_accepts_kind():
    rendered = Module.FIRMWARE_MANIFEST_SKEL % {
        "MODULE_NAME": "demo",
        "MODULE_NAME_CAPITALIZED": "Demo",
        "FIRMWARE_KIND": "micropython",
    }
    assert '"kind": "micropython"' in rendered


def test_firmware_main_py_skel_is_micropython():
    assert "from machine import Pin" in Module.FIRMWARE_MAIN_PY_SKEL
    assert "led.toggle()" in Module.FIRMWARE_MAIN_PY_SKEL
