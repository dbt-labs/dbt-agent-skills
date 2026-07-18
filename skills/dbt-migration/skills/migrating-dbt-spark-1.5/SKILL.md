---
name: migrating-dbt-spark-1.5
description: Use when upgrading the dbt-spark adapter in a dbt project from dbt-spark 1.5 to the latest release track (entry point 1.8) so it runs on the dbt platform. Covers the dbt-spark-adapter-specific changes only; it is distinct from the dbt-core migration skill for 1.5 — run both for a full migration.
metadata:
    fromVersion: '1.5'
    toVersion: '1.8'
---

# Migrate the dbt-spark adapter from 1.5 to the latest release track

You are upgrading the **dbt-spark adapter** in a dbt project that currently targets
dbt-spark **1.5** to **1.8** (the entry point of the latest release track). This skill
covers only the changes specific to the dbt-spark adapter — the dbt-core changes for
this hop are covered separately by the `migrating-dbt-1.5` skill, which you should run
as well for a complete migration.

A 1.5 project takes three hops to reach 1.8 (1.5→1.6, 1.6→1.7, 1.7→1.8). Apply every
change below that is present in the project, then continue down the chain.

## Changes to apply

### 1. No dbt-spark-adapter-specific changes at the 1.5→1.6 hop

The 1.5→1.6 hop contributes **no** actionable dbt-spark-adapter-specific changes. There
is nothing for this skill to apply at this hop directly — proceed to the next hop.

### 2. Apply the 1.6→1.8 dbt-spark changes

The rest of this migration continues from the 1.6→1.8 dbt-spark hops. Read
`../migrating-dbt-spark-1.6/SKILL.md` now and apply every change in its "Changes to
apply" section (quoting non-string `server_side_parameters` values) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.6→1.8 dbt-spark hops, and it can change
independently of this skill.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. Profile
validation runs during parse, so a `server_side_parameters` change that would break on
the latest track surfaces here. A clean parse (no errors, no deprecation warnings) means
the migration succeeded. Runtime-only dbt-spark behaviors (see the 1.6 skill) require a
live Spark session and are not something `dbt parse` exercises — do not prescribe a live
`dbt run`/`dbt build` to check them.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or
`dbt compile`, and do not query any warehouse. Those touch data and are validated
separately. `dbt parse` is purely static and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
