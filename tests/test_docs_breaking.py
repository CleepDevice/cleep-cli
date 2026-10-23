#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleepcli.docs import Docs


def _arg(name, type_="str", optional=False, formats=None):
    return {
        "name": name,
        "type": type_,
        "optional": optional,
        "formats": formats or [],
    }


def _ret(type_="dict", formats=None):
    return {"type": type_, "formats": formats or []}


def test_compare_doc_args_detects_removed_parameter():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {"ping": {"args": [_arg("a")], "returns": []}}
    old_doc = {"ping": {"args": [_arg("a"), _arg("b")], "returns": []}}
    docs._Docs__compare_doc_args(new_doc, old_doc, errors, warnings)
    assert any("removed" in err for err in errors)


def test_compare_doc_args_detects_required_new_parameter():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {
        "ping": {"args": [_arg("a"), _arg("b", optional=False)], "returns": []}
    }
    old_doc = {"ping": {"args": [_arg("a")], "returns": []}}
    docs._Docs__compare_doc_args(new_doc, old_doc, errors, warnings)
    assert any("new parameter" in err for err in errors)


def test_compare_doc_args_allows_optional_new_parameter():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {
        "ping": {"args": [_arg("a"), _arg("b", optional=True)], "returns": []}
    }
    old_doc = {"ping": {"args": [_arg("a")], "returns": []}}
    docs._Docs__compare_doc_args(new_doc, old_doc, errors, warnings)
    assert errors == []


def test_compare_doc_args_detects_order_and_type_change():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {
        "ping": {
            "args": [_arg("b"), _arg("a", type_="int")],
            "returns": [],
        }
    }
    old_doc = {
        "ping": {
            "args": [_arg("a"), _arg("b")],
            "returns": [],
        }
    }
    docs._Docs__compare_doc_args(new_doc, old_doc, errors, warnings)
    assert any("order has changed" in err for err in errors)
    assert any("type is different" in warn for warn in warnings)


def test_compare_doc_returns_detects_removed_type():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {"ping": {"args": [], "returns": [_ret("dict")]}}
    old_doc = {"ping": {"args": [], "returns": [_ret("dict"), _ret("list")]}}
    docs._Docs__compare_doc_returns(new_doc, old_doc, errors, warnings)
    assert any("return type list removed" in warn for warn in warnings)


def test_compare_doc_returns_detects_format_change():
    docs = Docs()
    errors, warnings = [], []
    new_doc = {
        "ping": {"args": [], "returns": [_ret("dict", formats=["a"])]}
    }
    old_doc = {
        "ping": {"args": [], "returns": [_ret("dict", formats=["b"])]}
    }
    docs._Docs__compare_doc_returns(new_doc, old_doc, errors, warnings)
    assert any("formats updated" in warn for warn in warnings)
