---
name: migrating-dbt-databricks-1.3
description: Use when migrating a dbt project on the dbt-databricks adapter from 1.3 to the latest release track (entry point 1.8). Covers the dbt-databricks-adapter-specific breaking and behavior changes only — run this alongside the core migrating-dbt-1.3 skill, which handles the dbt-core changes for the same hops.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate a dbt-databricks project from 1.3 to the latest release track

You are upgrading the **dbt-databricks adapter** side of a dbt project that
currently targets dbt-databricks **1.3** to **1.8** (the entry point of the latest
release track). This skill covers only the changes that come from the
**dbt-databricks adapter** — it is a companion to the core `migrating-dbt-1.3`
skill, which covers the dbt-core changes for the same hops. Apply both.

A 1.3 project passes through 1.3→1.4, 1.4→1.5, 1.5→1.6, 1.6→1.7, 1.7→1.8. This
skill owns the three dbt-databricks cases on the **1.3→1.4** hop, then chains to
`migrating-dbt-databricks-1.4` for the remaining hops. Apply every change below
that is present in the project. Make only the changes required by this upgrade —
do not refactor unrelated code.

Work through the project systematically: read `profiles.yml` (all targets),
`models/`, `macros/`, and `dbt_project.yml`, then apply the fixes.

## Changes to apply

### 1. A schema containing `.` now raises an error (1.3→1.4, behavior → error)

In 1.3, a Databricks `schema:` value containing a `.` (e.g. `foo.bar`) only logged
a warning ("… contains '.', which could cause unexpected behavior … will not be
allowed in the future release"). From 1.4 on, `DatabricksCredentials.__post_init__`
raises a hard `DbtValidationError`/`Runtime Error` at credential-parse time:

```
The schema should not contain '.': foo.bar
If you are trying to set a catalog, please use `catalog` instead.
```

Check **every target** in `profiles.yml` (not just the default). For any target
whose `schema:` value contains a `.`:

- If the dotted value was actually meant to select a catalog + schema (e.g.
  `main.analytics`), split it: move the catalog segment to `catalog:` and leave the
  bare schema in `schema:` (e.g. `catalog: main`, `schema: analytics`).
- Otherwise rename the schema so it has no `.` and update anything that referenced
  the old name.

The trigger is the **`profiles.yml` `schema:` value**, not a model-level `+schema:`
config (that path goes through `generate_schema_name` and never reaches this check).

### 2. Identifiers are now backtick-quoted by default (1.3→1.4, behavior)

In 1.3, `DatabricksRelation` inherited Spark's all-False quote policy, so relation
references compiled **unquoted** (`catalog.schema.model`). From 1.4 on,
`DatabricksQuotePolicy` defaults all-True with a backtick `quote_character`, so the
same references compile **backtick-quoted** (`` `catalog`.`schema`.`model` ``).

This is automatic — there is no config to change. But it is a real behavior change
to be aware of and flag:

- Backtick-quoting makes identifiers **case-sensitive** as written. Any model,
  macro, source, or hardcoded SQL that relied on the old unquoted, case-folded
  behavior can resolve differently.
- Flag anything the migration can't see or fix — downstream BI tools, hand-written
  SQL outside the project, or external references to these relations — so the user
  can confirm they still resolve.

Do not add manual backticks to model SQL; the adapter applies quoting itself.

### 3. Rename overridden incremental-validation macros (1.3→1.4, breaking)

In 1.3 the Databricks incremental materialization validated file format and
incremental strategy through **spark-named** macros
(`dbt_spark_validate_get_file_format`,
`dbt_spark_validate_get_incremental_strategy`). In 1.4 those calls were renamed to
`dbt_databricks_validate_get_file_format` /
`dbt_databricks_validate_get_incremental_strategy` (moved into dbt-databricks' own
`.../incremental/validate.sql`).

If the project **overrides** one of the old spark-named macros in `macros/`, that
override silently becomes **dead code** on 1.4+: the materialization no longer calls
that name, so the customization stops taking effect with no error. Find any macro
named:

- `dbt_spark_validate_get_file_format`
- `dbt_spark_validate_get_incremental_strategy`

and rename it to its `dbt_databricks_validate_get_*` equivalent so the customization
keeps running. Preserve the macro body exactly; only the macro name changes. If the
override was a verbatim copy of the built-in that adds nothing, delete it instead so
the built-in is used.

### 4. Apply the 1.4→1.8 changes

The rest of this migration continues from the 1.4→1.8 hops. Read
`../migrating-dbt-databricks-1.4/SKILL.md` now and apply every change in its
"Changes to apply" section (the socket-timeout default on 1.4→1.5, then the
1.6→1.7 default-catalog change it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.4→1.8 hops, and it can change
independently of this skill.

## Verify

After editing, confirm the project still parses by running **`dbt parse`**. A clean
parse (no errors, no deprecation warnings) means the static config is well-formed —
in particular it confirms the Change 1 dotted-schema fix (the schema check fires at
credential parse, so a remaining `.` fails `dbt parse` on 1.4+).

Two of the cases here are **behavioral** and are not fully observable from parse:

- **Change 2 (backtick quoting)** is only visible in compiled SQL. If you want to
  confirm it, `dbt compile` and inspect `target/compiled/…` for backtick-quoted
  relation refs — but this needs warehouse connectivity, and no code change is
  required, so parse is sufficient for the migration itself.
- **Change 3 (macro rename)** only manifests at `dbt run` (the renamed macro is
  called inside the incremental materialization). `dbt parse` confirms the renamed
  macro is well-formed; confirming it actually runs again can only be done by
  running the incremental model against a real Databricks workspace. State this
  explicitly rather than claiming the rename is verified by parse alone.

Do **not** run `dbt build`, `dbt test`, `dbt seed`, or `dbt snapshot`. Keep any
`dbt run` / `dbt compile` to the narrow confirmation described above, only if a live
workspace is available.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project
root (or append a "dbt-databricks adapter" section if the core skill already created
one) summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms
of the latest release track and the category above. Keep it concise and factual —
one entry per change.
