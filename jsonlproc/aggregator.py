"""Group-by aggregation for JSONL streams."""
from __future__ import annotations

import re
from typing import Any, Iterator

from .exceptions import AggregationError


_AGG_RE = re.compile(r"^(count|sum|avg|min|max|first|last)\((.+?)\)$", re.IGNORECASE)
_MISSING = object()


def _get_nested(record: dict, path: str) -> Any:
    """Access nested field by dotted path.

    Args:
        record: Source record.
        path: Dotted field path.

    Returns:
        Field value or None.
    """
    parts = path.split(".")
    obj: Any = record
    for part in parts:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part, None)
    return obj


def _parse_agg(expr: str) -> tuple[str, str | None]:
    """Parse an aggregation expression like 'sum(age)'.

    Args:
        expr: Aggregation expression string.

    Returns:
        Tuple of (function_name, field_path_or_None).

    Raises:
        AggregationError: If the expression is invalid.
    """
    expr = expr.strip()
    m = _AGG_RE.match(expr)
    if not m:
        raise AggregationError(f"Invalid aggregation expression: '{expr}'. Expected func(field).")
    func = m.group(1).lower()
    field = m.group(2).strip()
    if field == "*":
        field = None
    return func, field


class _GroupState:
    """Mutable state for one group during aggregation."""

    __slots__ = ("_funcs", "_fields", "_counts", "_sums", "_mins", "_maxs", "_firsts", "_lasts", "_avgs", "_n")

    def __init__(self, agg_specs: list[tuple[str, str, str | None]]) -> None:
        self._funcs = [(alias, func, field) for alias, func, field in agg_specs]
        self._n: int = 0
        self._counts: dict[str, int] = {alias: 0 for alias, f, _ in agg_specs}
        self._sums: dict[str, float] = {alias: 0.0 for alias, f, _ in agg_specs if f == "sum"}
        self._mins: dict[str, Any] = {alias: _MISSING for alias, f, _ in agg_specs if f == "min"}
        self._maxs: dict[str, Any] = {alias: _MISSING for alias, f, _ in agg_specs if f == "max"}
        self._firsts: dict[str, Any] = {alias: _MISSING for alias, f, _ in agg_specs if f == "first"}
        self._lasts: dict[str, Any] = {alias: _MISSING for alias, f, _ in agg_specs if f == "last"}
        self._avgs: dict[str, tuple[float, int]] = {alias: (0.0, 0) for alias, f, _ in agg_specs if f == "avg"}

    def update(self, record: dict) -> None:
        """Update state with a new record.

        Args:
            record: Incoming record dict.
        """
        self._n += 1
        for alias, func, field in self._funcs:
            val = _get_nested(record, field) if field else None
            self._counts[alias] = self._counts.get(alias, 0) + 1
            if func == "sum" and val is not None:
                self._sums[alias] = self._sums.get(alias, 0.0) + float(val)
            elif func == "avg" and val is not None:
                s, c = self._avgs.get(alias, (0.0, 0))
                self._avgs[alias] = (s + float(val), c + 1)
            elif func == "min" and val is not None:
                cur = self._mins.get(alias, _MISSING)
                if cur is _MISSING or val < cur:
                    self._mins[alias] = val
            elif func == "max" and val is not None:
                cur = self._maxs.get(alias, _MISSING)
                if cur is _MISSING or val > cur:
                    self._maxs[alias] = val
            elif func == "first" and self._firsts.get(alias) is _MISSING:
                self._firsts[alias] = val
            elif func == "last":
                self._lasts[alias] = val

    def result(self) -> dict:
        """Return the aggregated values dict.

        Returns:
            Dict mapping alias to aggregated value.
        """
        out: dict = {}
        for alias, func, field in self._funcs:
            if func == "count":
                out[alias] = self._counts.get(alias, 0)
            elif func == "sum":
                out[alias] = self._sums.get(alias, 0.0)
            elif func == "avg":
                s, c = self._avgs.get(alias, (0.0, 0))
                out[alias] = s / c if c > 0 else None
            elif func == "min":
                v = self._mins.get(alias, _MISSING)
                out[alias] = None if v is _MISSING else v
            elif func == "max":
                v = self._maxs.get(alias, _MISSING)
                out[alias] = None if v is _MISSING else v
            elif func == "first":
                v = self._firsts.get(alias, _MISSING)
                out[alias] = None if v is _MISSING else v
            elif func == "last":
                v = self._lasts.get(alias, _MISSING)
                out[alias] = None if v is _MISSING else v
        return out


class Aggregator:
    """Groups records and computes aggregations over each group.

    Works in a single streaming pass; group state is kept in memory.

    Args:
        group_by: Field name or list of field names to group on.
        aggregations: Dict mapping output alias to aggregation expression.
            Example: ``{"total": "sum(amount)", "n": "count(*)"}``

    Raises:
        AggregationError: If aggregation expressions are invalid.
    """

    def __init__(self, group_by: str | list[str], aggregations: dict[str, str]) -> None:
        if isinstance(group_by, str):
            group_by = [k.strip() for k in group_by.split(",") if k.strip()]
        self._group_by = group_by
        self._agg_specs: list[tuple[str, str, str | None]] = []
        for alias, expr in aggregations.items():
            func, field = _parse_agg(expr)
            self._agg_specs.append((alias, func, field))

    def _group_key(self, record: dict) -> tuple:
        """Build the group key tuple for a record.

        Args:
            record: Source record.

        Returns:
            Hashable tuple of group values.
        """
        return tuple(_get_nested(record, k) for k in self._group_by)

    def aggregate(self, stream: Iterator[dict]) -> Iterator[dict]:
        """Consume the stream and yield one record per group.

        Args:
            stream: Iterator of record dicts.

        Yields:
            One aggregated dict per group, including group keys and
            aggregated field values.
        """
        groups: dict[tuple, _GroupState] = {}
        key_values: dict[tuple, dict] = {}
        for record in stream:
            key = self._group_key(record)
            if key not in groups:
                groups[key] = _GroupState(self._agg_specs)
                key_values[key] = {k: v for k, v in zip(self._group_by, key)}
            groups[key].update(record)
        for key, state in groups.items():
            yield {**key_values[key], **state.result()}
