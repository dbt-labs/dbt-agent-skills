# Config and Materialization (`fix.by: config`)

## Incremental strategy (`materialization:incremental_strategy`)

Lake Compute builds incremental models with `append` or `insert_overwrite`.
A `merge` (or `delete+insert`) on a `unique_key` isn't supported yet.

Changing the strategy changes what the table holds. A merge updates rows in
place; an append adds new rows beside the old ones. **Don't change it without
the user.** Offer these:

1. Keep the model on Snowflake for now (drop it from the scope).
2. `insert_overwrite`. On Lake Compute it replaces the whole table with what
   the model's SQL returns on every run, as a table model does, so the
   incremental saving is gone. Only offer it when that SQL returns every row
   the table should hold. A model that reads only recent rows (an
   `is_incremental()` filter, the last N days) or builds on `{{ this }}` loses
   the rest of its history.
3. `append`, and deduplicate in the models that read it (for example,
   `qualify row_number() over (partition by <key> order by <updated_at> desc) = 1`).

## Schema changes (`on_schema_change`)

Lake Compute doesn't apply `on_schema_change` yet. An incremental model's next
run fails when its SQL returns a column the table doesn't have, whatever
`on_schema_change` says. The tool doesn't flag this. When an incremental
model moves, tell the user: after a column change, rebuild it with
`--full-refresh`, or keep it on Snowflake while its columns still change.

## Hooks (`config:pre_hook`, `config:post_hook`)

Hooks run SQL on the warehouse around the build. Find out what each one does
before suggesting anything. Grants, audits and clean-ups often matter. Offer:

- Moving it to an `on-run-end` hook in `dbt_project.yml`, which runs on
  Snowflake.
- Moving it to a model of its own that stays on Snowflake.
- Dropping it, only if the user says it isn't needed.

## Other settings (`config:grants`, `config:persist_docs`, ...)

Lake Compute doesn't apply them. Remove the setting from the model, or keep
the model on Snowflake. Ask the user which.

## Seeds (`changes[].kind: seed_catalog`)

A seed read by a model on Lake Compute has to be Iceberg: set its
`catalog_name`, or place it on lakecompute (`adapter: lakecompute` in its
config).

## A parent table that isn't Iceberg (`changes[].kind: iceberg_format`)

Add `table_format: iceberg` to the parent model's config, or switch the parent
too: put it in `--select`.
