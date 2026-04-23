# Setup: dbt Fusion Path

Use this when the project runs dbt Fusion.

## Key insight

Adding `--write-index` to a Fusion parse command automatically generates the Parquet index — there is no separate ingest step. The index is written after compilation, with ~2ms overhead.

## Creating the index

Run parse with `--write-index` and `--static-analysis strict` for the richest metadata:

```bash
dbtf parse --write-index --static-analysis strict
```

The index is written to `target/index/` by default. Query immediately:

```bash
dbt-index status --db target/index
```

Or set `DBT_USE_INDEX=1` so every Fusion command keeps the index fresh automatically:

```bash
export DBT_USE_INDEX=1
```

Specifying a different location with `--index-dir` (or `DBT_INDEX_DIR`) is rarely needed — the default works in almost all cases:

```bash
dbtf parse --write-index --static-analysis strict --index-dir /path/to/index
```

## Environment variables

| Flag | Environment variable | Description |
|---|---|---|
| `--write-index` | `DBT_USE_INDEX=1` | Write parquet index alongside JSON artifacts |
| `--index-dir` | `DBT_INDEX_DIR=/path/to/index` | Directory for index output (default: `<target>/index/`) |

## Verify

```bash
dbt-index status
```

## Keeping the index fresh

Since `--write-index` is additive to normal commands, the index stays fresh automatically as long as the flag (or `DBT_USE_INDEX=1` env var) is set. Every `dbtf build`, `dbtf run`, etc. refreshes the index.

## Differences from Core path

- No separate `dbt-index ingest` step needed — index is generated as part of the command
- Faster write path (Arrow → Parquet directly, ~2ms vs ~100ms)
- Column lineage: Fusion's compile-time static analysis populates `dbt.column_lineage` with richer data
- Static analysis provides richer type inference and lineage signals
- Everything else is identical — same commands, same schemas, same query surface
