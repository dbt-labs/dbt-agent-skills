# dbt-index Command Reference

## Quick command cheat sheet

```bash
# Orient: get project summary (node counts, coverage, last run)
dbt-index status
dbt-index status --detail  # per-package breakdown

# Find: full-text search across node names, descriptions, and unique_ids
dbt-index search "revenue"
dbt-index search --type model --tag pii  # narrow by resource type and tag
dbt-index search --tag pii --columns unique_id,name,description,tags  # select specific output columns
dbt-index search --where "materialized = 'incremental'"  # SQL predicate on dbt.nodes

# Deep-dive: inspect a specific node
dbt-index describe customers                               # compact summary
dbt-index describe customers --detail                      # all sections
dbt-index describe customers --detail sql                  # compiled SQL only
dbt-index describe customers --detail columns              # column names, types, descriptions
dbt-index describe customers --detail tests                # test details
dbt-index describe customers --detail lineage              # parents/children node lists
dbt-index describe customers --detail column-lineage       # column-level lineage
dbt-index describe customers --detail catalog              # warehouse catalog metadata (requires hydrate)
dbt-index describe customers --detail sql,columns,lineage  # combine sections comma-separated
dbt-index describe customers --sql --columns --tests       # individual section flags (alternative)
dbt-index describe model.my_project.fct_orders --detail

# DAG traversal: walk the dependency graph
dbt-index lineage customers --upstream --depth 5
dbt-index lineage customers --downstream --depth 3
dbt-index lineage customers --column customer_id           # column-level lineage (Fusion only)
dbt-index lineage customers --detail                       # include name, resource_type, description per node
dbt-index lineage customers --downstream --format tree     # render as indented tree
dbt-index lineage customers --edge-type ref                # filter by edge type (ref, source, metric, macro)

# Blast radius: severity-based impact analysis with column-level support
dbt-index impact stg_customers
dbt-index impact stg_customers --detail                    # full downstream node list and test details
dbt-index impact stg_customers --column customer_id        # column-level impact (Fusion only)

# Hydrate: populate missing column data types from the warehouse
dbt-index hydrate                             # all nodes missing column data types
dbt-index hydrate customers                   # single node
dbt-index describe customers --auto-hydrate   # hydrate on demand during describe

# Warehouse queries: SQL in your profile's dialect (Snowflake, BigQuery, Redshift, Databricks, DuckDB)
# Read-only by default; use --mutate for DDL/DML.
# Supports {{ ref('model') }} and {{ source('src', 'table') }} — resolved to three-part names via the index.
# Also accepts three-part names directly, plus SHOW/DESCRIBE for schema exploration.
dbt-index warehouse run "SELECT * FROM analytics.prod.customers LIMIT 10"
dbt-index warehouse run "SELECT * FROM {{ ref('customers') }} LIMIT 10"
dbt-index warehouse run "SELECT * FROM {{ source('stripe', 'payments') }}"
dbt-index warehouse run "SHOW TABLES IN analytics.prod"
dbt-index warehouse run "DESCRIBE TABLE analytics.prod.customers"
dbt-index warehouse run "SELECT * FROM information_schema.columns WHERE table_name = 'customers'"
dbt-index warehouse run --profile my_project --target prod "SELECT count(*) FROM {{ ref('orders') }}"
dbt-index warehouse run --mutate "CREATE TABLE tmp AS SELECT 1"

# Semantic layer: discover, compile, and execute metric queries locally
dbt-index metrics list                                                    # list all metrics
dbt-index metrics list --search revenue                                   # filter by name
dbt-index metrics list --saved-queries                                    # list saved queries instead
dbt-index metrics describe revenue                                        # see queryable dimensions/entities
dbt-index metrics describe revenue --all                                  # include full metric metadata
dbt-index metrics run revenue --group-by metric_time:day                  # execute against warehouse
dbt-index metrics run revenue --group-by metric_time:day --dry-run        # preview SQL only
dbt-index metrics run --saved-query weekly_revenue_report                 # run a saved query
dbt-index metrics run revenue --group-by metric_time:day \
  --where "metric_time >= '2024-01-01'" --order-by -revenue --limit 10  # filter, sort, limit
dbt-index metrics run revenue --group-by metric_time:day \
  --time-constraint 2024-01-01 2024-01-31                                  # date range shorthand
dbt-index metrics run '{"metrics":["revenue"],"group_by":["metric_time:day"]}'  # JSON query spec

# Raw SQL against the index (DuckDB SQL): escape hatch for anything the structured commands can't answer
dbt-index metadata run "SELECT n.name, unnest(n.tags) AS tag FROM dbt.nodes n WHERE n.resource_type = 'model'"
dbt-index metadata run --attach prod=prod.duckdb "SELECT * FROM dbt.nodes d LEFT JOIN prod.dbt.nodes p USING (unique_id)"
echo "SELECT COUNT(*) FROM dbt.nodes" | dbt-index metadata run -  # stdin

# Schema discovery: list all tables in the index, then inspect columns of a specific table (use before writing queries)
dbt-index metadata list
dbt-index metadata describe dbt.nodes

# Build timing analysis
dbt-index timings                              # summary (default)
dbt-index timings slowest                      # top 20 by wall-clock time
dbt-index timings bottlenecks                  # critical path (OTel only)
dbt-index timings phases                       # parse/compile/run breakdown (OTel only)
dbt-index timings queries                      # individual SQL statements (OTel only)
dbt-index timings all                          # all sections combined
dbt-index timings node customers               # detail for a specific node
dbt-index timings export-html timeline.html    # interactive HTML waterfall

# Sync production state from dbt platform (feeds into diff)
dbt-index cloud-sync                          # auto-detects environment ID
dbt-index cloud-sync --environment-id 12345
dbt-index cloud-sync --skip-discovery         # faster: artifacts only, no Discovery API

# Compare local vs dbt platform production (auto-runs cloud-sync if needed)
dbt-index diff
dbt-index diff --sync                         # force a fresh cloud-sync first
dbt-index diff --only added
dbt-index diff --only modified --type model

# Doctor: check index integrity and completeness (errors = structural problems, warnings = incomplete enrichment)
dbt-index doctor
dbt-index doctor --name semantic_layer_summary   # run a specific check

# System: update or uninstall dbt-index itself
dbt-index system update                           # installs the latest version
dbt-index system update --version 1.0.0-beta.40   # installs a specific version
dbt-index system uninstall --yes                  # --yes required in non-TTY environments

# Re-ingest: pick up new artifacts after a dbt run (Core path only)
dbt-index ingest
dbt-index ingest --target-dir path/to/target     # custom target directory
dbt-index ingest --auto-hydrate                   # hydrate missing column types after ingest

# Export: dump tables to Parquet
dbt-index export --table dbt.nodes --table dbt.edges  # specific tables
dbt-index export -o ./parquet-out                      # custom output directory

# MCP server: expose dbt-index as MCP tools over stdio
dbt-index serve
dbt-index serve --no-cloud-sync  # skip automatic cloud sync on startup
```

## Per-command flag reference

### `search`

| Flag | Description |
|---|---|
| `--type` | Filter by resource_type (repeatable) |
| `--tag` | Filter by tag (repeatable, OR) |
| `--package` | Filter by package_name |
| `--materialized` | Filter by materialization |
| `--where` | Additional SQL WHERE predicate on dbt.nodes |
| `--columns` | Columns to include (comma-separated) |

### `describe`

| Flag | Description |
|---|---|
| `--detail [SECTIONS]` | Show detail sections. No value = all. Comma-separated: `columns,tests,sql,lineage,column-lineage,catalog` |
| `--sql` | Include compiled SQL (alternative to `--detail sql`) |
| `--columns` | Include column listing |
| `--tests` | Include tests + latest status |
| `--lineage` | Include direct parents/children |
| `--column-lineage` | Include column-level lineage |
| `--catalog` | Include physical catalog metadata |
| `--auto-hydrate` | Hydrate column schemas from warehouse before display |
| `--profile` | Profile name for hydration (default: from dbt_project.yml) |
| `--target` | Target name for hydration warehouse connection |
| `--profiles-dir` | Override profiles directory for hydration |
| `--project-dir` | Path to dbt project directory for hydration |
| `--show-all-errors` | Show all individual hydration errors instead of a summary |

### `lineage`

| Flag | Description |
|---|---|
| `--upstream` | Traverse upstream (default if neither set: both directions) |
| `--downstream` | Traverse downstream (default if neither set: both directions) |
| `--depth` | Max hops, 1-10 (default: 3) |
| `--column` | Trace a specific column (column-level lineage, Fusion only) |
| `--edge-type` | Filter: ref, source, metric, macro |
| `--detail` | Include name, resource_type, description per node |

### `impact`

| Flag | Description |
|---|---|
| `--column` | Narrow impact to a single column (Fusion only) |
| `--detail` | Show full downstream node list and test details |

### `metrics run`

| Flag | Description |
|---|---|
| `<names>` | Metric names (positional, comma-separated or space-separated) |
| `--group-by` | Group by dimensions/entities (comma-separated) |
| `--order-by` | Order by dimensions/metrics (prefix with `-` for DESC) |
| `--where` | SQL-like where filters (repeatable) |
| `--time-constraint` | Date range shorthand: `--time-constraint START END` |
| `--limit` | Limit rows returned |
| `--saved-query` | Run a saved query by name |
| `--dry-run` | Only compile to SQL, don't execute |
| `--dialect` | Target SQL dialect (default: inferred). Values: duckdb, snowflake, redshift, bigquery, databricks |
| `--profile` | Profile name (default: from dbt_project.yml) |
| `--target` | Target name for warehouse connection |
| `--profiles-dir` | Override profiles directory |
| `--project-dir` | Path to dbt project directory |

### `metrics describe`

| Flag | Description |
|---|---|
| `<names>` | Metric names (positional, comma-separated or space-separated) |
| `--all` | Include full metric metadata (type, description, label, filter, type_params, tags, package, group) |

### `metrics list`

| Flag | Description |
|---|---|
| `--search` | Filter metrics by name, label, or description |
| `--saved-queries` | List saved queries instead of metrics |

### `metadata run`

| Flag | Description |
|---|---|
| `--mutate` | Allow DDL/DML (default: read-only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN) |
| `--attach ALIAS=PATH` | Attach additional DuckDB files (repeatable) |
| `--param NAME=VALUE` | Bind named parameters ($name in SQL, repeatable) |

### `warehouse run`

| Flag | Description |
|---|---|
| `--mutate` | Allow DDL/DML (default: read-only) |
| `--profile` | Profile name (default: from dbt_project.yml) |
| `--target` | Target name |
| `--profiles-dir` | Override profiles directory |
| `--project-dir` | Path to dbt project directory |

### `hydrate`

| Flag | Description |
|---|---|
| `[NODE]` | Optional node to hydrate (omit for all nodes missing types) |
| `--profile` | Profile name (default: from dbt_project.yml) |
| `--target` | Target name for warehouse connection |
| `--profiles-dir` | Override profiles directory |
| `--project-dir` | Path to dbt project directory |
| `--show-all-errors` | Show all individual errors instead of a summary |

### `ingest`

| Flag | Description |
|---|---|
| `--target-dir` | Path to dbt target (artifact) directory (default: `target`) |
| `--index-dir` | Directory for the index output |
| `--auto-hydrate` | After ingestion, hydrate missing column schemas from the warehouse |
| `--profile` | Profile name for hydration (default: from dbt_project.yml) |
| `--target` | Target name for hydration warehouse connection |
| `--profiles-dir` | Override profiles directory for hydration |
| `--project-dir` | Path to dbt project directory for hydration |
| `--show-all-errors` | Show all individual hydration errors instead of a summary |

### `diff`

| Flag | Description |
|---|---|
| `--sync` | Force a fresh cloud-sync before diffing |
| `--environment-id` | dbt Cloud environment ID (auto-detected if omitted) |
| `--only` | Filter: added, removed, modified (repeatable) |
| `--type` | Filter by resource_type |

### `timings`

Subcommands: `summary` (default), `slowest` (longest nodes), `bottlenecks` (nodes ranked by warehouse load, OTel only), `phases` (parse/compile/run breakdown, OTel only), `queries` (individual SQL, OTel only), `all`, `node <name>`, `export-html <file>`.

### `serve`

| Flag | Description |
|---|---|
| `--profile` | Profile name for warehouse queries |
| `--target` | Target name for warehouse queries |
| `--profiles-dir` | Override profiles directory |
| `--project-dir` | Path to dbt project directory |
| `--no-cloud-sync` | Disable automatic cloud sync on startup |

## Doctor checks

Run a specific check with `dbt-index doctor --name <check>`.

| Severity | Check name | Description |
|---|---|---|
| error | `dangling_edges` | DAG edges referencing non-existent nodes |
| error | `dangling_column_lineage` | Column lineage referencing non-existent nodes |
| error | `dangling_test_metadata` | Test metadata referencing non-existent nodes |
| error | `dangling_node_columns` | Node columns referencing non-existent nodes |
| error | `dangling_semantic_entities` | Semantic entities referencing non-existent semantic models |
| error | `dangling_semantic_dimensions` | Semantic dimensions referencing non-existent semantic models |
| error | `dangling_semantic_measures` | Semantic measures referencing non-existent semantic models |
| error | `orphaned_semantic_models` | Semantic models with no matching node |
| error | `dangling_metric_semantic_model` | Metrics referencing non-existent semantic models |
| error | `dangling_input_metrics` | Derived/ratio metrics referencing non-existent input metrics |
| error | `duplicate_node_columns` | Same column defined twice on a node |
| error | `project_row_count` | No project data loaded |
| error | `dangling_run_results` | Run results referencing non-existent nodes |
| warn | `empty_grain` | Models with no grain defined |
| warn | `missing_column_lineage` | Models with no column-level lineage |
| warn | `missing_column_types` | Columns with no type information |
| warn | `model_no_columns` | Models with no column definitions |
| warn | `semantic_model_no_entities` | Semantic models with no entities |
| warn | `semantic_model_no_dimensions` | Semantic models with no dimensions |
| warn | `semantic_model_no_measures` | Semantic models with no measures |
| warn | `dimension_column_drift` | Dimension expr doesn't match any declared column |
| warn | `measure_column_drift` | Measure expr doesn't match any declared column |
| warn | `measure_missing_agg_time_dim` | Measures missing an aggregation time dimension |
| warn | `orphan_foreign_entities` | Foreign entities with no matching target |
| warn | `missing_compiled_code` | Nodes with no compiled SQL |
| info | `table_row_counts` | Row counts for all index tables |
| info | `node_summary` | Node count by resource type |
| info | `grain_coverage` | Percentage of models with grain defined |
| info | `test_coverage` | Percentage of models with tests |
| info | `semantic_layer_summary` | Semantic model/metric/saved query counts |
| info | `semantic_layer_coverage` | Semantic layer coverage statistics |

OTel-specific checks (only when OTel data is loaded):

| Severity | Check name | Description |
|---|---|---|
| warn | `otel_orphan_node_spans` | OTel spans referencing non-existent nodes |
| warn | `otel_missing_node_spans` | Nodes with no OTel execution span |
| warn | `otel_orphan_queries` | OTel queries referencing non-existent nodes |
| info | `otel_summary` | OTel ingestion statistics |

## Index schema overview

Two schemas with 34 tables and 5 analytical views. The `unique_id` column is the primary join key across most tables.

Use `dbt-index metadata list` to list all tables. Use `dbt-index metadata describe <table>` to see column details for a specific table.

### `dbt.*` — Project metadata (28 tables + 2 views)

#### Core node tables

| Table | Description | Key columns | Joins to |
|---|---|---|---|
| `nodes` | Every resource (model, source, test, seed, snapshot) | `unique_id`, `name`, `resource_type`, `package_name`, `materialized`, `compiled_code`, `grain`, `table_role`, `access_level`, `group_name`, `tags`, `description` | Primary table — others join via `unique_id` |
| `node_columns` | Column definitions per node | `unique_id`, `column_name`, `declared_type`, `inferred_type`, `catalog_type`, `description`, `tags`, `tests` | `nodes.unique_id` |
| `edges` | Node-level DAG (parent -> child) | `parent_unique_id`, `child_unique_id`, `edge_type` | `nodes.unique_id` on both columns |
| `column_lineage` | Column-level lineage | `from_node_unique_id`, `from_column_name`, `to_node_unique_id`, `to_column_name`, `lineage_kind` | `nodes.unique_id` + `node_columns.column_name` |
| `test_metadata` | Test configuration details | `unique_id`, `test_name`, `attached_node`, `column_name`, `severity`, `kwargs` | `nodes.unique_id` (for test nodes), `attached_node` -> `nodes.unique_id` |
| `node_input_files` | Files contributing to each node | `unique_id`, `file_path`, `file_hash`, `input_kind` | `nodes.unique_id` |
| `sample_data` | Sample rows per node | `unique_id`, `sample_rows` (JSON) | `nodes.unique_id` |
| `unit_tests` | Unit test definitions | `unique_id`, `name`, `model`, `given` (JSON), `expect` (JSON), `depends_on_nodes` | `model` -> `nodes.unique_id` |

#### Enriched views

| View | Description | Key columns |
|---|---|---|
| `nodes_enriched` | Nodes joined with latest run status and catalog metadata | All `nodes` columns + `last_run_status`, `last_execution_time`, `catalog_table_type`, `catalog_owner` |
| `tests_enriched` | Tests joined with metadata and latest results | `unique_id`, `test_name`, `test_type`, `attached_node`, `column_name`, `severity`, `last_run_status`, `last_run_failures`, `failure_rows` |

#### Semantic layer tables

| Table | Description | Key columns | Joins to |
|---|---|---|---|
| `semantic_models` | MetricFlow semantic model definitions | `unique_id`, `name`, `model`, `primary_entity`, `depends_on_nodes` | `model` -> `nodes.unique_id` |
| `semantic_entities` | Entities within semantic models | `unique_id`, `name`, `entity_type`, `entity_role`, `expr` | `unique_id` -> `semantic_models.unique_id` |
| `semantic_measures` | Measures within semantic models | `unique_id`, `name`, `agg`, `expr`, `agg_time_dimension` | `unique_id` -> `semantic_models.unique_id` |
| `semantic_dimensions` | Dimensions within semantic models | `unique_id`, `name`, `dimension_type`, `expr`, `time_granularity` | `unique_id` -> `semantic_models.unique_id` |
| `semantic_relationships` | Relationships between semantic models | `name`, `from_unique_id`, `to_unique_id`, `from_columns`, `to_columns`, `cardinality` | `from_unique_id`/`to_unique_id` -> `semantic_models.unique_id` |
| `metrics` | Metric definitions (simple, derived, ratio, cumulative, conversion) | `unique_id`, `name`, `metric_type`, `type_params` (JSON), `depends_on_nodes` | `depends_on_nodes` -> `nodes.unique_id` |
| `saved_queries` | Saved query definitions | `unique_id`, `name`, `query_params` (JSON), `exports` (JSON), `depends_on_nodes` | `depends_on_nodes` -> `nodes.unique_id` |
| `time_spines` | Time spine definitions | `unique_id`, `primary_column`, `primary_granularity` | `unique_id` -> `nodes.unique_id` |

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
| `node_status` | view | Lifecycle status per node (parsed -> compiled -> run) | `unique_id`, `name`, `resource_type`, `run_status`, `effective_phase`, `is_stale` | `nodes.unique_id` |

## Global flags

- `--db <path>` — index location (default: `target/index`; env: `DBT_INDEX_DB`). Only needed if using a non-default location.
- `--format compact` — default output format: YAML envelope with metadata keys + embedded TSV `data` block, token-efficient for LLMs (do not change). Other values: `json`, `csv`, `table`, `ndjson`, `tree`.
- `--raw` — only meaningful with `compact`: strips the YAML envelope, leaving just the TSV `data` block
- `--limit <n>` — max rows returned (default 100, use 0 for unlimited)
- `-v, --verbose` — print progress and diagnostic messages to stderr
- `--auto-reingest` — auto-reingest stale manifests based on fingerprinting
- `--no-send-anonymous-usage-stats` — disable anonymous usage statistics
