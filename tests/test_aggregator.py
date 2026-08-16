"""Tests for the Aggregator group-by and aggregation logic."""
from __future__ import annotations

import pytest

from jsonlproc import Aggregator
from jsonlproc.exceptions import AggregationError


def records(*dicts):
    return iter(dicts)


def agg_list(group_by, aggs, data):
    a = Aggregator(group_by, aggs)
    return list(a.aggregate(iter(data)))


# --- count ---

def test_count_all() -> None:
    data = [{"city": "NY", "age": 25}, {"city": "NY", "age": 30}, {"city": "LA", "age": 22}]
    results = agg_list("city", {"n": "count(*)"}, data)
    by_city = {r["city"]: r for r in results}
    assert by_city["NY"]["n"] == 2
    assert by_city["LA"]["n"] == 1


# --- sum ---

def test_sum() -> None:
    data = [{"city": "NY", "amount": 100}, {"city": "NY", "amount": 200}, {"city": "LA", "amount": 50}]
    results = agg_list("city", {"total": "sum(amount)"}, data)
    by_city = {r["city"]: r for r in results}
    assert by_city["NY"]["total"] == 300.0
    assert by_city["LA"]["total"] == 50.0


# --- avg ---

def test_avg() -> None:
    data = [{"g": "A", "v": 10}, {"g": "A", "v": 20}, {"g": "B", "v": 5}]
    results = agg_list("g", {"avg_v": "avg(v)"}, data)
    by_g = {r["g"]: r for r in results}
    assert by_g["A"]["avg_v"] == 15.0
    assert by_g["B"]["avg_v"] == 5.0


# --- min / max ---

def test_min() -> None:
    data = [{"g": "X", "v": 10}, {"g": "X", "v": 3}, {"g": "X", "v": 7}]
    results = agg_list("g", {"min_v": "min(v)"}, data)
    assert results[0]["min_v"] == 3


def test_max() -> None:
    data = [{"g": "X", "v": 10}, {"g": "X", "v": 3}, {"g": "X", "v": 7}]
    results = agg_list("g", {"max_v": "max(v)"}, data)
    assert results[0]["max_v"] == 10


# --- first / last ---

def test_first_last() -> None:
    data = [{"g": "A", "v": 1}, {"g": "A", "v": 2}, {"g": "A", "v": 3}]
    results = agg_list("g", {"first_v": "first(v)", "last_v": "last(v)"}, data)
    assert results[0]["first_v"] == 1
    assert results[0]["last_v"] == 3


# --- multiple group keys ---

def test_multiple_group_keys() -> None:
    data = [
        {"country": "US", "city": "NY", "v": 10},
        {"country": "US", "city": "NY", "v": 20},
        {"country": "US", "city": "LA", "v": 5},
        {"country": "UK", "city": "LN", "v": 100},
    ]
    results = agg_list(["country", "city"], {"total": "sum(v)", "n": "count(*)"}, data)
    by_key = {(r["country"], r["city"]): r for r in results}
    assert by_key[("US", "NY")]["total"] == 30.0
    assert by_key[("US", "NY")]["n"] == 2
    assert by_key[("US", "LA")]["total"] == 5.0
    assert by_key[("UK", "LN")]["n"] == 1


# --- multiple agg functions in one call ---

def test_multiple_agg_functions() -> None:
    data = [{"g": "A", "v": i} for i in range(1, 6)]
    results = agg_list("g", {
        "n": "count(*)",
        "total": "sum(v)",
        "avg_v": "avg(v)",
        "min_v": "min(v)",
        "max_v": "max(v)",
    }, data)
    r = results[0]
    assert r["n"] == 5
    assert r["total"] == 15.0
    assert r["avg_v"] == 3.0
    assert r["min_v"] == 1
    assert r["max_v"] == 5


# --- streaming (single pass) ---

def test_streaming_single_pass() -> None:
    """Aggregator must work with a one-shot iterator."""
    def gen():
        for i in range(100):
            yield {"g": str(i % 5), "v": i}
    a = Aggregator("g", {"n": "count(*)", "total": "sum(v)"})
    results = list(a.aggregate(gen()))
    assert len(results) == 5


# --- error handling ---

def test_invalid_agg_expr() -> None:
    with pytest.raises(AggregationError):
        Aggregator("g", {"bad": "unknown(field)"})


def test_invalid_agg_format() -> None:
    with pytest.raises(AggregationError):
        Aggregator("g", {"bad": "just_a_field"})
