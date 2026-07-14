---
name: migrating-dbt-1.7
description: Upgrade a dbt project from dbt-core 1.7 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.7.
metadata:
    fromVersion: '1.7'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.7 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.7** to **1.8**
(the entry point of the latest release track). Apply every change below that is
present in the project, then verify the project parses under 1.8. Make only the
changes required by this upgrade — do not refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Rename `tests:` → `data_tests:` (deprecation)

The `tests` key is deprecated in 1.8 in favor of `data_tests`. Rename it
everywhere it appears:

- The top-level `tests:` block in `dbt_project.yml`.
- Every `tests:` block in schema YAML (`models/**/*.yml`), both at the model
  level and under individual columns.
  Rename the key only; leave the test list contents unchanged.

### 2. Built-in materialization overrides now require an explicit opt-in (breaking + deprecation)

In 1.8, `require_explicit_package_overrides_for_builtin_materializations`
defaults to `True`, and overriding a built-in materialization emits a
deprecation warning. Find any macro that redefines a built-in materialization
(e.g. `{% materialization view, default %}`, `table`, `incremental`,
`seed`, `snapshot`).

- **Preferred fix:** if the override is a verbatim copy of the built-in (adds
  nothing), delete the macro file so the built-in is used.
- **Otherwise:** keep the override but add to `dbt_project.yml`:
    ```yaml
    flags:
        require_explicit_package_overrides_for_builtin_materializations: false
    ```

### 3. Remove spaces from resource names (deprecation)

Spaces in resource names raise `SpacesInResourceNameDeprecation` in 1.8. Find
resources (sources, models, seeds, etc.) whose `name:` contains a space — e.g.
a source `name: raw events` — rename it (e.g. `raw_events`) and update every
reference, including `source('raw events', ...)` / `ref('...')` calls.

This is a judgment-heavy change. Before renaming, **ask the user to confirm**
when a rename could collide with an existing name, cross a package / dbt Mesh
boundary, or change a relation name (`alias`/`identifier`). **Explicitly flag
any references you cannot see or fix** — e.g. `--select` in scheduled jobs,
`selectors.yml`, or BI tools — so the user can update them.

### 4. Declare each `primary_key` constraint in exactly one place (behavior → parse error)

In 1.8, declaring a `primary_key` constraint both at the model level
(`constraints:`) and at the column level (`columns: <col>: constraints:`)
throws a `ParsingError` at parse time. For any model that does this, keep the
`primary_key` in exactly one location and remove the duplicate.

### 5. Update dependency pins for the dbt-core / dbt-adapters split (behavior)

In 1.8, dbt-core was split into `dbt-core`, `dbt-common`, and `dbt-adapters`,
and adapters are decoupled from a fixed core version.

- In `requirements.txt` (or equivalent), bump the adapter pin to its 1.8 line
  (e.g. `dbt-duckdb~=1.8.0`, `dbt-snowflake~=1.8.0`); the adapter pulls the
  correct core/common/adapters split transitively. Do not pin `dbt-core~=1.7`.
  This is an **edit to the requirements file only** — do NOT run `pip install`
  or otherwise mutate the Python environment; dependency installation is handled
  separately.
- If any Python code imports from `dbt.exceptions`, `dbt.contracts`, or
  `dbt.events`, update those imports for the split (many moved to
  `dbt_common` / `dbt.adapters`).

### 6. Widen `require-dbt-version` so 1.8 is allowed (version gate)

If `dbt_project.yml` has a `require-dbt-version` bound that excludes 1.8 (e.g.
`[">=1.7.0", "<1.8.0"]`), widen the upper bound (e.g. `[">=1.7.0", "<1.9.0"]`)
so the project runs under 1.8.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. A
clean parse (no errors, no deprecation warnings) means the migration succeeded.
If the parse fails, read the error and fix the specific resource it names, then
parse again.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`,
or `dbt compile`, and do not query any warehouse. Those touch data and are
validated separately — they are out of scope here. `dbt parse` is purely static
and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the
project root summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in
terms of the latest release track and the category above. Keep it concise and
factual — one entry per change.
