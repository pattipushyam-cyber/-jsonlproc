# jsonlproc

> A streaming JSON Lines processor that **never loads the entire dataset into memory**.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Filter, project, group/aggregate, and sort `.jsonl` files with a clean CLI and a composable Python library — all in a single streaming pass.

---

## Installation

```bash
# Clone and install in editable mode
git clone https://github.com/yourname/jsonlproc.git
cd jsonlproc
pip install -e .

# Optional: faster JSON parsing with orjson
pip install -e ".[fast]"

# Development dependencies (pytest, benchmarks)
pip install -e ".[dev]"
```

---

## Quick Start — CLI

```bash
# Filter records where age >= 18
jsonlproc users.jsonl --filter "age >= 18"

# Select specific fields
jsonlproc users.jsonl --select "name, age, city"

# Combine filter + select + sort + limit
jsonlproc users.jsonl \
  --filter "status == 'active' AND age >= 18" \
  --select "name, age, city" \
  --sort "age DESC" \
  --limit 10

# Group by city and count records
jsonlproc users.jsonl \
  --group-by city \
  --agg '{"count": "count(*)", "avg_age": "avg(age)"}' \
  --sort "count DESC"

# Read from stdin, write to file
cat users.jsonl | jsonlproc - --filter "score > 100" --output filtered.jsonl

# Output as a pretty-printed JSON array
jsonlproc users.jsonl --format json --pretty

# Show processing statistics
jsonlproc users.jsonl --filter "age > 30" --stats
```

---

## CLI Reference

| Argument | Short | Description |
|---|---|---|
| `input` | — | Input `.jsonl` file, or `-` for stdin |
| `--filter EXPR` | `-f` | Filter expression |
| `--select FIELDS` | `-s` | Comma-separated field specs |
| `--group-by FIELDS` | `-g` | Comma-separated group-by field names |
| `--agg JSON` | `-a` | JSON aggregation spec |
| `--sort KEYS` | `-S` | Sort keys, optional `DESC` suffix |
| `--limit N` | `-l` | Max output records |
| `--output FILE` | `-o` | Output file (default: stdout) |
| `--format` | — | `jsonl` (default) or `json` array |
| `--pretty` | — | Pretty-print output |
| `--stats` | — | Print processing stats to stderr |

---

## Library Usage

```python
from jsonlproc import JsonlStream, FilterEngine, Projector, Aggregator, Sorter

# --- Streaming ---
stream = JsonlStream("users.jsonl")
for record in stream:
    print(record)

# --- Head / Count / Sample ---
first_5 = stream.head(5)
total   = stream.count()
sample  = stream.sample(100)  # reservoir sampling

# --- Filter ---
fe = FilterEngine("age >= 18 AND status == 'active'")
active_adults = [r for r in stream if fe.evaluate(r)]

# --- Project ---
proj = Projector(["name", "city: address.city", "adult: age >= 18"])
projected = [proj.project(r) for r in stream]

# --- Aggregate ---
agg = Aggregator(
    group_by="city",
    aggregations={"count": "count(*)", "avg_age": "avg(age)", "max_score": "max(score)"},
)
for group in agg.aggregate(iter(stream)):
    print(group)

# --- Sort ---
sorter = Sorter(sort_keys=["score"], reverse=True, limit=10)
top10 = list(sorter.sort(iter(stream)))

# --- Lazy Pipeline ---
results = stream.pipe(
    lambda s: (r for r in s if fe.evaluate(r)),
    lambda s: (proj.project(r) for r in s),
)
for record in results:
    print(record)
```

---

## Filter Expression Syntax

| Syntax | Example | Description |
|---|---|---|
| `==` `!=` | `status == 'active'` | Equality / inequality |
| `<` `<=` `>` `>=` | `age >= 18` | Numeric comparison |
| `AND` `OR` `NOT` | `age > 18 AND active == true` | Logical operators (case-insensitive) |
| `IN (...)` | `status IN ('active', 'pending')` | Membership test |
| `CONTAINS` | `name CONTAINS 'John'` | Substring or list membership |
| `EXISTS` | `EXISTS user.email` | Field presence check |
| Nested access | `user.address.city == 'NY'` | Dot-notation for nested objects |
| Array index | `tags[0] == 'admin'` | Zero-based array access |
| Parentheses | `(age > 18 OR role == 'admin') AND active` | Grouping |
| Literals | `'string'`, `42`, `3.14`, `true`, `false`, `null` | All scalar types |

---

## Field Projection Syntax (`--select`)

| Spec | Example | Output |
|---|---|---|
| Simple field | `name` | `{"name": ...}` |
| Nested field | `user.name` | `{"user.name": ...}` |
| Rename | `full_name: user.name` | `{"full_name": ...}` |
| Computed | `adult: age >= 18` | `{"adult": true/false}` |
| Array index | `first_tag: tags[0]` | `{"first_tag": ...}` |

---

## Aggregation Functions

| Function | Expression | Description |
|---|---|---|
| `count` | `count(*)` | Count all records in group |
| `sum` | `sum(field)` | Sum numeric values |
| `avg` | `avg(field)` | Average of numeric values |
| `min` | `min(field)` | Minimum value |
| `max` | `max(field)` | Maximum value |
| `first` | `first(field)` | First value seen |
| `last` | `last(field)` | Last value seen |

---

## Performance

`jsonlproc` is designed for **memory efficiency**:

- **Streaming core**: records are processed one line at a time — the full file is never held in RAM
- **Lazy pipeline**: `pipe()` chains processors using Python generators with zero intermediate buffers
- **Top-N heap sort**: when `--limit` is combined with `--sort`, uses `heapq.nsmallest`/`nlargest` to keep only N records in memory
- **Reservoir sampling**: `sample(n)` uses Vitter's algorithm — O(n) memory regardless of dataset size
- **Fast JSON**: automatically uses `orjson` when installed for up to 3× faster parsing

---

## Running Tests

```bash
pytest
pytest -v           # verbose
pytest --benchmark-only   # run benchmarks (requires pytest-benchmark)
```

---

## License

MIT © 2024 — see [LICENSE](LICENSE) for details.
