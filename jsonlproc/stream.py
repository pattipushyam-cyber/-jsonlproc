import gzip
import heapq
import random
import sys
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import orjson
    def _loads(line: str) -> dict:
        return orjson.loads(line)
except ImportError:
    import json
    def _loads(line: str) -> dict:
        return json.loads(line)


class JsonlStream:
    """Streaming processor for JSON Lines files.

    Reads JSONL and Gzip-compressed JSONL files line by line without loading
    the entire dataset into memory. Supports stdin, malformed line handling,
    batching, and lazy pipeline chaining.

    Args:
        path: Path to the .jsonl or .jsonl.gz file, or "-" to read from stdin.

    Attributes:
        path: Resolved path or "-" for stdin.
        bad_line_count: Number of malformed lines encountered.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.bad_line_count: int = 0

    def _open(self):
        """Open the source for reading, supporting gzip if path ends in .gz.

        Returns:
            A file-like object.
        """
        if self.path == "-":
            return sys.stdin
        if self.path.endswith(".gz"):
            return gzip.open(self.path, "rt", encoding="utf-8")
        return open(self.path, "r", encoding="utf-8")

    def __iter__(self) -> Iterator[dict]:
        """Yield one record per line, streaming.

        Yields:
            Parsed dict for each valid JSON line.
        """
        fh = self._open()
        try:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield _loads(line)
                except (ValueError, KeyError) as exc:
                    self.bad_line_count += 1
                    print(f"[jsonlproc] Warning: skipping malformed line {lineno}: {exc}", file=sys.stderr)
        finally:
            if self.path != "-":
                fh.close()

    def count(self) -> int:
        """Count valid lines without loading records into memory.

        Returns:
            Number of valid JSON lines.
        """
        return sum(1 for _ in self)

    def head(self, n: int) -> list[dict]:
        """Return the first N records.

        Args:
            n: Number of records to return.

        Returns:
            List of up to n records.
        """
        result = []
        for record in self:
            result.append(record)
            if len(result) >= n:
                break
        return result

    def pipe(self, *processors: Callable[[Iterator[dict]], Iterator[dict]]) -> Iterator[dict]:
        """Chain multiple processors lazily.

        Each processor must accept an Iterator[dict] and yield dicts.

        Args:
            *processors: Callable processors to chain in order.

        Yields:
            Records after passing through all processors.
        """
        stream: Iterator[dict] = iter(self)
        for processor in processors:
            stream = processor(stream)
        yield from stream

    def sample(self, n: int) -> list[dict]:
        """Return a random reservoir sample of N records.

        Uses Vitter's reservoir sampling algorithm (O(N) time,
        O(n) memory) so the full dataset is never loaded.

        Args:
            n: Number of records to sample.

        Returns:
            List of up to n randomly sampled records.
        """
        reservoir: list[dict] = []
        for i, record in enumerate(self):
            if i < n:
                reservoir.append(record)
            else:
                j = random.randint(0, i)
                if j < n:
                    reservoir[j] = record
        return reservoir

    def batch(self, size: int) -> Iterator[list[dict]]:
        """Yield records in batches of specified size.

        Args:
            size: Maximum number of records per batch.

        Yields:
            Lists containing up to `size` records.
        """
        if size <= 0:
            raise ValueError(f"Batch size must be positive, got {size}")
        buf: list[dict] = []
        for record in self:
            buf.append(record)
            if len(buf) >= size:
                yield buf
                buf = []
        if buf:
            yield buf

