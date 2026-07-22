---
name: migrating-dbt-bigquery-1.6
description: Use when migrating a dbt project on the dbt-bigquery adapter from dbt 1.6 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the dbt-bigquery-adapter-specific behavior change at the 1.6→1.7 hop. This is the adapter-specific companion to the core migrating-dbt-1.6 skill — run both for a full BigQuery migration.
metadata:
    fromVersion: '1.6'
    toVersion: '1.8'
---

# Migrate a dbt-bigquery project from dbt 1.6 to the latest release track

You are upgrading the **dbt-bigquery adapter** side of a dbt project that currently
targets **1.6**, on its way to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-bigquery-adapter-specific** change. The dbt-core
changes for the same hops are covered separately by the `migrating-dbt-1.6` skill —
apply that one too for a complete migration.

A 1.6 BigQuery project crosses two boundaries (1.6→1.7, 1.7→1.8). The only
dbt-bigquery-specific change on this path lands at **1.6→1.7**; the 1.7→1.8 hop
contributes no dbt-bigquery-specific change, so this is the terminal dbt-bigquery
skill in the chain — there is nothing further to chain to.

Work through the project systematically: read `dbt_project.yml` and `profiles.yml`
for every target that sets `job_execution_timeout_seconds`, then apply the fix.

## Changes to apply

### 1. Review `job_execution_timeout_seconds` values now that the timeout is actually enforced (1.6→1.7, behavior)

Before 1.7, a configured `job_execution_timeout_seconds` was passed to the
BigQuery client's local wait call, but **the timeout was not actually enforced**
against the running job — a query that exceeded it kept running to completion on
BigQuery's side regardless of the configured value. From 1.7, dbt-bigquery uses
`asyncio` and actually **cancels** the job when the timeout elapses, and the
invocation errors.

This means a `job_execution_timeout_seconds` value that was previously harmless
(because it was never really enforced) can now **cause queries to be killed and
error** if the value is too low for how long the project's queries legitimately
take.

Find every `job_execution_timeout_seconds` set in `profiles.yml` (any target) or
passed via `dbt_project.yml` connection config. For each one:

- Check whether the project's longest-running models/queries could realistically
  exceed the configured value. If the value was set defensively/arbitrarily
  (common, since it never mattered before), **ask the user** to confirm it still
  reflects a real intended ceiling, or to raise it.
- If no `job_execution_timeout_seconds` is set anywhere, no action is needed —
  there's no configured value that could newly misbehave.

## Verify

This is a **runtime behavior change** — the timeout is only enforced when a real
BigQuery job actually runs past the configured duration. `dbt parse` cannot
observe it.

- **Static check (no credentials):** run **`dbt parse` only** to confirm the
  project still parses after any config review/edit.
- **Behavioral confirmation (needs a live BigQuery connection):** if you changed a
  timeout value, that's a config edit with no compiled-SQL difference to inspect
  — confirming the new value is sufficient requires running the affected model(s)
  against a real BigQuery connection. Do not prescribe this in an environment
  without credentials.

Do not run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or
`dbt compile` as part of this skill's verification.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the
project root (or append a "dbt-bigquery adapter" section if the core skill
already created one) summarizing what you found. Include:

- which (if any) `job_execution_timeout_seconds` values were reviewed or changed,
- what was decided,
- the category of the latest release track upgrade it addresses (behavior).

Do not print a target version number in this document — describe changes in
terms of the latest release track and the category above. Keep it concise and
factual.
