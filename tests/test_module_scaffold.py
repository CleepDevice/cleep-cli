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
