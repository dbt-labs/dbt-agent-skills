---
name: migrating-dbt-redshift-1.5
description: Use when migrating a dbt project that uses the dbt-redshift adapter from 1.5 to the latest release track (entry point 1.8). Covers the dbt-redshift-adapter-specific changes only (the list_relations_without_caching rewrite, then the 1.6→1.8 redshift hops) — apply it alongside the core migrating-dbt-1.5 skill, which handles the dbt-core changes.
metadata:
    fromVersion: '1.5'
    toVersion: '1.8'
---

# Migrate the dbt-redshift adapter from 1.5 to the latest release track

You are upgrading the **dbt-redshift-adapter-specific** parts of a dbt project that
currently targets dbt-redshift **1.5**, on its way to **1.8** (the entry point of the
latest release track). A 1.5 project takes three hops to reach 1.8 (1.5→1.6, 1.6→1.7,
1.7→1.8), so this migration applies the redshift changes from every hop.

This skill is **adapter-specific and complements the core `migrating-dbt-1.5` skill** —
it does not repeat the dbt-core changes. For a full migration, apply both. The Python
dependency-pin bump (e.g. `dbt-redshift~=1.8.0` in `requirements.txt`) is handled by the
core skill's dependency-split step — do not duplicate it here.

Note on scope: the `sslmode` → `verify-ca` remap and autocommit-by-default (which the
migration doc labels 1.5→1.6) actually landed at **1.4→1.5** per adapter source, so a
project **starting at 1.5 already has them in effect** and does not encounter them on the
way to 1.8. They are therefore not part of this skill; if you are unsure whether your
project started before 1.5, see `../migrating-dbt-redshift-1.4/SKILL.md`. Most redshift
changes are adapter-internal behavior shifts — apply a change only where the project
actually exercises it (here: an overridden relation-listing macro).

## Changes to apply

### 1. `list_relations_without_caching` rewritten with Redshift-native SQL (1.5→1.6, behavior)

Through 1.5, the macro `redshift__list_relations_without_caching`
(`dbt/include/redshift/macros/adapters.sql`) delegated to
`postgres__list_relations_without_caching`, querying `pg_tables`/`pg_views` with **no
materialized-view detection**. At 1.6 it was rewritten as a Redshift-native query against
`information_schema.tables`/`information_schema.views`, adding `materialized_view`
detection (`view_definition ilike '%create materialized view%'`). This changes which
relation **types** dbt sees when it lists a schema — materialized views are now
recognized as their own type rather than being missed or mistyped.

This is an **adapter-internal behavior change requiring no project edit** in the common
case. It only needs action if the project **overrides** `redshift__list_relations_without_caching`
(or `postgres__list_relations_without_caching`) in its own `macros/`:

- If your override is a verbatim copy of the pre-1.6 postgres-delegating body, **delete
  it** so the project picks up the rewritten built-in with materialized-view detection.
- If your override adds custom logic, **re-base it on the 1.6 `information_schema` query**
  (including the materialized-view `case` expression) so materialized views are listed
  correctly; a stale override keeps the old `pg_tables`/`pg_views` behavior and will miss
  materialized views.

If the project does not override this macro, no edit is needed — just be aware the set of
relation types dbt discovers may change (materialized views now appear).

### 2. Apply the 1.6→1.8 redshift changes

The rest of this migration continues from the 1.6→1.8 hop. Read
`../migrating-dbt-redshift-1.6/SKILL.md` now and apply every change in its "Changes to
apply" section (the `merge_exclude_columns` insert bug fix and the catalog-macro
restructuring, then the 1.7→1.8 redshift hop it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.6→1.8 redshift hops, and it can change
independently of this skill.

## Verify

This is a runtime/behavior change, not a static-parse concern, so `dbt parse` alone will
**not** exercise it. Verify at the lowest-cost level that actually observes it:

- **Confirm whether the project overrides the macro** — grep the project's `macros/` for
  `list_relations_without_caching`. If there is no override, the built-in rewrite applies
  automatically and there is nothing to change.
- **Source-level check** (no warehouse) that the installed adapter has the rewritten
  built-in:
  ```bash
  grep -A6 "macro redshift__list_relations_without_caching" \
      "$(python -c 'import dbt.include.redshift, os; print(os.path.dirname(dbt.include.redshift.__file__))')/macros/adapters.sql"
  ```
  On 1.6+ the body is a full `information_schema` query with a materialized-view `case`;
  pre-1.6 it is a one-line delegation to `postgres__list_relations_without_caching`.
- The **actual relation-listing SQL** dbt emits is only observable via `dbt --debug run`
  against a **live warehouse** (grep the logged SQL for `information_schema`). If
  warehouse credentials are unavailable, verify at the source level and note the runtime
  behavior was not exercised.
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
