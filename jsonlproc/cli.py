"""Command-line interface for jsonlproc."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterator

try:
    import orjson
    def _dumps(obj: dict) -> str:
        return orjson.dumps(obj).decode()
except ImportError:
    def _dumps(obj: dict) -> str:
        return json.dumps(obj, ensure_ascii=False)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    p = argparse.ArgumentParser(
        prog="jsonlproc",
        description="Streaming JSON Lines processor — filter, project, aggregate, sort.",
    )
    p.add_argument("input", help="Input .jsonl file, or '-' for stdin")
    p.add_argument("-f", "--filter", dest="filter_expr", default=None,
                   help="Filter expression (e.g. \"age >= 18 AND status == 'active'\")")
    p.add_argument("-s", "--select", dest="select", default=None,
                   help="Comma-separated field specs (e.g. 'name, age, city: user.city')")
    p.add_argument("-g", "--group-by", dest="group_by", default=None,
                   help="Comma-separated group-by fields")
    p.add_argument("-a", "--agg", dest="agg", default=None,
                   help='JSON aggregation spec (e.g. \'{"count": "count(*)"}\'')
    p.add_argument("-S", "--sort", dest="sort", default=None,
                   help="Sort key(s) with optional DESC suffix (e.g. 'count DESC, name')")
    p.add_argument("-l", "--limit", dest="limit", type=int, default=None,
                   help="Maximum number of output records")
    p.add_argument("-o", "--output", dest="output", default=None,
                   help="Output file (default: stdout)")
    p.add_argument("--format", dest="format", choices=["jsonl", "json"], default="jsonl",
                   help="Output format (jsonl or json array)")
    p.add_argument("--pretty", action="store_true",
                   help="Pretty-print JSON output")
    p.add_argument("--stats", action="store_true",
                   help="Print processing stats to stderr")
    return p


def _parse_sort_keys(sort_str: str) -> tuple[list[str], bool]:
    """Parse a sort key string like 'count DESC, name'.

    Args:
        sort_str: Comma-separated sort spec.

    Returns:
        Tuple of (key_list, reverse_flag). Reverse is True if any key has DESC.
    """
    parts = [p.strip() for p in sort_str.split(",")]
    keys = []
    reverse = False
    for part in parts:
        tokens = part.split()
        keys.append(tokens[0])
        if len(tokens) > 1 and tokens[1].upper() == "DESC":
            reverse = True
    return keys, reverse


def _write_output(
    stream: Iterator[dict],
    out_file,
    fmt: str,
    pretty: bool,
) -> int:
    """Write records to the output file.

    Args:
        stream: Iterator of output records.
        out_file: Writable file-like object.
        fmt: 'jsonl' or 'json'.
        pretty: If True, pretty-print JSON.

    Returns:
        Number of records written.
    """
    written = 0
    if fmt == "jsonl":
        for record in stream:
            if pretty:
                out_file.write(json.dumps(record, indent=2, ensure_ascii=False))
            else:
                out_file.write(_dumps(record))
            out_file.write("\n")
            written += 1
    else:
        records = list(stream)
        written = len(records)
        if pretty:
            out_file.write(json.dumps(records, indent=2, ensure_ascii=False))
        else:
            out_file.write(json.dumps(records, ensure_ascii=False))
        out_file.write("\n")
    return written


def main(argv: list[str] | None = None) -> int:
    """Entry point for the jsonlproc CLI.

    Args:
        argv: Argument list (defaults to sys.argv).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    start = time.monotonic()
    from .stream import JsonlStream
    from .filter_engine import FilterEngine
    from .projector import Projector
    from .aggregator import Aggregator
    from .sorter import Sorter
    from .exceptions import JsonlProcError

    try:
        stream = JsonlStream(args.input)
        pipeline: Iterator[dict] = iter(stream)

        records_read = 0
        records_filtered = 0

        # --- filter ---
        if args.filter_expr:
            fe = FilterEngine(args.filter_expr)
            fe.compile()

            def _filter_pipe(s: Iterator[dict]) -> Iterator[dict]:
                nonlocal records_read, records_filtered
                for rec in s:
                    records_read += 1
                    if fe.evaluate(rec):
                        records_filtered += 1
                        yield rec

            pipeline = _filter_pipe(pipeline)
        else:
            def _count_pipe(s: Iterator[dict]) -> Iterator[dict]:
                nonlocal records_read
                for rec in s:
                    records_read += 1
                    yield rec

            pipeline = _count_pipe(pipeline)

        # --- select / project ---
        if args.select:
            proj = Projector(args.select)
            pipeline = (proj.project(r) for r in pipeline)

        # --- group-by / aggregate ---
        if args.group_by and args.agg:
            agg_dict = json.loads(args.agg)
            agg = Aggregator(args.group_by, agg_dict)
            pipeline = agg.aggregate(pipeline)

        # --- sort ---
        if args.sort:
            keys, reverse = _parse_sort_keys(args.sort)
            limit = args.limit if args.limit else None
            sorter = Sorter(keys, reverse=reverse, limit=limit)
            pipeline = sorter.sort(pipeline)
        elif args.limit:
            def _limit_pipe(s: Iterator[dict]) -> Iterator[dict]:
                for i, rec in enumerate(s):
                    if i >= args.limit:
                        break
                    yield rec
            pipeline = _limit_pipe(pipeline)

        # --- output ---
        if args.output:
            out_path = Path(args.output)
            if str(out_path).endswith(".gz"):
                import gzip
                with gzip.open(out_path, "wt", encoding="utf-8") as f:
                    written = _write_output(pipeline, f, args.format, args.pretty)
            else:
                with out_path.open("w", encoding="utf-8") as f:
                    written = _write_output(pipeline, f, args.format, args.pretty)
        else:
            written = _write_output(pipeline, sys.stdout, args.format, args.pretty)

        elapsed = time.monotonic() - start
        if args.stats:
            print(
                f"[jsonlproc] stats: read={records_read} filtered={records_filtered} "
                f"written={written} bad_lines={stream.bad_line_count} "
                f"time={elapsed:.3f}s",
                file=sys.stderr,
            )
        return 0

    except JsonlProcError as exc:
        print(f"[jsonlproc] Error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"[jsonlproc] Error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[jsonlproc] Error: invalid JSON in --agg argument: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
