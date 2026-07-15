---
name: migrating-dbt-1.6
description: Upgrade a dbt project from dbt-core 1.6 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.6.
metadata:
    fromVersion: '1.6'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.6 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.6** to **1.8**
(the entry point of the latest release track). A 1.6 project takes two hops to reach
1.8 (1.6→1.7, then 1.7→1.8), so this migration applies changes from both hops. Apply
every change below that is present in the project, then verify the project parses
under 1.8. Make only the changes required by this upgrade — do not refactor
unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Fix `clean-targets` entries that overlap source paths or resolve outside the project (1.6→1.7, breaking)

Starting in 1.7, `dbt clean` raises a hard error if any entry in `dbt_project.yml`'s
`clean-targets` overlaps a source path (`seed-paths`, `model-paths`, `macro-paths`,
etc.) or resolves outside the project directory. On 1.6 this was silently allowed —
and could delete source files, since `dbt clean` actually removes every path listed.
Check `clean-targets` against the project's other `-paths` settings and remove or
narrow any entry that overlaps one of them or points outside the project root.

### 2. Numeric columns in contract-enforced models need explicit precision/scale (1.6→1.7, deprecation)

In 1.7, a bare `numeric` (or `decimal`) column type with no precision/scale on a
model with `config: contract: enforced: true` triggers a deprecation warning. Find
every such column in a contract-enforced model and add explicit precision/scale
(e.g. `numeric(18,2)`). If the model's compiled SQL already casts the column to a
specific precision/scale, match that value; otherwise pick a precision/scale wide
enough for the existing data.

### 3. Apply the 1.7→1.8 changes

The rest of this migration is exactly the 1.7→1.8 hop. Read
`../migrating-dbt-1.7/SKILL.md` now and apply every change in its "Changes to
apply" section (renaming `tests:` → `data_tests:`, the built-in materialization
override opt-in, removing spaces from resource names, deduplicating `primary_key`
constraints, the dbt-core/dbt-adapters dependency split, and widening
`require-dbt-version`) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.7→1.8 hop, and it can change
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
