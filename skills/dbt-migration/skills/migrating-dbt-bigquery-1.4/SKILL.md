---
name: migrating-dbt-bigquery-1.4
description: Use when migrating a dbt project on the dbt-bigquery adapter from dbt 1.4 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative dbt-bigquery-adapter-specific behavior changes for a BigQuery project currently on 1.4. This is the adapter-specific companion to the core migrating-dbt-1.4 skill — run both for a full BigQuery migration.
metadata:
    fromVersion: '1.4'
    toVersion: '1.8'
---

# Migrate a dbt-bigquery project from dbt 1.4 to the latest release track

You are upgrading the **dbt-bigquery adapter** side of a dbt project that currently
targets **1.4**, on its way to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-bigquery-adapter-specific** changes. The dbt-core
changes for the same hops are covered separately by the `migrating-dbt-1.4` skill —
apply that one too for a complete migration.

A 1.4 BigQuery project crosses three boundaries (1.4→1.5, 1.5→1.6, 1.6→1.7); the
1.4→1.5 and 1.5→1.6 hops each carry a dbt-bigquery-specific change (the 1.3→1.4 job-label
change is only reached from `migrating-dbt-bigquery-1.3`). Apply every change below that
is present in the project. Make only the changes required by this upgrade — do not
refactor unrelated code.

Work through the project systematically: read `dbt_project.yml` and every incremental
model (especially ones using `insert_overwrite`), then apply the fixes.

## Changes to apply

### 1. Handle NULL partition values in dynamic `insert_overwrite` incremental models (1.4→1.5, behavior)

For an incremental model using `incremental_strategy: insert_overwrite` with a
`partition_by` and **no static `partitions` config** (the *dynamic* insert_overwrite
path), dbt-bigquery builds a query that collects the partitions to replace with
`array_agg(distinct <partition>)`. This query changed at 1.5:

- **On 1.4:** `array_agg(distinct <partition>)` — a NULL partition value is included in
  the array. Because a BigQuery array cannot contain a NULL element, this can raise
  `Array cannot have a null element` when a partition value is NULL.
- **On 1.5 and later:** `array_agg(distinct <partition> IGNORE NULLS)` — NULL partition
  values are **silently excluded** from the set of partitions to replace.

The migration hazard is a data-correctness change, not just an error going away. After
upgrading, rows whose partition expression evaluates to NULL are dropped from the
partition-replacement set, so those rows may not be written/overwritten as before — with
no error to flag it.

Find every dynamic `insert_overwrite` incremental model and check whether its
`partition_by` expression can produce NULL (e.g. `cast(created_at as date)` where
`created_at` can be NULL). If so, handle NULL explicitly rather than relying on adapter
behavior — for example coalesce the partition expression to a non-NULL sentinel:

```sql
coalesce(cast(created_at as date), date '1900-01-01') as order_date
```

or filter out NULL-partition rows in the model. Choose based on whether those rows should
be kept (coalesce to a sentinel partition) or dropped (filter). **Confirm the intended
behavior with the user** — which rows belong in which partition is a data-modeling
decision, not a mechanical one.

**Honest caveat on the runtime error.** The `Array cannot have a null element` failure is
*possible* on 1.4 but not guaranteed: it only fires if a NULL-partition row actually
reaches the partition-collection query. A model whose incremental `where` filter excludes
NULL-partition rows (e.g. `where cast(created_at as date) >= (select max(order_date) ...)`,
since `NULL >= date` is never true) never triggers it, and both 1.4 and 1.5 runs succeed —
the version difference is then visible only in the compiled SQL text
(`target/run/.../<model>.sql`), not as a runtime error. Do not promise the error will
appear. The reason to make the fix is the correctness change above (NULL partitions
silently excluded from replacement on 1.5+), which applies regardless of whether the 1.4
error ever fired.

### 2. Apply the 1.5→1.8 dbt-bigquery changes

The rest of this adapter migration continues from the 1.5→1.8 hops. Read
`../migrating-dbt-bigquery-1.5/SKILL.md` now and apply every change in its "Changes to
apply" section (the `dbt debug` expanded-connection-keys change) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it is
the single source of truth for the 1.5→1.8 dbt-bigquery hops, and it can change
independently of this skill.

## Verify

The static part of this fix is visible in the model SQL; the behavior needs a warehouse.

- **Static check (no credentials):** run **`dbt parse`** to confirm the model still parses
  after your NULL-handling edit. `dbt parse` is static and does **not** compile against or
  query BigQuery, so it confirms only that the change is syntactically valid, not that
  partitions behave as intended.
- **Behavioral confirmation (needs a live BigQuery connection):** the partition-collection
  query is only emitted when the incremental (dynamic) path actually runs. With real
  credentials, run `dbt seed --full-refresh`, then `dbt run` twice (the second run takes
  the incremental path), and confirm the model builds and the expected partitions are
  present. You can also inspect the compiled second-run SQL in
  `target/run/.../<model>.sql`. Do **not** prescribe these commands in an environment
  without credentials — they would fail to connect rather than no-op.

Do not run `dbt build`/`dbt test`/`dbt snapshot`/`dbt compile` as part of verification.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated) — the `insert_overwrite` change is **behavior**.

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
