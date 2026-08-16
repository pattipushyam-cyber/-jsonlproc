"""Streaming top-N sort using a min-heap."""
from __future__ import annotations

import heapq
import re
from typing import Any, Iterator


_BRACKET_RE = re.compile(r"(\w+)\[(\d+)\]")


def _get_nested(record: dict, path: str) -> Any:
    """Access a nested field by dotted path with optional bracket index.

    Args:
        record: Source record dict.
        path: Field path like 'user.name' or 'tags[0]'.

    Returns:
        Field value or None if not found.
    """
    parts = path.split(".")
    obj: Any = record
    for part in parts:
        m = _BRACKET_RE.fullmatch(part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if not isinstance(obj, dict) or key not in obj:
                return None
            obj = obj[key]
            if not isinstance(obj, list) or idx >= len(obj):
                return None
            obj = obj[idx]
        else:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(part)
    return obj


class _SortKey:
    """Wrapper that enables mixed-type comparison for heap and sort operations.

    Handles None values (sorts last) and mixed int/float/str types.

    Args:
        value: The sort key value.
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def _cmp_tuple(self) -> tuple:
        """Build a tuple that allows cross-type comparison."""
        v = self.value
        if v is None:
            return (2, 0, "")  # None sorts last
        if isinstance(v, bool):
            return (0, int(v), "")
        if isinstance(v, (int, float)):
            return (0, v, "")
        return (1, 0, str(v))

    def __lt__(self, other: "_SortKey") -> bool:
        return self._cmp_tuple() < other._cmp_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _SortKey):
            return NotImplemented
        return self._cmp_tuple() == other._cmp_tuple()

    def __le__(self, other: "_SortKey") -> bool:
        return self < other or self == other

    def __gt__(self, other: "_SortKey") -> bool:
        return not self <= other

    def __ge__(self, other: "_SortKey") -> bool:
        return not self < other


class Sorter:
    """Sorts a stream of records by one or more keys.

    When *limit* is provided, uses a heap-based top-N algorithm that
    keeps at most *limit* records in memory. Without a limit, all records
    are collected and sorted.

    Args:
        sort_keys: List of field paths to sort by.
        reverse: If True, sort in descending order.
        limit: Optional maximum number of records to return.
    """

    def __init__(
        self,
        sort_keys: list[str],
        reverse: bool = False,
        limit: int | None = None,
    ) -> None:
        self._sort_keys = sort_keys
        self._reverse = reverse
        self._limit = limit

    def _make_key(self, record: dict) -> tuple:
        """Build a comparison key tuple from a record.

        Args:
            record: Source record.

        Returns:
            Tuple of _SortKey values.
        """
        return tuple(_SortKey(_get_nested(record, k)) for k in self._sort_keys)

    def sort(self, stream: Iterator[dict]) -> Iterator[dict]:
        """Sort the stream, yielding records in order.

        Uses heapq.nlargest/nsmallest when *limit* is set (memory-efficient).
        Falls back to a full in-memory sort otherwise.

        Args:
            stream: Iterator of record dicts.

        Yields:
            Records in sorted order.
        """
        if self._limit is not None:
            yield from self._top_n(stream)
        else:
            yield from self._full_sort(stream)

    def _top_n(self, stream: Iterator[dict]) -> Iterator[dict]:
        """Memory-efficient top-N using a heap.

        Args:
            stream: Source iterator.

        Yields:
            Up to *limit* records sorted by key.
        """
        n = self._limit
        assert n is not None
        key_fn = self._make_key
        if self._reverse:
            # nlargest returns in descending order
            yield from heapq.nlargest(n, stream, key=key_fn)
        else:
            # nsmallest returns in ascending order
            yield from heapq.nsmallest(n, stream, key=key_fn)

    def _full_sort(self, stream: Iterator[dict]) -> Iterator[dict]:
        """Full in-memory sort.

        Args:
            stream: Source iterator.

        Yields:
            All records sorted by key.
        """
        records = list(stream)
        records.sort(key=self._make_key, reverse=self._reverse)
        yield from records

