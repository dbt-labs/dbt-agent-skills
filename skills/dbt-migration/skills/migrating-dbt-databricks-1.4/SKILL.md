---
name: migrating-dbt-databricks-1.4
description: Use when migrating a dbt project on the dbt-databricks adapter from 1.4 to the latest release track (entry point 1.8). Covers the dbt-databricks-adapter-specific behavior changes only — run this alongside the core migrating-dbt-1.4 skill, which handles the dbt-core changes for the same hops.
metadata:
    fromVersion: '1.4'
    toVersion: '1.8'
---

# Migrate a dbt-databricks project from 1.4 to the latest release track

You are upgrading the **dbt-databricks adapter** side of a dbt project that
currently targets dbt-databricks **1.4** to **1.8** (the entry point of the latest
release track). This skill covers only the changes that come from the
**dbt-databricks adapter** — it is a companion to the core `migrating-dbt-1.4`
skill, which covers the dbt-core changes for the same hops. Apply both.

A 1.4 project passes through 1.4→1.5, 1.5→1.6, 1.6→1.7, 1.7→1.8. This skill owns
the one dbt-databricks case on the **1.4→1.5** hop, then chains to
`migrating-dbt-databricks-1.5` for the remaining hops. Apply every change below
that is present in the project. Make only the changes required by this upgrade —
do not refactor unrelated code.

Work through the project systematically: read `profiles.yml` (all targets),
`models/`, `macros/`, and `dbt_project.yml`, then apply the fixes.

## Changes to apply

### 1. A default socket timeout of 180s is now applied (1.4→1.5, behavior)

On 1.4, dbt-databricks applies no socket timeout of its own — the
`databricks-sql-connector` default governs. From the 1.5 line on,
`connections.py` sets `connection_parameters["_socket_timeout"] = 180`, so any
query whose socket is idle longer than 180 seconds is cut off unless the project
overrides it.

(Attribution note: the source change list placed this default under 1.5→1.6, but
source inspection shows it was introduced in the **1.5 line** — absent in 1.4,
present identically in 1.5 and 1.6. So for a project starting on 1.4 it lands on
the **1.4→1.5** hop, which is why it belongs here.)

If the project runs long queries that can sit with an idle socket for over three
minutes (large MERGE/OPTIMIZE, slow warehouse cold-starts, long-running Python
models), set an explicit `_socket_timeout` under `connection_parameters` in the
relevant `profiles.yml` target(s) so the new 180s default does not truncate them:

```yaml
connection_parameters:
  _socket_timeout: 600
```

If the project's queries comfortably finish inside 180s, no change is needed —
but flag the new default to the user so they can decide, since this is a
behavior change they cannot see from the project code alone.

### 2. Apply the 1.5→1.8 changes

The rest of this migration continues from the 1.5→1.8 hops. Read
`../migrating-dbt-databricks-1.5/SKILL.md` now and apply every change in its
"Changes to apply" section (the 1.5→1.6 hop has no dbt-databricks cases; it chains
onward to the 1.6→1.7 default-catalog change) to this project.

Read that file directly rather than relying on prior knowledge of what it
contains — it is the single source of truth for the 1.5→1.8 hops, and it can change
independently of this skill.

## Verify

After editing, confirm the project still parses by running **`dbt parse`**. A clean
parse means the `profiles.yml` change is well-formed.

The socket-timeout change is a **connection behavior**, not a parse-time or
compile-time artifact: it cannot be observed statically, and reproducing the
truncation would require a query that idles past 180s against a real workspace.
`dbt parse` confirms the `_socket_timeout` config is in place; it does not (and
cannot) confirm the runtime timeout behavior. State this explicitly rather than
claiming parse verifies the timeout.

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

Do not print a target version number in this document — describe changes in terms
of the latest release track and the category above. Keep it concise and factual —
one entry per change.
