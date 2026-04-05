# Setup: dbt Fusion Path

Use this when the project runs dbt Fusion.

## Key insight

Adding `--use-index` to any Fusion command automatically generates the Parquet index as part of that command — there is no separate ingest step. The index is written during the parse phase with ~2ms overhead.

## Creating the index

Just add `--use-index` to your normal Fusion commands:

```bash
dbtf parse --use-index
dbtf build --use-index
dbtf run --use-index
dbtf test --use-index
```

The index is written to `target/index/` by default. Use `--index-dir` to specify a different location:

```bash
dbtf parse --use-index --index-dir /path/to/index
```

## Environment variables

Instead of passing flags every time, set environment variables:

| Flag | Environment variable | Description |
|---|---|---|
| `--use-index` | `DBT_USE_INDEX=1` | Write parquet index alongside JSON artifacts |
| `--index-dir` | `DBT_INDEX_DIR=/path/to/index` | Directory for index output (default: `<target>/index/`) |

With these set, every Fusion command automatically keeps the index up-to-date with no extra flags.

## Verify

```bash
dbt-index status -d target/index
```

## Keeping the index fresh

Since `--use-index` is additive to normal commands, the index stays fresh automatically as long as the flag (or env var) is set. Every `dbtf build`, `dbtf run`, etc. regenerates the index as part of the parse phase.

## Differences from Core path

- No separate `dbt-index ingest` step needed — index is generated as part of the command
- Faster write path (Arrow → Parquet directly, ~2ms vs ~100ms)
- Column lineage: Fusion's compile-time static analysis populates `dbt.column_lineage` with richer data
- Everything else is identical — same commands, same schemas, same query surface
