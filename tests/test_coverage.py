#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile

from cleepcli.test import coverage_report_to_dict, is_file_coverage_valid


SAMPLE_COVERAGE = """Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
/tmp/demo/backend/demo.py                  42      2    95%
/tmp/demo/backend/__init__.py               0      0   100%
-----------------------------------------------------------
TOTAL                                      42      2    95%
"""


def test_coverage_report_to_dict_parses_files_and_score():
    result = coverage_report_to_dict(SAMPLE_COVERAGE)
    assert result["score"] == 9.5
    assert len(result["files"]) == 2
    by_file = {entry["file"]: entry for entry in result["files"]}
    assert by_file["/tmp/demo/backend/demo.py"]["statements"] == 42
    assert by_file["/tmp/demo/backend/demo.py"]["coverage"] == 95


def test_is_file_coverage_valid_skips_init():
    assert is_file_coverage_valid(
        {"file": "/tmp/demo/backend/__init__.py", "statements": 0, "coverage": 100}
    )


def test_is_file_coverage_valid_rejects_fully_uncovered():
    assert not is_file_coverage_valid(
        {"file": "/tmp/demo/backend/empty.py", "statements": 0, "coverage": 100}
    )


def test_is_file_coverage_valid_rejects_too_many_pragmas():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        # 10 lines => max_pragma = 1; two pragmas must fail
        handle.write("a = 1\n" * 8)
        handle.write("b = 1  # pragma: no cover\n")
        handle.write("c = 1  # pragma: no cover\n")
        path = handle.name
    try:
        assert not is_file_coverage_valid(
            {"file": path, "statements": 10, "coverage": 80}
        )
    finally:
        os.unlink(path)


def test_is_file_coverage_valid_allows_one_pragma():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write("a = 1\n" * 10)
        handle.write("b = 1  # pragma: no cover\n")
        path = handle.name
    try:
        assert is_file_coverage_valid(
            {"file": path, "statements": 11, "coverage": 90}
        )
    finally:
        os.unlink(path)
