# Information Schema view columns

These are the columns of Information Schema **v1** (`target/info_schema/v1/`), captured with `describe`. Columns can be added within v1, so this list may be incomplete. To check the current set, run:

```bash
dbt show --limit -1 --inline "describe select * from {{ info_schema('<view>') }}"
```

`dbt check` only sees the parse-time subset of these columns. See [Columns available for checks](https://docs.getdbt.com/reference/info-schema#columns-available-for-checks).

## Graph

| View | Columns |
|---|---|
| `dag_nodes` | `unique_id`, `resource_type`, `ingested_at`. Enabled DAG participants only (models, tests, sources, seeds, snapshots, exposures, metrics, unit tests, analyses). |
| `edges` | `parent_unique_id`, `child_unique_id`, `ingested_at`. Also holds macro → macro edges. Tests and unit tests only ever appear as children. |
| `column_lineage` | `parent_node_unique_id`, `parent_column_name`, `child_node_unique_id`, `child_column_name`, `evolution`, `ingested_at`. Empty unless `--static-analysis strict` was used. |

## Resources

**`models`**: `unique_id`, `name`, `resource_type`, `package_name`, `original_file_path`, `fqn` (VARCHAR[]), `alias`, `description`, `node_language`, `raw_code`, `database_name`, `schema_name`, `relation_name`, `identifier`, `enabled`, `materialized`, `incremental_strategy`, `on_schema_change`, `unique_key`, `full_refresh`, `persist_docs`, `pre_hook`, `post_hook`, `grants`, `config` (double-encoded JSON), `access`, `group`, `contract_enforced`, `version`, `latest_version`, `deprecation_date`, `constraints`, `primary_key` (VARCHAR[]), `docs_show`, `properties_yml_file_path`, `time_spine`, `tags` (VARCHAR[]), `classifiers` (VARCHAR[]), `meta` (JSON), `ai_context`, `compiled_code`, `compiled_path`, `search_text`, `grain`, `grain_declared`, `grain_tested`, `grain_inferred` (all VARCHAR[]), `layer_inferred`, `ingested_at`

**`seeds`**, **`snapshots`**: the same columns as `models`.

**`sources`**: the same columns as `models`, plus `source_name`, `source_description`, `loader`, `loaded_at_field`, `loaded_at_query`, `freshness`, `external`, `source_meta`, `quoting`

**`data_tests`**: `unique_id`, `name`, `package_name`, `original_file_path`, `raw_code`, `fqn`, `description`, `database_name`, `schema_name`, `relation_name`, `enabled`, `materialized`, `config`, `tags`, `meta`, `group`, `properties_yml_file_path`, `compiled_code`, `compiled_path`, `test_name`, `test_definition_package`, `arguments`, `column_name`, `node_unique_id` (the tested model or source), `severity`, `warn_if`, `error_if`, `fail_calc`, `store_failures`, `store_failures_as`, `where`, `limit`, `ingested_at`

**`unit_tests`**: `unique_id`, `name`, `model` (the tested model's **name**, not its `unique_id`), `description`, `package_name`, `original_file_path`, `fqn`, `given`, `expect`, `overrides`, `versions`, `config`, `created_at`, `ingested_at`. There is no `enabled` column.

**`node_columns`**: `node_unique_id`, `column_name`, `column_index`, `data_type_declared`, `data_type_inferred`, `data_type_actual`, `data_type`, `description`, `label`, `expression`, `quote`, `granularity`, `tags`, `classifiers`, `meta`, `constraints`, `tests`, `comment`, `ingested_at`. The `data_type_*` columns are null after `parse`.

**`exposures`**: `unique_id`, `name`, `exposure_type`, `label`, `owner_name`, `owner_email`, `url`, `maturity`, `description`, `package_name`, `original_file_path`, `fqn`, `depends_on` (VARCHAR[]), `tags`, `meta`, `config`, `created_at`, `ingested_at`

**`metrics`**: `unique_id`, `name`, `label`, `metric_type`, `description`, `package_name`, `original_file_path`, `fqn`, `type_params`, `metric_filter`, `time_granularity`, `semantic_model_name`, `input_metric_names` (VARCHAR[]), `group`, `tags`, `meta`, `ai_context`, `config`, `created_at`, `ingested_at`

**`groups`**: `unique_id`, `name`, `description`, `package_name`, `original_file_path`, `owner_name`, `owner_email`, `config`, `ingested_at`

**`project`**: includes `project_name`, `dbt_version`, `adapter_type`, `git_sha`, `git_branch`, `git_uncommitted_changes`, `last_full_parse_at`

**`packages`**: `package_name`, `package_source`, `version`, `git_url`, `git_revision`, `local_path`, `ingested_at`

## Runtime (`dbt_rt`)

These views are not available in `dbt check`. `invocations` gets a row from every `parse`, `compile`, `run` and `build`. `run_results`, `diagnostics` and `adapter_queries` stay empty until a `run` or `build`.

**`invocations`**: `invocation_id`, `command`, `selector`, `dbt_version`, `generated_at`, `elapsed_time`, `args`, `node_count`, `target_name`, `target_type`, `target_database`, `target_schema`, `target_threads`, `vars_override`, `git_sha`, `git_branch`, `git_uncommitted_changes`. `node_count` and `target_name` can be null for `parse` and `compile` rows.

**`run_results`**: `unique_id`, `invocation_id`, `status`, `execution_time`, `thread_id`, `message`, `failures`, `compiled`, `compiled_code_hash`, `relation_name`, `adapter_response`, `timing`, `batch_results`, `rows_affected`, `created_at`

**`diagnostics`**: `unique_id`, `invocation_id`, `severity`, `code`, `message`, `detail`, `source_phase`, `created_at`
