"""Tests for FilterEngine expression parser and evaluator."""
from __future__ import annotations

import pytest

from jsonlproc import FilterEngine
from jsonlproc.exceptions import ParseError


def fe(expr: str) -> FilterEngine:
    engine = FilterEngine(expr)
    engine.compile()
    return engine


# --- Comparison operators ---

def test_eq_match() -> None:
    assert fe("status == 'active'").evaluate({"status": "active"})

def test_eq_no_match() -> None:
    assert not fe("status == 'active'").evaluate({"status": "inactive"})

def test_neq() -> None:
    assert fe("status != 'active'").evaluate({"status": "inactive"})

def test_lt() -> None:
    assert fe("age < 18").evaluate({"age": 17})
    assert not fe("age < 18").evaluate({"age": 18})

def test_lte() -> None:
    assert fe("age <= 18").evaluate({"age": 18})
    assert fe("age <= 18").evaluate({"age": 17})
    assert not fe("age <= 18").evaluate({"age": 19})

def test_gt() -> None:
    assert fe("age > 18").evaluate({"age": 19})

def test_gte() -> None:
    assert fe("age >= 18").evaluate({"age": 18})

# --- Logical operators ---

def test_and_both_true() -> None:
    assert fe("age >= 18 AND status == 'active'").evaluate({"age": 20, "status": "active"})

def test_and_one_false() -> None:
    assert not fe("age >= 18 AND status == 'active'").evaluate({"age": 15, "status": "active"})

def test_or_one_true() -> None:
    assert fe("age < 10 OR status == 'active'").evaluate({"age": 30, "status": "active"})

def test_or_both_false() -> None:
    assert not fe("age < 10 OR status == 'active'").evaluate({"age": 30, "status": "inactive"})

def test_not() -> None:
    assert fe("NOT status == 'active'").evaluate({"status": "inactive"})
    assert not fe("NOT status == 'active'").evaluate({"status": "active"})

def test_case_insensitive_and_or_not() -> None:
    assert fe("age > 10 and age < 100").evaluate({"age": 50})
    assert fe("age < 5 or age > 90").evaluate({"age": 95})
    assert fe("not age == 5").evaluate({"age": 10})

# --- Nested field access ---

def test_nested_field() -> None:
    assert fe("user.age >= 18").evaluate({"user": {"age": 25}})
    assert not fe("user.age >= 18").evaluate({"user": {"age": 10}})

def test_deeply_nested() -> None:
    assert fe("a.b.c == 42").evaluate({"a": {"b": {"c": 42}}})

# --- Array index access ---

def test_array_index() -> None:
    assert fe("tags[0] == 'admin'").evaluate({"tags": ["admin", "user"]})
    assert not fe("tags[0] == 'admin'").evaluate({"tags": ["user", "admin"]})

def test_array_out_of_bounds() -> None:
    # Should not raise, just return None/falsy
    assert not fe("tags[5] == 'admin'").evaluate({"tags": ["a", "b"]})

# --- IN operator ---

def test_in_operator() -> None:
    assert fe("status IN ('active', 'pending')").evaluate({"status": "active"})
    assert fe("status IN ('active', 'pending')").evaluate({"status": "pending"})
    assert not fe("status IN ('active', 'pending')").evaluate({"status": "deleted"})

def test_in_numbers() -> None:
    assert fe("code IN (1, 2, 3)").evaluate({"code": 2})
    assert not fe("code IN (1, 2, 3)").evaluate({"code": 5})

# --- CONTAINS operator ---

def test_contains_string() -> None:
    assert fe("name CONTAINS 'test'").evaluate({"name": "test_user"})
    assert not fe("name CONTAINS 'test'").evaluate({"name": "admin"})

def test_contains_list() -> None:
    assert fe("roles CONTAINS 'admin'").evaluate({"roles": ["user", "admin"]})

# --- EXISTS operator ---

def test_exists_present() -> None:
    assert fe("EXISTS email").evaluate({"email": "a@b.com"})

def test_exists_missing() -> None:
    assert not fe("EXISTS email").evaluate({"name": "Alice"})

def test_exists_nested() -> None:
    assert fe("EXISTS user.email").evaluate({"user": {"email": "x@y.com"}})
    assert not fe("EXISTS user.email").evaluate({"user": {"name": "Alice"}})

def test_not_exists() -> None:
    assert fe("NOT EXISTS deleted_at").evaluate({"name": "Alice"})

# --- Literals ---

def test_null_literal() -> None:
    assert fe("deleted == null").evaluate({"deleted": None})
    assert not fe("deleted == null").evaluate({"deleted": "something"})

def test_bool_literal_true() -> None:
    assert fe("active == true").evaluate({"active": True})

def test_bool_literal_false() -> None:
    assert fe("active == false").evaluate({"active": False})

# --- Parentheses ---

def test_parentheses() -> None:
    expr = "(age >= 18 AND status == 'active') OR role == 'admin'"
    assert fe(expr).evaluate({"age": 15, "status": "inactive", "role": "admin"})
    assert not fe(expr).evaluate({"age": 15, "status": "inactive", "role": "user"})
    assert fe(expr).evaluate({"age": 25, "status": "active", "role": "user"})

# --- Error handling ---

def test_invalid_expression_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        FilterEngine("age >>= 5").compile()

def test_lazy_compile_on_evaluate() -> None:
    """compile() is called automatically on first evaluate()."""
    engine = FilterEngine("age > 10")
    assert engine.evaluate({"age": 20})

# --- Missing field graceful handling ---

def test_missing_field_returns_false_for_comparison() -> None:
    assert not fe("missing_field == 'value'").evaluate({"other": "thing"})

def test_double_quoted_string() -> None:
    assert fe('name == "Alice"').evaluate({"name": "Alice"})
