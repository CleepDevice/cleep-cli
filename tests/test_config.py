#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleepcli.config import get_core_version_from_sources


def test_get_core_version_from_sources(tmp_path):
    pkg = tmp_path / "cleep"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('__version__ = "0.2.0"\n')
    assert get_core_version_from_sources(str(tmp_path)) == "0.2.0"


def test_get_core_version_from_sources_missing_returns_none(tmp_path):
    assert get_core_version_from_sources(str(tmp_path)) is None
