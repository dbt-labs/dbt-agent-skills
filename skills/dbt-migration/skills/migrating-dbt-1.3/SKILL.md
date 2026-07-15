---
name: migrating-dbt-1.3
description: Upgrade a dbt project from dbt-core 1.3 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.3.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.3 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.3** to **1.8**
(the entry point of the latest release track). A 1.3 project takes five hops to
reach 1.8 (1.3→1.4, 1.4→1.5, 1.5→1.6, 1.6→1.7, 1.7→1.8), so this migration applies
changes from every hop. Apply every change below that is present in the project,
then verify the project parses under 1.8. Make only the changes required by this
upgrade — do not refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Pin Python model materializations that relied on the `view` default (1.3→1.4, behavior)

In 1.4 the default materialization for Python models (`.py` models with a
`def model(dbt, session)` and no explicit `materialized` config) changed from
`view` to `table`. On 1.3 such a model built as a view; from 1.4 on it builds as
a table — a physically different object with different storage and refresh
semantics, and every downstream `ref()` now resolves to a table.

Find every Python model that has no explicit materialization. If a model relied
on the old `view` default, set it explicitly:

```python
def model(dbt, session):
    dbt.config(materialized="view")
    ...
```

Models that are fine as tables need no change — the point is to make the choice
explicit so the upgrade does not silently swap the materialization out from under
downstream consumers.

### 2. Apply the 1.4→1.8 changes

The rest of this migration continues from the 1.4→1.8 hop. Read
`../migrating-dbt-1.4/SKILL.md` now and apply every change in its "Changes to
apply" section (moving a custom `log-path` / `target-path` out of
`dbt_project.yml`, and updating an overridden `collect_freshness` macro to return
the full query result, then the 1.5→1.8 hops it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.4→1.8 hop, and it can change
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
