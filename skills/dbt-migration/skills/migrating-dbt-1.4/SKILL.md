---
name: migrating-dbt-1.4
description: Upgrade a dbt project from dbt-core 1.4 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.4.
metadata:
    fromVersion: '1.4'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.4 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.4** to **1.8**
(the entry point of the latest release track). A 1.4 project takes four hops to reach
1.8 (1.4→1.5, 1.5→1.6, 1.6→1.7, 1.7→1.8), so this migration applies changes from all
of them. Apply every change below that is present in the project, then verify the
project parses under 1.8. Make only the changes required by this upgrade — do not
refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Move a custom `log-path` / `target-path` out of `dbt_project.yml` (1.4→1.5, deprecation)

Starting in 1.5, configuring `log-path` or `target-path` in `dbt_project.yml` is
deprecated in favor of the `--log-path` / `--target-path` CLI flags or the
`DBT_LOG_PATH` / `DBT_TARGET_PATH` environment variables. On 1.4 these keys are
silent.

The deprecation fires **only when the configured value differs from the default**
(`log-path: "logs"`, `target-path: "target"`) — dbt skips the warning when the value
equals the default. So:

- If `dbt_project.yml` sets `log-path` or `target-path` to a **custom** (non-default)
  directory, remove that key from `dbt_project.yml` and preserve the custom directory
  by passing the corresponding CLI flag (`--log-path` / `--target-path`) or setting the
  env var (`DBT_LOG_PATH` / `DBT_TARGET_PATH`) wherever the project is invoked. Flag
  any invocation sites you cannot see (scheduled jobs, CI config) so the user can move
  the setting there.
- If the value is already the **default** (`"logs"` / `"target"`), the key is silent
  and behaviorally inert; removing it is harmless and future-proofs the project, but
  leaving it does not produce a warning.

### 2. Update an overridden `collect_freshness` macro to return the full query result (1.4→1.5, deprecation)

In 1.5 the `collect_freshness` macro return signature changed: it now returns the
full query result (an object with both `table` and `response`) instead of a bare
`agate.Table`. A project that **overrides** `collect_freshness` (or an adapter-specific
`<adapter>__collect_freshness`) with the pre-1.5 convention — returning the table
directly — triggers a deprecation warning on 1.5 (and 1.6/1.7).

Find any such macro in `macros/`.

- **Preferred fix:** if the override is a verbatim copy of the built-in (adds
  nothing), delete the macro file so the built-in is used.
- **Otherwise:** keep the override but change its return so it returns the full query
  result — e.g. `{% set result = load_result('collect_freshness') %}` followed by
  `{{ return(result) }}` — rather than `return(result.table)`.

### 3. Apply the 1.5→1.8 changes

The rest of this migration is exactly the 1.5→1.8 hops. Read
`../migrating-dbt-1.5/SKILL.md` now and apply every change in its "Changes to
apply" section (the 1.5→1.6 rewrite of pre-1.6 flat `metrics:` definitions into the
MetricFlow spec, then the 1.6→1.8 hops it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.5→1.8 hops, and it can change
independently of this skill.

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
</content>
</invoke>
