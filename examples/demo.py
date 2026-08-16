"""Demo script showing jsonlproc library usage.

Run from the project root:
    python examples/demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jsonlproc import Aggregator, FilterEngine, JsonlStream, Projector, Sorter

SAMPLE = Path(__file__).parent / "sample.jsonl"


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def demo_streaming() -> None:
    """Show basic streaming and utility methods."""
    section("1. Streaming basics")
    stream = JsonlStream(SAMPLE)

    total = stream.count()
    print(f"Total records: {total}")

    first3 = stream.head(3)
    print(f"First 3 names: {[r['name'] for r in first3]}")

    sample5 = stream.sample(5)
    print(f"Random sample of 5: {[r['name'] for r in sample5]}")
    print(f"Bad lines encountered: {stream.bad_line_count}")


def demo_filtering() -> None:
    """Show FilterEngine with various operators."""
    section("2. Filtering")
    stream = JsonlStream(SAMPLE)

    fe = FilterEngine("age >= 18 AND status == 'active'")
    fe.compile()
    active_adults = [r for r in stream if fe.evaluate(r)]
    print(f"Active adults (age >= 18): {len(active_adults)} records")
    for r in active_adults[:3]:
        print(f"  {r['name']}, age={r['age']}, city={r['city']}")

    # EXISTS operator
    stream2 = JsonlStream(SAMPLE)
    fe2 = FilterEngine("NOT EXISTS deleted_at OR deleted_at == null")
    fe2.compile()
    not_deleted = [r for r in stream2 if fe2.evaluate(r)]
    print(f"\nNot deleted (deleted_at is null or missing): {len(not_deleted)} records")

    # CONTAINS operator on array
    stream3 = JsonlStream(SAMPLE)
    fe3 = FilterEngine("tags CONTAINS 'admin'")
    fe3.compile()
    admins = [r for r in stream3 if fe3.evaluate(r)]
    print(f"\nAdmins (tags contains 'admin'): {[r['name'] for r in admins]}")


def demo_projection() -> None:
    """Show field selection, renaming, and computed fields."""
    section("3. Projection")
    stream = JsonlStream(SAMPLE)

    proj = Projector([
        "name",
        "street: address.street",       # nested rename
        "first_tag: tags[0]",           # array index
        "adult: age >= 18",             # computed boolean
        "score",
    ])

    for record in stream.head(5):
        print(proj.project(record))


def demo_aggregation() -> None:
    """Show group-by aggregation over a full stream."""
    section("4. Aggregation (group by city)")
    stream = JsonlStream(SAMPLE)

    agg = Aggregator(
        group_by="city",
        aggregations={
            "count":     "count(*)",
            "avg_score": "avg(score)",
            "max_score": "max(score)",
            "min_age":   "min(age)",
        },
    )

    results = list(agg.aggregate(iter(stream)))
    # Sort results by city for deterministic display
    results.sort(key=lambda r: r["city"])
    for r in results:
        print(
            f"  {r['city']:15s}  count={r['count']}  "
            f"avg_score={r['avg_score']:.1f}  "
            f"max_score={r['max_score']}  "
            f"min_age={r['min_age']}"
        )


def demo_sorting() -> None:
    """Show top-N heap sort and full sort."""
    section("5. Sorting")
    stream = JsonlStream(SAMPLE)

    # Top 3 by score descending (heap-based — only 3 records in memory)
    sorter = Sorter(sort_keys=["score"], reverse=True, limit=3)
    top3 = list(sorter.sort(iter(stream)))
    print("Top 3 by score (DESC):")
    for r in top3:
        print(f"  {r['name']:10s}  score={r['score']}")

    # Sort all records by age ascending
    stream2 = JsonlStream(SAMPLE)
    sorter2 = Sorter(sort_keys=["age"])
    youngest_first = list(sorter2.sort(iter(stream2)))
    print("\nAll records by age (ASC):")
    for r in youngest_first:
        print(f"  {r['name']:10s}  age={r['age']}")


def demo_pipeline() -> None:
    """Show lazy pipe chaining."""
    section("6. Lazy pipeline (filter -> project)")
    stream = JsonlStream(SAMPLE)

    fe = FilterEngine("status == 'active' AND age >= 18")
    fe.compile()
    proj = Projector(["name", "city", "score"])

    def filter_step(s):
        for r in s:
            if fe.evaluate(r):
                yield r

    def project_step(s):
        for r in s:
            yield proj.project(r)

    results = list(stream.pipe(filter_step, project_step))
    print(f"Active adults after pipe: {len(results)} records")
    for r in results[:5]:
        print(f"  {r}")


if __name__ == "__main__":
    demo_streaming()
    demo_filtering()
    demo_projection()
    demo_aggregation()
    demo_sorting()
    demo_pipeline()
    print("\nDemo complete!")
