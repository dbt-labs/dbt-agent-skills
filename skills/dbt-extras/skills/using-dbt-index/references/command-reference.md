# dbt-index Command Reference

## Quick command cheat sheet

```bash
# Orient: get project summary (node counts, coverage, last run)
dbt-index status
dbt-index status --detail  # per-package breakdown

# Find: full-text search across node names, descriptions, and unique_ids
dbt-index search "revenue"
dbt-index search --type model --tag pii  # narrow by resource type and tag
dbt-index search --tag pii --columns unique_id,name,description,tags  # select specific output columns (see `dbt-index schema dbt.nodes` for options)

# Deep-dive: inspect a specific node (columns, SQL, tests, lineage)
dbt-index node customers --detail
dbt-index node model.my_project.fct_orders --sql --columns

# DAG traversal: walk the dependency graph up to 5 layers upstream of `customers`
dbt-index lineage customers --upstream --depth 5
dbt-index lineage customers --column customer_id  # column-level lineage

# Blast radius: list all nodes downstream of `stg_customers` (change impact)
dbt-index impact stg_customers --depth 5

# Raw SQL: escape hatch for anything the structured commands can't answer
dbt-index query "SELECT n.name, unnest(n.tags) AS tag FROM dbt.nodes n WHERE n.resource_type = 'model'"

# Schema discovery: list all tables in the index, then inspect columns of a specific table (use before writing queries)
dbt-index schema
dbt-index schema dbt.nodes

# Compare environments: show nodes added in dev vs prod
dbt-index diff --base prod.duckdb --only added

# Doctor: check index integrity and completeness (errors = structural problems, warnings = incomplete enrichment)
dbt-index doctor

# Re-ingest: pick up new artifacts after a dbt run (Core path only)
dbt-index ingest

# Export: dump a table to Parquet for use outside the index
dbt-index export --table dbt.nodes
```

## Index schema overview

Two schemas with 39 tables/views total. The `unique_id` column is the primary join key across most tables.

Use `dbt-index schema` to list all tables. Use `dbt-index schema <table>` to see column details for a specific table.

### `dbt.*` — Project metadata (30 tables + 2 views)

#### Core node tables

| Table | Description | Key columns | Joins to |
|---|---|---|---|
| `nodes` | Every resource (model, source, test, seed, snapshot) | `unique_id`, `name`, `resource_type`, `package_name`, `materialized`, `compiled_code`, `grain`, `table_role`, `access_level`, `group_name`, `tags`, `description` | Primary table — others join via `unique_id` |
| `node_columns` | Column definitions per node | `unique_id`, `column_name`, `declared_type`, `inferred_type`, `catalog_type`, `description`, `tags`, `tests` | `nodes.unique_id` |
| `edges` | Node-level DAG (parent → child) | `parent_unique_id`, `child_unique_id`, `edge_type` | `nodes.unique_id` on both columns |
| `column_lineage` | Column-level lineage | `from_node_unique_id`, `from_column_name`, `to_node_unique_id`, `to_column_name`, `lineage_kind` | `nodes.unique_id` + `node_columns.column_name` |
| `test_metadata` | Test configuration details | `unique_id`, `test_name`, `attached_node`, `column_name`, `severity`, `kwargs` | `nodes.unique_id` (for test nodes), `attached_node` → `nodes.unique_id` |
| `node_input_files` | Files contributing to each node | `unique_id`, `file_path`, `file_hash`, `input_kind` | `nodes.unique_id` |
| `sample_data` | Sample rows per node | `unique_id`, `sample_rows` (JSON) | `nodes.unique_id` |
| `unit_tests` | Unit test definitions | `unique_id`, `name`, `model`, `given` (JSON), `expect` (JSON), `depends_on_nodes` | `model` → `nodes.unique_id` |

#### Enriched views

| View | Description | Key columns |
|---|---|---|
| `nodes_enriched` | Nodes joined with latest run status and catalog metadata | All `nodes` columns + `last_run_status`, `last_execution_time`, `catalog_table_type`, `catalog_owner` |
| `tests_enriched` | Tests joined with metadata and latest results | `unique_id`, `test_name`, `test_type`, `attached_node`, `column_name`, `severity`, `last_run_status`, `last_run_failures`, `failure_rows` |

#### Semantic layer tables

| Table | Description | Key columns | Joins to |
|---|---|---|---|
| `semantic_models` | MetricFlow semantic model definitions | `unique_id`, `name`, `model`, `primary_entity`, `depends_on_nodes` | `model` → `nodes.unique_id` |
| `semantic_entities` | Entities within semantic models | `unique_id`, `name`, `entity_type`, `entity_role`, `expr` | `unique_id` → `semantic_models.unique_id` |
| `semantic_measures` | Measures within semantic models | `unique_id`, `name`, `agg`, `expr`, `agg_time_dimension` | `unique_id` → `semantic_models.unique_id` |
| `semantic_dimensions` | Dimensions within semantic models | `unique_id`, `name`, `dimension_type`, `expr`, `time_granularity` | `unique_id` → `semantic_models.unique_id` |
| `semantic_relationships` | Relationships between semantic models | `name`, `from_unique_id`, `to_unique_id`, `from_columns`, `to_columns`, `cardinality` | `from_unique_id`/`to_unique_id` → `semantic_models.unique_id` |
| `metrics` | Metric definitions | `unique_id`, `name`, `metric_type`, `type_params` (JSON), `depends_on_nodes` | `depends_on_nodes` → `nodes.unique_id` |
| `saved_queries` | Saved query definitions | `unique_id`, `name`, `query_params` (JSON), `exports` (JSON), `depends_on_nodes` | `depends_on_nodes` → `nodes.unique_id` |
| `time_spines` | Time spine definitions | `unique_id`, `primary_column`, `primary_granularity` | `unique_id` → `nodes.unique_id` |

#### Catalog tables

| Table | Description | Key columns | Joins to |
|---|---|---|---|
| `catalog_tables` | Physical warehouse table metadata | `unique_id`, `table_type`, `database_name`, `schema_name`, `table_name`, `table_owner` | `nodes.unique_id` |
| `catalog_stats` | Table-level statistics | `unique_id`, `stat_id`, `stat_label`, `stat_value` | `nodes.unique_id` |
| `column_stats` | Column-level profiling statistics | `unique_id`, `column_name`, `row_count`, `distinct_count`, `null_pct`, `min_value`, `max_value` | `nodes.unique_id` + `node_columns.column_name` |

#### Project metadata tables

| Table | Description | Key columns |
|---|---|---|
| `project` | Project-level info | `project_name`, `dbt_version`, `adapter_type`, `git_sha`, `git_branch` |
| `packages` | Installed packages | `package_name`, `package_source`, `version`, `git_url` |
| `project_vars` | dbt_project.yml variables | `var_name`, `var_value` (JSON) |
| `project_env_vars` | Environment variables referenced | `env_var_name`, `used_in` |
| `docs` | Doc block definitions | `unique_id`, `name`, `block_contents` |
| `groups` | Access groups | `unique_id`, `name`, `owner_name`, `owner_email` |
| `macros` | Macro definitions | `unique_id`, `name`, `macro_sql`, `depends_on_macros` |
| `exposures` | Exposure definitions | `unique_id`, `name`, `exposure_type`, `owner_name`, `depends_on_nodes` |
| `source_freshness` | Source freshness results | `unique_id`, `status`, `max_loaded_at`, `snapshotted_at` |

### `dbt_rt.*` — Runtime data (6 tables + 3 views)

| Table/View | Type | Description | Key columns | Joins to |
|---|---|---|---|---|
| `invocations` | table | One row per dbt run/test/build | `invocation_id`, `command`, `dbt_version`, `generated_at`, `elapsed_time`, `args` (JSON) | Primary key: `invocation_id` |
| `invocation_nodes` | table | Which nodes were part of each invocation | `invocation_id`, `unique_id` | `invocations.invocation_id` + `nodes.unique_id` |
| `run_results` | table | Per-node execution results | `unique_id`, `invocation_id`, `status`, `execution_time`, `message`, `failures` | `nodes.unique_id` + `invocations.invocation_id` |
| `test_failures` | table | Failing test rows as JSON | `unique_id`, `invocation_id`, `failure_rows` (JSON) | `nodes.unique_id` + `invocations.invocation_id` |
| `adapter_queries` | table | Actual SQL sent to warehouse | `unique_id`, `invocation_id`, `query_sql`, `rows_affected`, `bytes_scanned` | `nodes.unique_id` + `invocations.invocation_id` |
| `diagnostics` | table | Warnings and errors from dbt | `unique_id`, `invocation_id`, `severity`, `code`, `message` | `nodes.unique_id` + `invocations.invocation_id` |
| `run_results_latest` | view | Latest execution result per node | Same as `run_results` | `nodes.unique_id` |
| `dag_validity` | view | Whether parents were built before children | `unique_id`, `status`, `parent_unique_id`, `parent_is_fresh` | `nodes.unique_id` |
| `node_status` | view | Lifecycle status per node (parsed → compiled → run) | `unique_id`, `name`, `resource_type`, `run_status`, `effective_phase`, `is_stale` | `nodes.unique_id` |

## Global flags

- `--db <path>` — index location (default: `target/index`; env: `DBT_INDEX_DB`). Only needed if using a non-default location.
- `--format compact` — default output format: YAML envelope with metadata keys + embedded CSV `data` block, token-efficient for LLMs (do not change)
- `--raw` — only meaningful with `compact`: strips the YAML envelope, leaving just the CSV `data` block
- `--limit <n>` — max rows returned (default 100, use 0 for unlimited)
