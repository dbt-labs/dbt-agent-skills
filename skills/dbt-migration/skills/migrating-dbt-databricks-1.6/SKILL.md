---
name: migrating-dbt-databricks-1.6
description: Use when migrating a dbt project on the dbt-databricks adapter from 1.6 to the latest release track (entry point 1.8). Covers the dbt-databricks-adapter-specific behavior change only — run this alongside the core migrating-dbt-1.6 skill, which handles the dbt-core changes for the same hops.
metadata:
    fromVersion: '1.6'
    toVersion: '1.8'
---

# Migrate a dbt-databricks project from 1.6 to the latest release track

You are upgrading the **dbt-databricks adapter** side of a dbt project that
currently targets dbt-databricks **1.6** to **1.8** (the entry point of the latest
release track). This skill covers only the changes that come from the
**dbt-databricks adapter** — it is a companion to the core `migrating-dbt-1.6`
skill, which covers the dbt-core changes for the same hops. Apply both.

A 1.6 project passes through 1.6→1.7 and 1.7→1.8. This skill owns the one
dbt-databricks case on the **1.6→1.7** hop. The **1.7→1.8** hop has no
dbt-databricks-adapter-specific changes, so this skill is terminal — there is no
further dbt-databricks skill to chain to. Apply the change below if it is present.
Make only the changes required by this upgrade — do not refactor unrelated code.

Work through the project systematically: read `profiles.yml` (all targets),
`models/`, and `dbt_project.yml`, then apply the fix.

## Changes to apply

### 1. Default catalog is now forced to `hive_metastore` when unset (1.6→1.7, behavior)

On 1.6 and earlier, if a Databricks target left `catalog:` unset,
`DatabricksCredentials` left `database = None`, so relations resolved into the
connection's **session-default catalog**. From 1.7 on,
`DatabricksCredentials.__post_init__` forces `database = "hive_metastore"` when
`catalog:` is unset. Relations then compile as
`` `hive_metastore`.`schema`.`model` ``.

On a workspace whose session-default catalog is already `hive_metastore`, this is
invisible. But on a Unity Catalog workspace whose session default is a **non-hive**
catalog (e.g. `main`), a project that relied on the session default will silently
start reading and writing in `hive_metastore` instead — a different physical
location.

Check every Databricks target in `profiles.yml`:

- If a target **omits `catalog:`** and the project relied on the connection's
  session-default catalog being something other than `hive_metastore`, set
  `catalog:` explicitly to that catalog so the target keeps resolving where it did
  before (e.g. `catalog: main`, or `catalog: "{{ env_var('DBT_DATABRICKS_CATALOG') }}"`).
- If the project genuinely intended `hive_metastore` (or the session default already
  is `hive_metastore`), no change is needed — but flag the new forced default to the
  user, since this is a behavior change they cannot see from the project code alone
  and it depends on the target workspace's session default, which the migration
  cannot inspect.

This is the only dbt-databricks case on this hop, and the 1.7→1.8 hop adds none, so
there is nothing further to chain — the dbt-databricks migration ends here.

## Verify

After editing, confirm the project still parses by running **`dbt parse`**. A clean
parse means the `profiles.yml` change is well-formed.

The catalog default is a **connection/compile behavior**, not a parse-time artifact.
The clean, warehouse-independent signal is that on 1.7+ `dbt debug` reports
`catalog: hive_metastore` when `catalog:` is unset, whereas ≤1.6 shows no catalog
line. Confirming the *data-location* difference (session default vs. forced
`hive_metastore`) requires a Unity Catalog workspace whose session default is not
`hive_metastore`; it cannot be observed on a workspace whose session default is
already `hive_metastore`. `dbt parse` confirms the explicit `catalog:` config is in
place; the behavioral difference can only be confirmed against a real workspace.
State this explicitly rather than claiming parse verifies the catalog behavior.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, or `dbt snapshot`,
and do not query any warehouse. `dbt parse` is the only verification to run here.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project
root summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms
of the latest release track and the category above. Keep it concise and factual —
one entry per change.
