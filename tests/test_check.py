#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from unittest.mock import patch

import pytest

from cleepcli.check import Check
from cleepcli import config


@pytest.fixture
def check():
    with patch("cleepcli.check.Tools.get_cleep_url", return_value="https://127.0.0.1"):
        return Check()


def test_check_constant_missing(check):
    msg = check._Check__check_constant(
        {"name": "MODULE_NAME", "type": str, "value": None}
    )
    assert "missing" in msg


def test_check_constant_wrong_type(check):
    msg = check._Check__check_constant(
        {"name": "MODULE_VERSION", "type": str, "value": 1}
    )
    assert "wrong type" in msg


def test_check_constant_empty_string(check):
    msg = check._Check__check_constant(
        {"name": "MODULE_NAME", "type": str, "value": ""}
    )
    assert "empty" in msg


def test_check_constant_validator(check):
    msg = check._Check__check_constant(
        {
            "name": "MODULE_CATEGORY",
            "type": str,
            "value": "bad",
            "validator": lambda v: v == "APPLICATION",
            "message": "invalid category",
        }
    )
    assert msg == "invalid category"


def test_check_constant_ok(check):
    assert (
        check._Check__check_constant(
            {"name": "MODULE_NAME", "type": str, "value": "demo"}
        )
        is None
    )


def test_check_desc_json_valid(check, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(
        json.dumps(
            {
                "icon": "cog",
                "global": {"js": [], "html": [], "css": []},
                "config": {"js": ["a.js"], "html": ["a.html"]},
            }
        )
    )
    result = check._Check__check_desc_json({"fullpath": str(path)})
    assert result["errors"] == []
    assert result["content"]["icon"] == "cog"


def test_check_desc_json_missing_keys(check, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({"icon": "cog"}))
    result = check._Check__check_desc_json({"fullpath": str(path)})
    assert any("mandatory key" in err for err in result["errors"])


def test_check_desc_json_invalid_json(check, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text("{not json")
    result = check._Check__check_desc_json({"fullpath": str(path)})
    assert any("Error loading" in err for err in result["errors"])


def test_check_desc_json_invalid_section_types(check, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(
        json.dumps(
            {
                "icon": "cog",
                "global": {"js": "not-a-list"},
                "config": {"html": "nope"},
                "res": "bad",
            }
        )
    )
    result = check._Check__check_desc_json({"fullpath": str(path)})
    assert any("global.js" in err for err in result["errors"])
    assert any("config.html" in err for err in result["errors"])
    assert any("res section" in err for err in result["errors"])


def test_check_module_tree_lists_files_and_skips_gitkeep(check, tmp_path):
    module = "demo"
    src = tmp_path / "modules" / module / "bin"
    src.mkdir(parents=True)
    (src / "tool").write_text("#!/bin/sh\n")
    (src / ".gitkeep").write_text("")
    dst = tmp_path / "opt" / module
    dst.mkdir(parents=True)

    with patch.object(config, "MODULES_SRC", str(tmp_path / "modules")), patch.object(
        config, "MODULES_DST", str(tmp_path / "opt")
    ):
        result = check._check_module_tree(module, "bin")

    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "tool"
    assert result["errors"] == []


def test_check_module_tree_missing_module_raises(check):
    with patch.object(config, "MODULES_DST", "/tmp/cleep-cli-missing-dst"):
        with pytest.raises(Exception, match="does not exist"):
            check._check_module_tree("nope", "bin")
