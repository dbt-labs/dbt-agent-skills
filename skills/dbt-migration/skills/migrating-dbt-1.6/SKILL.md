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

### 1. Numeric columns in contract-enforced models need explicit precision/scale (1.6→1.7, deprecation)

In 1.7, a bare `numeric` (or `decimal`) column type with no precision/scale on a
model with `config: contract: enforced: true` triggers a deprecation warning. Find
every such column in a contract-enforced model and add explicit precision/scale
(e.g. `numeric(18,2)`). If the model's compiled SQL already casts the column to a
specific precision/scale, match that value; otherwise pick a precision/scale wide
enough for the existing data.

### 2. Decide how to handle breaking contract changes on unversioned models (1.6→1.7, behavior)

Before 1.7, a breaking change to a **contracted but unversioned** model (e.g.
removing/renaming a column, changing a column's data type) raised a hard error at
parse time. From 1.7, the same change only produces a **warning** — the project
still parses and runs.

Find every unversioned model with `config: contract: enforced: true`. This isn't
a code fix so much as a policy decision, so **ask the user which they want**:

- If the team relies on the old hard-error behavior to catch breaking contract
  changes before they ship, add `--warn-error` (or `--warn-error-options` scoped to
  this warning) to the invocation so the warning becomes a build failure again.
- If versioning contracted models (`versions:` + `latest_version:`) is the
  intended long-term fix for breaking-change safety, that's a larger modeling
  change the user should plan separately — flag it as a follow-up rather than
  attempting it as part of this migration.
- If neither applies, no action is needed — note that the project was checked
  and has no unversioned contracted models (or none with pending breaking
  changes), so the warning has nothing to fire on today.

### 3. Apply the 1.7→1.8 changes

The rest of this migration is exactly the 1.7→1.8 hop. Execute the skill
`migrating-dbt-1.7` for this hop.

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

Create a section for this version hop and describe changes in
terms of the latest release track and the category above. Keep it concise and
factual — one entry per change. If there's an existing `migration_changes.md` 
prepared by the previous version hop, append to the doc.
