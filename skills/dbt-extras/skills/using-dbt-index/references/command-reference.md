# dbt-index Command Reference

## Quick command cheat sheet

```bash
# Orient: get project summary (node counts, coverage, last run)
dbt-index status

# Find: full-text search across node names, descriptions, and unique_ids
dbt-index search "revenue"
dbt-index search --type model --tag pii

# Inspect: deep-dive into a specific node (columns, SQL, tests, lineage)
dbt-index describe customers --detail
dbt-index describe customers --sql --columns --tests

# DAG traversal: walk the dependency graph
dbt-index lineage customers --upstream --depth 5
dbt-index lineage customers --column customer_id

# Impact analysis before a change
dbt-index impact stg_orders
dbt-index impact stg_orders --column order_id

# Metadata: list tables, describe columns, run raw SQL on the index
dbt-index metadata list
dbt-index metadata describe dbt.nodes
dbt-index metadata run "SELECT name, materialized FROM dbt.nodes WHERE resource_type = 'model'"

# Warehouse: execute SQL against the remote warehouse
dbt-index warehouse run "SELECT * FROM orders LIMIT 10"

# Metrics: discover, describe, and execute metric queries
dbt-index metrics list
dbt-index metrics describe --metrics revenue
dbt-index metrics run --metrics revenue --group-by metric_time:day
dbt-index metrics run --metrics revenue --group-by metric_time:day --dry-run

# Diff vs production
dbt-index diff
dbt-index diff --only added --type model

# Build performance
dbt-index timings slowest
dbt-index timings export-html timeline.html

# Doctor: check index integrity and completeness
dbt-index doctor

# Re-ingest: pick up new artifacts after a dbt run (Core path only)
dbt-index ingest

# Export: dump a table to Parquet for use outside the index
dbt-index export --table dbt.nodes
```

## Index schema overview

Two schemas. The `unique_id` column is the primary join key across most tables.

Use `dbt-index metadata list` to list all tables. Use `dbt-index metadata describe <table>` to see column details.

### `dbt.*` — Project metadata (28 tables)

| Table | What it stores |
|---|---|
| `nodes` | Every resource (model, source, test, seed, snapshot) with compiled SQL, config, grain |
| `node_columns` | Column definitions with type provenance and PK/unique markers |
| `edges` | Node-level DAG (parent → child) |
| `column_lineage` | Column-level lineage mappings |
| `test_metadata` | Test definitions with unique/not_null/relationship details |
| `metrics` | MetricFlow metric definitions (simple, derived, ratio, cumulative, conversion) |
| `semantic_models` | Semantic model definitions with entities, measures, dimensions |
| `catalog_tables` | Physical warehouse table metadata |
| `exposures`, `groups`, `macros`, `docs` | Project structure |
| `project`, `packages` | Reproducibility metadata |

### `dbt_rt.*` — Runtime execution data (6 tables)

| Table | What it stores |
|---|---|
| `invocations` | One row per `dbt run/test/build` |
| `run_results` | Per-node execution: status, timing, rows affected |
| `test_failures` | Failing rows as JSON for root-cause diagnosis |
| `adapter_queries` | Actual SQL sent to the warehouse |
| `diagnostics` | Warnings and errors from dbt runs |

### Analytical views (5)

| View | What it provides |
|---|---|
| `run_results_latest` | Most recent result per node |
| `node_status` | Staleness detection |
| `dag_validity` | DAG integrity checks |
| `nodes_enriched` | Nodes joined with latest run status and catalog metadata |
| `tests_enriched` | Tests joined with metadata and latest results |

Run `dbt-index metadata list` for the full listing. Run `dbt-index metadata describe dbt.nodes` to see columns.

## Global flags

- `--db <path>` — index location (default: `target/index`; env: `DBT_INDEX_DB`). Only needed if using a non-default location.
- `--format` — output format: `compact` (default, YAML envelope with CSV data block, token-efficient for LLMs), `json`, `csv`, `table`, `ndjson`, `tree`
- `--raw` — only meaningful with `compact`: strips the YAML envelope, leaving just the CSV `data` block
- `--limit <n>` — max rows returned (default 100, use 0 for unlimited)
