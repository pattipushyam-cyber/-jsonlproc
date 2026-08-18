"""Tests for the JsonlStream streaming engine."""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from jsonlproc import JsonlStream


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Helper: write records as JSONL."""
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_basic_streaming(tmp_path: Path) -> None:
    records = [{"id": i, "val": i * 2} for i in range(100)]
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, records)
    stream = JsonlStream(p)
    result = list(stream)
    assert len(result) == 100
    assert result[0] == {"id": 0, "val": 0}
    assert result[99] == {"id": 99, "val": 198}


def test_streaming_10k_records(tmp_path: Path) -> None:
    """Stream 10k records without memory blow-up."""
    p = tmp_path / "big.jsonl"
    n = 10_000
    with p.open("w") as f:
        for i in range(n):
            f.write(json.dumps({"id": i, "name": f"user_{i}", "score": i * 1.5}) + "\n")
    stream = JsonlStream(p)
    count = 0
    for _ in stream:
        count += 1
    assert count == n


def test_count(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(50)])
    assert JsonlStream(p).count() == 50


def test_head(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(20)])
    result = JsonlStream(p).head(5)
    assert len(result) == 5
    assert result[0] == {"x": 0}
    assert result[4] == {"x": 4}


def test_head_more_than_available(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(3)])
    result = JsonlStream(p).head(100)
    assert len(result) == 3


def test_malformed_json_skipped(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    with p.open("w") as f:
        f.write(json.dumps({"ok": 1}) + "\n")
        f.write("NOT JSON\n")
        f.write(json.dumps({"ok": 2}) + "\n")
        f.write("{bad\n")
        f.write(json.dumps({"ok": 3}) + "\n")
    stream = JsonlStream(p)
    result = list(stream)
    assert len(result) == 3
    assert stream.bad_line_count == 2


def test_empty_lines_skipped(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    with p.open("w") as f:
        f.write(json.dumps({"x": 1}) + "\n")
        f.write("\n")
        f.write("\n")
        f.write(json.dumps({"x": 2}) + "\n")
    result = list(JsonlStream(p))
    assert len(result) == 2


def test_pipe(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(10)])

    def only_even(stream):
        for r in stream:
            if r["x"] % 2 == 0:
                yield r

    def double_x(stream):
        for r in stream:
            yield {"x": r["x"] * 2}

    result = list(JsonlStream(p).pipe(only_even, double_x))
    assert result == [{"x": 0}, {"x": 4}, {"x": 8}, {"x": 12}, {"x": 16}]


def test_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.dumps({"a": 1}) + "\n" + json.dumps({"a": 2}) + "\n"
    monkeypatch.setattr(sys, "stdin", StringIO(data))
    result = list(JsonlStream("-"))
    assert result == [{"a": 1}, {"a": 2}]


def test_sample(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(100)])
    sample = JsonlStream(p).sample(10)
    assert len(sample) == 10
    # All sampled records are valid records
    for r in sample:
        assert "x" in r
        assert 0 <= r["x"] < 100


def test_sample_fewer_than_n(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(5)])
    sample = JsonlStream(p).sample(20)
    assert len(sample) == 5


def test_path_as_string(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": 1}])
    result = list(JsonlStream(str(p)))
    assert result == [{"x": 1}]


def test_gzip_streaming(tmp_path: Path) -> None:
    import gzip
    p = tmp_path / "data.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for i in range(25):
            f.write(json.dumps({"id": i, "val": i * 3}) + "\n")
    stream = JsonlStream(p)
    result = list(stream)
    assert len(result) == 25
    assert result[0] == {"id": 0, "val": 0}
    assert result[24] == {"id": 24, "val": 72}


def test_batching(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": i} for i in range(10)])
    stream = JsonlStream(p)
    batches = list(stream.batch(3))
    assert len(batches) == 4
    assert len(batches[0]) == 3
    assert len(batches[1]) == 3
    assert len(batches[2]) == 3
    assert len(batches[3]) == 1
    assert batches[0] == [{"x": 0}, {"x": 1}, {"x": 2}]


def test_batching_invalid_size(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    _write_jsonl(p, [{"x": 1}])
    stream = JsonlStream(p)
    with pytest.raises(ValueError):
        list(stream.batch(0))

