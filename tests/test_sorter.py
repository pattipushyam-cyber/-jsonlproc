"""Tests for the Sorter streaming top-N sort."""
from __future__ import annotations

import pytest

from jsonlproc import Sorter


def make_records(n: int) -> list[dict]:
    return [{"id": i, "score": (n - i), "name": f"user_{i:04d}"} for i in range(n)]


def test_basic_sort_asc() -> None:
    records = [{"v": 3}, {"v": 1}, {"v": 2}]
    result = list(Sorter(["v"]).sort(iter(records)))
    assert [r["v"] for r in result] == [1, 2, 3]


def test_basic_sort_desc() -> None:
    records = [{"v": 3}, {"v": 1}, {"v": 2}]
    result = list(Sorter(["v"], reverse=True).sort(iter(records)))
    assert [r["v"] for r in result] == [3, 2, 1]


def test_top_n_limit() -> None:
    records = make_records(100)
    # Sort by score DESC, take top 5
    result = list(Sorter(["score"], reverse=True, limit=5).sort(iter(records)))
    assert len(result) == 5
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)
    assert min(scores) >= 96  # Top 5 scores from range 1..100


def test_top_n_limit_ascending() -> None:
    records = make_records(100)
    result = list(Sorter(["score"], reverse=False, limit=5).sort(iter(records)))
    assert len(result) == 5
    scores = [r["score"] for r in result]
    assert scores == sorted(scores)
    assert max(scores) <= 5


def test_sort_by_string() -> None:
    records = [{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}]
    result = list(Sorter(["name"]).sort(iter(records)))
    assert [r["name"] for r in result] == ["Alice", "Bob", "Charlie"]


def test_sort_none_last() -> None:
    records = [{"v": 3}, {"v": None}, {"v": 1}]
    result = list(Sorter(["v"]).sort(iter(records)))
    assert result[-1]["v"] is None


def test_sort_nested_key() -> None:
    records = [
        {"user": {"age": 30}},
        {"user": {"age": 20}},
        {"user": {"age": 25}},
    ]
    result = list(Sorter(["user.age"]).sort(iter(records)))
    assert [r["user"]["age"] for r in result] == [20, 25, 30]


def test_sort_limit_larger_than_dataset() -> None:
    records = [{"v": i} for i in range(5)]
    result = list(Sorter(["v"], limit=100).sort(iter(records)))
    assert len(result) == 5


def test_sort_empty_stream() -> None:
    result = list(Sorter(["v"]).sort(iter([])))
    assert result == []


def test_full_sort_1000_records() -> None:
    import random
    records = [{"v": random.randint(0, 10000)} for _ in range(1000)]
    result = list(Sorter(["v"]).sort(iter(records)))
    assert len(result) == 1000
    values = [r["v"] for r in result]
    assert values == sorted(values)
