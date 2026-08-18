"""Tests for the jsonlproc CLI."""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from jsonlproc.cli import main


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def run_cli(args: list[str], capsys) -> tuple[str, str, int]:
    """Run CLI and capture stdout/stderr."""
    code = main(args)
    captured = capsys.readouterr()
    return captured.out, captured.err, code


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    p = tmp_path / "data.jsonl"
    records = [
        {"name": "Alice", "age": 30, "city": "NY", "status": "active"},
        {"name": "Bob", "age": 17, "city": "LA", "status": "active"},
        {"name": "Carol", "age": 25, "city": "NY", "status": "inactive"},
        {"name": "Dave", "age": 40, "city": "LA", "status": "active"},
        {"name": "Eve", "age": 22, "city": "NY", "status": "active"},
    ]
    _write_jsonl(p, records)
    return p


def test_basic_passthrough(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file)], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    assert len(lines) == 5
    assert code == 0


def test_filter(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--filter", "age >= 18"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    assert all(r["age"] >= 18 for r in records)
    assert len(records) == 4


def test_select(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--select", "name, age"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    assert all(set(r.keys()) == {"name", "age"} for r in records)


def test_filter_and_select(sample_file: Path, capsys) -> None:
    out, err, code = run_cli(
        [str(sample_file), "--filter", "age >= 18", "--select", "name"],
        capsys,
    )
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    assert len(records) == 4
    assert all("name" in r and "age" not in r for r in records)


def test_limit(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--limit", "2"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    assert code == 0
    assert len(lines) == 2


def test_sort_asc(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--sort", "age"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    ages = [r["age"] for r in records]
    assert ages == sorted(ages)


def test_sort_desc(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--sort", "age DESC"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    ages = [r["age"] for r in records]
    assert ages == sorted(ages, reverse=True)


def test_group_by_and_agg(sample_file: Path, capsys) -> None:
    out, err, code = run_cli(
        [str(sample_file), "--group-by", "city", "--agg", '{"n": "count(*)"}'],
        capsys,
    )
    lines = [l for l in out.strip().split("\n") if l]
    records = [json.loads(l) for l in lines]
    assert code == 0
    by_city = {r["city"]: r for r in records}
    assert by_city["NY"]["n"] == 3
    assert by_city["LA"]["n"] == 2


def test_output_json_format(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--format", "json"], capsys)
    assert code == 0
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert len(parsed) == 5


def test_output_to_file(sample_file: Path, tmp_path: Path, capsys) -> None:
    out_file = tmp_path / "out.jsonl"
    code = main([str(sample_file), "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    lines = out_file.read_text().strip().split("\n")
    assert len(lines) == 5


def test_stats_output(sample_file: Path, capsys) -> None:
    out, err, code = run_cli(
        [str(sample_file), "--filter", "age >= 18", "--stats"],
        capsys,
    )
    assert code == 0
    assert "stats:" in err
    assert "read=" in err


def test_invalid_filter_returns_error(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--filter", "age >>= 5"], capsys)
    assert code == 1
    assert "Error" in err


def test_nonexistent_file(capsys) -> None:
    out, err, code = run_cli(["nonexistent.jsonl"], capsys)
    assert code == 1
    assert "Error" in err


def test_stdin(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    data = json.dumps({"x": 1}) + "\n" + json.dumps({"x": 2}) + "\n"
    monkeypatch.setattr(sys, "stdin", StringIO(data))
    out, err, code = run_cli(["-"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    assert code == 0
    assert len(lines) == 2


def test_pretty_output(sample_file: Path, capsys) -> None:
    out, err, code = run_cli([str(sample_file), "--pretty", "--limit", "1"], capsys)
    assert code == 0
    assert "\n" in out  # pretty printed has newlines within record


def test_output_to_gzip_file(sample_file: Path, tmp_path: Path) -> None:
    import gzip
    out_file = tmp_path / "out.jsonl.gz"
    code = main([str(sample_file), "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    with gzip.open(out_file, "rt", encoding="utf-8") as f:
        lines = [l for l in f.read().strip().split("\n") if l]
    assert len(lines) == 5


def test_input_from_gzip_file(sample_file: Path, tmp_path: Path, capsys) -> None:
    import gzip
    gz_input = tmp_path / "input.jsonl.gz"
    with sample_file.open("rb") as f_in, gzip.open(gz_input, "wb") as f_out:
        f_out.writelines(f_in)
    out, err, code = run_cli([str(gz_input), "--limit", "2"], capsys)
    lines = [l for l in out.strip().split("\n") if l]
    assert code == 0
    assert len(lines) == 2

