---
name: migrating-dbt-redshift-1.6
description: Use when migrating a dbt project that uses the dbt-redshift adapter from 1.6 to the latest release track (entry point 1.8). Covers the dbt-redshift-adapter-specific changes only (the merge_exclude_columns insert fix and the catalog-macro restructuring) — apply it alongside the core migrating-dbt-1.6 skill, which handles the dbt-core changes.
metadata:
    fromVersion: '1.6'
    toVersion: '1.8'
---

# Migrate the dbt-redshift adapter from 1.6 to the latest release track

You are upgrading the **dbt-redshift-adapter-specific** parts of a dbt project that
currently targets dbt-redshift **1.6**, on its way to **1.8** (the entry point of the
latest release track). A 1.6 project takes two hops to reach 1.8 (1.6→1.7, 1.7→1.8), and
both dbt-redshift changes land at the **1.6→1.7** hop, so they are both documented here.

This skill is **adapter-specific and complements the core `migrating-dbt-1.6` skill** —
it does not repeat the dbt-core changes. For a full migration, apply both.

Both changes below are adapter-internal — apply a change only where the project actually
exercises it (a merge-strategy incremental model, or an overridden catalog macro). Work
through `models/` and `macros/`.

## Changes to apply

### 1. `merge_exclude_columns` no longer drops excluded columns from inserts (1.6→1.7, behavior — bug fix)

In `redshift__get_merge_sql`
(`dbt/include/redshift/macros/materializations/incremental_merge.sql`), the
`WHEN NOT MATCHED ... INSERT` clause through 1.6 iterated the **exclude-filtered**
`update_columns`. So on an incremental `merge` model with `merge_exclude_columns` set, any
excluded column was wrongly dropped from the INSERT of brand-new rows — those rows landed
with the excluded column **NULL** (or produced a column-count error). At 1.7 the macro was
fixed to use a separate unfiltered `insert_columns` for the INSERT clause, while
`update_columns` still drives the UPDATE.

This is a **built-in bug fix that requires no project edit** in the common case — a model
like:

```sql
{{ config(materialized='incremental', incremental_strategy='merge',
          unique_key='order_id', merge_exclude_columns=['created_at']) }}
```

simply starts inserting the excluded column correctly on 1.7+. Two things to check:

- If the project has any **workaround** for the old bug (e.g. a post-hook backfilling the
  NULLed column, or the excluded column redundantly re-added elsewhere), that workaround
  is now unnecessary and may double-write — review and remove it.
- If the project **overrides** `redshift__get_merge_sql` (or `get_merge_sql`) in its own
  `macros/`, re-base the override on the 1.7 body so the INSERT uses the full
  `insert_columns` list; a stale override keeps the bug.

### 2. Catalog query macros restructured / split into multiple files (1.6→1.7, behavior)

Through 1.6 the catalog macros were a single file `catalog.sql` under
`dbt/include/redshift/macros/` (`redshift__get_catalog`, `redshift__get_base_catalog`,
`redshift__get_extended_catalog`, `redshift__can_select_from`,
`redshift__no_svv_table_info_warning`). At 1.7 they were split into a `catalog/`
directory:

- `by_schema.sql` — `redshift__get_catalog` + its helpers,
- `by_relation.sql` — the new `redshift__get_catalog_relations` + helpers,
- `catalog.sql` — the shared building blocks.

This is an **adapter-internal restructuring requiring no project edit** in the common
case (`dbt docs generate` continues to work unchanged). It only needs action if the
project **overrides** any of these catalog macros in its own `macros/`: the override
target may have moved files, and the new by-relation macros (`redshift__get_catalog_relations`)
did not exist pre-1.7. Find any overridden `redshift__get_*catalog*` macro and re-base it
on the 1.7 `catalog/` layout, adding a by-relation override if you override the by-schema
path and need parity.

> Boundary note (source vs Notion): the migration doc places the catalog split at 1.7→1.8.
> Adapter source shows it landed at **1.6→1.7** — the 1.7 and 1.8 `catalog/` directories
> are byte-identical (verified via `diff -rq` across the 1.7 and 1.8 wheels), while 1.6
> ships the single `catalog.sql`. It is documented here at the hop where it is crossed. A
> project starting at 1.7 would already have the split in effect (see
> `../migrating-dbt-redshift-1.7/SKILL.md`).

### 3. Apply the 1.7→1.8 redshift changes

The rest of this migration continues from the 1.7→1.8 hop. Read
`../migrating-dbt-redshift-1.7/SKILL.md` now and apply everything in its "Changes to
apply" section to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.7→1.8 redshift hop, and it can change
independently of this skill.

## Verify

Both changes are runtime/behavior concerns, not static-parse concerns, so `dbt parse`
alone will **not** exercise them. Verify at the lowest-cost level that actually observes
each:

- **`merge_exclude_columns` fix (Change 1):** confirm the installed adapter has the fix at
  the source level (no warehouse):
  ```bash
  grep -c "insert_columns" \
      "$(python -c 'import dbt.include.redshift, os; print(os.path.dirname(dbt.include.redshift.__file__))')/macros/materializations/incremental_merge.sql"
  ```
  Expect `0` pre-1.7 (bug present), `>0` on 1.7+ (fix present). The actual row-level
  behavior (a newly merged row keeping its excluded-column value instead of NULL) is
  **only observable against a live warehouse** — a full-refresh build, an incremental
  merge of a brand-new row, then reading the column back. If warehouse credentials are
  unavailable, verify at the source level and note the runtime behavior was not exercised.
  Also grep the project's `macros/` for any `get_merge_sql` override and any workaround
  post-hook.
- **Catalog split (Change 2):** confirm the installed adapter's layout at the source level
  (no warehouse):
  ```bash
  ls "$(python -c 'import dbt.include.redshift, os; print(os.path.dirname(dbt.include.redshift.__file__))')/macros/catalog"*
  ```
  On 1.7+ you get a `catalog/` directory (`by_schema.sql`, `by_relation.sql`,
  `catalog.sql`); on 1.6 a single `catalog.sql`. The catalog actually building is
  observable via `dbt docs generate` against a **live warehouse**; without credentials,
  grep the project's `macros/` for any overridden catalog macro (the real risk) and verify
  the source layout.
- Run `dbt parse` after edits to confirm the project still parses cleanly.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
(or append a "dbt-redshift adapter" section if the core skill already created one)
summarizing everything you did. For each change include:

- the file that changed (or "no file change — adapter behavior only" where applicable),
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
