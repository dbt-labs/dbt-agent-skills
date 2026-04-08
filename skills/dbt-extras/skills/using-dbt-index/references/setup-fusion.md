# Setup: dbt Fusion Path

Use this when the project runs dbt Fusion.

## Key insight

Adding `--use-index` (or setting `DBT_USE_INDEX=1`) to any Fusion command automatically generates the Parquet index as part of that command — there is no separate ingest step. The index is written after compilation, with ~2ms overhead.

## Creating the index

Just add `--use-index` to your normal Fusion commands:

```bash
dbtf parse --use-index
dbtf build --use-index
dbtf run --use-index
dbtf test --use-index
```

Or set `DBT_USE_INDEX=1` once so every Fusion command keeps the index fresh automatically:

```bash
export DBT_USE_INDEX=1
```

The index is written to `target/index/` by default. Specifying a different location with `--index-dir` (or `DBT_INDEX_DIR`) is rarely needed — the default works in almost all cases:

```bash
dbtf parse --use-index --index-dir /path/to/index
```

## Environment variables

| Flag | Environment variable | Description |
|---|---|---|
| `--use-index` | `DBT_USE_INDEX=1` | Write parquet index alongside JSON artifacts |
| `--index-dir` | `DBT_INDEX_DIR=/path/to/index` | Directory for index output (default: `<target>/index/`) |

## Verify

```bash
dbt-index status
```

## Keeping the index fresh

Since `--use-index` is additive to normal commands, the index stays fresh automatically as long as the flag (or env var) is set. Every `dbtf build`, `dbtf run`, etc. refreshes the index.

## Differences from Core path

- No separate `dbt-index ingest` step needed — index is generated as part of the command
- Faster write path (Arrow → Parquet directly, ~2ms vs ~100ms)
- Column lineage: Fusion's compile-time static analysis populates `dbt.column_lineage` with richer data
- Everything else is identical — same commands, same schemas, same query surface
