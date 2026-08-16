"""Field selection, renaming, and computed field projection."""
from __future__ import annotations

import re
from typing import Any


def _get_nested(record: dict, path: str) -> Any:
    """Access a nested field using dot-notation and bracket indexing.

    Args:
        record: Source record.
        path: Field path like 'user.name' or 'tags[0]'.

    Returns:
        Field value, or None if not found.
    """
    _BRACKET_RE = re.compile(r"(\w+)\[(\d+)\]")
    parts = path.split(".")
    obj: Any = record
    for part in parts:
        m = _BRACKET_RE.fullmatch(part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if not isinstance(obj, dict) or key not in obj:
                return None
            obj = obj[key]
            if not isinstance(obj, (list, tuple)) or idx >= len(obj):
                return None
            obj = obj[idx]
        else:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(part)
            if obj is None:
                return None
    return obj


def _parse_field_spec(spec: str) -> tuple[str, str, str | None]:
    """Parse a single field specification string.

    Handles:
    - ``name``                  -> (name, name, None)
    - ``full_name: name``       -> (full_name, name, None)
    - ``adult: age >= 18``      -> (adult, None, 'age >= 18')
    - ``user.name``             -> (user.name, user.name, None)

    Args:
        spec: Raw field specification string.

    Returns:
        Tuple of (output_name, source_path_or_none, expression_or_none).
    """
    spec = spec.strip()
    if ":" in spec:
        alias, rest = spec.split(":", 1)
        alias = alias.strip()
        rest = rest.strip()
        # Heuristic: if rest contains spaces or operators it's an expression
        op_chars = re.compile(r"[><=!]|\s+(AND|OR|NOT|IN|CONTAINS|EXISTS)\s+", re.I)
        if op_chars.search(rest) or " " in rest:
            return (alias, None, rest)
        else:
            return (alias, rest, None)
    return (spec, spec, None)


class Projector:
    """Projects records to a subset of fields, with optional renaming and computed fields.

    Args:
        fields: A comma-separated string or list of field specifications.

    Example::

        p = Projector(["name", "full_name: user.name", "adult: age >= 18"])
        p.project({"user": {"name": "Alice"}, "age": 20})
        # -> {"name": None, "full_name": "Alice", "adult": True}
    """

    def __init__(self, fields: str | list[str]) -> None:
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(",") if f.strip()]
        self._specs = [_parse_field_spec(f) for f in fields]
        self._engines: dict[str, Any] = {}
        self._init_engines()

    def _init_engines(self) -> None:
        """Pre-compile filter engines for computed fields."""
        from .filter_engine import FilterEngine
        for alias, source, expr in self._specs:
            if expr is not None:
                fe = FilterEngine(expr)
                fe.compile()
                self._engines[alias] = fe

    def project(self, record: dict) -> dict:
        """Project a single record according to the field specifications.

        Args:
            record: Source record dict.

        Returns:
            New dict containing only the specified fields.
        """
        result: dict = {}
        for alias, source, expr in self._specs:
            if expr is not None:
                result[alias] = self._engines[alias].evaluate(record)
            elif source is not None:
                result[alias] = _get_nested(record, source)
            else:
                result[alias] = None
        return result
