"""Tests for the Projector field selection and mapping."""
from __future__ import annotations

import pytest

from jsonlproc import Projector


def test_simple_field() -> None:
    p = Projector(["name"])
    result = p.project({"name": "Alice", "age": 30})
    assert result == {"name": "Alice"}

def test_multiple_fields() -> None:
    p = Projector(["name", "age"])
    result = p.project({"name": "Alice", "age": 30, "city": "NY"})
    assert result == {"name": "Alice", "age": 30}

def test_nested_field() -> None:
    p = Projector(["user.name"])
    result = p.project({"user": {"name": "Bob", "age": 25}})
    assert result == {"user.name": "Bob"}

def test_rename_field() -> None:
    p = Projector(["full_name: name"])
    result = p.project({"name": "Alice", "age": 30})
    assert result == {"full_name": "Alice"}

def test_rename_nested() -> None:
    p = Projector(["city: address.city"])
    result = p.project({"address": {"city": "London"}})
    assert result == {"city": "London"}

def test_computed_field_comparison() -> None:
    p = Projector(["adult: age >= 18"])
    assert p.project({"age": 20})["adult"] is True
    assert p.project({"age": 15})["adult"] is False

def test_computed_field_complex() -> None:
    p = Projector(["is_active: status == 'active'"])
    assert p.project({"status": "active"})["is_active"] is True
    assert p.project({"status": "banned"})["is_active"] is False

def test_array_index_field() -> None:
    p = Projector(["first_tag: tags[0]"])
    result = p.project({"tags": ["python", "cli"]})
    assert result == {"first_tag": "python"}

def test_missing_field_returns_none() -> None:
    p = Projector(["missing"])
    result = p.project({"name": "Alice"})
    assert result == {"missing": None}

def test_comma_separated_string_input() -> None:
    p = Projector("name, age")
    result = p.project({"name": "Alice", "age": 30, "extra": True})
    assert result == {"name": "Alice", "age": 30}

def test_mixed_specs() -> None:
    p = Projector(["name", "years: age", "adult: age >= 18"])
    result = p.project({"name": "Bob", "age": 25})
    assert result["name"] == "Bob"
    assert result["years"] == 25
    assert result["adult"] is True

def test_project_preserves_types() -> None:
    p = Projector(["score", "active"])
    result = p.project({"score": 98.5, "active": True})
    assert isinstance(result["score"], float)
    assert isinstance(result["active"], bool)
