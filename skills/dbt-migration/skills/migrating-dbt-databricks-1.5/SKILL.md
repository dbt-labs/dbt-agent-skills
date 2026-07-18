---
name: migrating-dbt-databricks-1.5
description: Use when migrating a dbt project on the dbt-databricks adapter from 1.5 to the latest release track (entry point 1.8). Covers the dbt-databricks-adapter-specific changes only — run this alongside the core migrating-dbt-1.5 skill, which handles the dbt-core changes for the same hops.
metadata:
    fromVersion: '1.5'
    toVersion: '1.8'
---

# Migrate a dbt-databricks project from 1.5 to the latest release track

You are upgrading the **dbt-databricks adapter** side of a dbt project that
currently targets dbt-databricks **1.5** to **1.8** (the entry point of the latest
release track). This skill covers only the changes that come from the
**dbt-databricks adapter** — it is a companion to the core `migrating-dbt-1.5`
skill, which covers the dbt-core changes for the same hops. Apply both.

A 1.5 project passes through 1.5→1.6, 1.6→1.7, 1.7→1.8.

## Changes to apply

### 1. The 1.5→1.6 hop has no dbt-databricks changes

There are **no dbt-databricks-adapter-specific changes on the 1.5→1.6 hop**.
Nothing to do for this hop. (The socket-timeout default is a 1.4→1.5 change, so a
1.5 project is already past it.) Do not invent a change here.

### 2. Apply the 1.6→1.8 changes

The actionable dbt-databricks work for a 1.5 project is on the later hops. Read
`../migrating-dbt-databricks-1.6/SKILL.md` now and apply every change in its
"Changes to apply" section (the 1.6→1.7 default-catalog change) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.6→1.8 hops, and it can change
independently of this skill.

## Verify

After applying the chained 1.6→1.8 changes, confirm the project still parses by
running **`dbt parse`**. Follow the verification guidance in
`../migrating-dbt-databricks-1.6/SKILL.md` for the case it owns.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or
`dbt compile`, and do not query any warehouse. `dbt parse` is the only verification
to run here.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project
root summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

If the only dbt-databricks work was the chained 1.6→1.8 change, record that; if the
project had nothing to change on any hop, say so explicitly. Do not print a target
version number in this document. Keep it concise and factual — one entry per change.
