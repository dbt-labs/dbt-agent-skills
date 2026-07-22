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

### 1. Replace `--dry-run` with `dbt deps --lock` (1.7→1.8, breaking)

The `--dry-run` flag is removed from `dbt deps --add-package` in 1.8 — a
command using it now errors instead of running. Find any invocation of
`dbt deps --add-package ... --dry-run` (in scripts, CI config, or documented
in the project) and replace it with `dbt deps --lock`, which is the 1.8
equivalent for resolving/locking package versions without installing them.

### 2. Remove spaces from resource names (1.7→1.8, deprecated)

Spaces in resource names raise `SpacesInResourceNameDeprecation` in 1.8. Find
resources (sources, models, seeds, etc.) whose `name:` contains a space — e.g.
a source `name: raw events` — and rename it (e.g. `raw_events`).

Update every reference you can find: `source('raw events', ...)` / `ref('...')`
calls, the resource's own file name if it's derived from the name, and any
`select`/`exclude` selectors in the project (`selectors.yml`). If a rename
would collide with an existing resource name, pick a distinct name that
preserves the original intent (e.g. append a qualifier) rather than skipping
the rename. **Note, but do not block on**, references you cannot see from the
project alone — `--select` in scheduled jobs or BI tool references — so the
user knows to check them.

### 3. Declare each `primary_key` constraint in exactly one place (1.7→1.8, behavior)

In 1.8, declaring a `primary_key` constraint both at the model level
(`constraints:`) and at the column level (`columns: <col>: constraints:`)
throws a `ParsingError` at parse time. For any model that does this, keep the
`primary_key` in exactly one location and remove the duplicate.

### 4. Widen `require-dbt-version` so 1.8 is allowed

This isn't a behavior change being tracked for compatibility — it's a
mechanical prerequisite for the project to run under 1.8 at all. If
`dbt_project.yml` has a `require-dbt-version` bound that excludes 1.8 (e.g.
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

Create a section for this version hop and describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one
entry per change. If there's an existing `migration_changes.md` prepared by a
previous version hop, append to the doc — this is the last hop, so the result
is the complete migration summary.
