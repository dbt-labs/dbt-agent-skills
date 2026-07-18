---
name: migrating-dbt-bigquery-1.5
description: Use when migrating a dbt project on the dbt-bigquery adapter from dbt 1.5 to the latest release track (entry point 1.8) so it runs on the dbt platform. Covers the dbt-bigquery-adapter-specific behavior change for a BigQuery project currently on 1.5. This is the adapter-specific companion to the core migrating-dbt-1.5 skill — run both for a full BigQuery migration.
metadata:
    fromVersion: '1.5'
    toVersion: '1.8'
---

# Migrate a dbt-bigquery project from dbt 1.5 to the latest release track

You are upgrading the **dbt-bigquery adapter** side of a dbt project that currently
targets **1.5**, on its way to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-bigquery-adapter-specific** changes. The dbt-core
changes for the same hops are covered separately by the `migrating-dbt-1.5` skill —
apply that one too for a complete migration.

A 1.5 BigQuery project crosses two boundaries (1.5→1.6, 1.6→1.7). Only the 1.5→1.6 hop
carries a dbt-bigquery-specific change, described below. **This skill is terminal for the
dbt-bigquery adapter:** the 1.6→1.7 hop has no dbt-bigquery-adapter case (the one
candidate, `job_execution_timeout` server-side cancellation, was live-verified and did not
reproduce at this boundary — 1.6 and 1.7 behave identically — so it is not a case), and
there is nothing further to chain to. Do the dbt-core changes for 1.6→1.8 via the
`migrating-dbt-1.5` core skill.

## Changes to apply

### 1. Do not hardcode the `dbt debug` connection field list (1.5→1.6, behavior — usually no project change)

At 1.6, dbt-bigquery expanded the set of connection fields it reports. `dbt debug`'s
Connection section lists **13** fields on 1.5 and **19** on 1.6 — the 13 (`method`,
`database`, `schema`, `location`, `priority`, `timeout_seconds`,
`maximum_bytes_billed`, `execution_project`, `job_retry_deadline_seconds`, `job_retries`,
`job_creation_timeout_seconds`, `job_execution_timeout_seconds`, `gcs_bucket`) plus
`impersonate_service_account`, `client_id`, `token_uri`, `dataproc_region`,
`dataproc_cluster_name`, `dataproc_batch`.

This is a **diagnostic-output** change, not a change to how the project builds. **In the
dbt project itself there is nothing to fix** — no model, config, or `profiles.yml` edit is
required, and adding fields to a profile is not part of this migration. Do not invent a fix
here.

The only actionable item is external: if any tooling around the project parses `dbt debug`
output and assumes the 1.5 field set — a script, a health check, or an agent that counts
or matches connection fields — update it to tolerate the expanded field list (do not
hardcode 13 fields or an exact field roster). Flag such tooling to the user; it usually
lives outside the dbt project directory (CI, monitoring, wrappers), so you may not be able
to see or change it here.

## Verify

There is normally **no project code change** for this hop, so there is nothing new for
`dbt parse` to confirm beyond the project still parsing. Run **`dbt parse`** to confirm the
project is still structurally valid.

The field-count behavior is only observable by running `dbt debug`, which **requires a live
BigQuery connection**. If credentials are configured, run
`dbt debug --profiles-dir .` and confirm the Connection section is read correctly by any
downstream tooling. Do **not** prescribe `dbt debug` in an environment without credentials
— it would fail the connection test rather than no-op, and it verifies tooling behavior
rather than a change in the project.

Do not run `dbt build`/`dbt run`/`dbt test`/`dbt seed`/`dbt snapshot`/`dbt compile` as
part of verification.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
summarizing everything you did. If you made **no** change to the project for this hop
(the common case), record that explicitly — note that the 1.5→1.6 `dbt debug` connection
field expansion is a diagnostic-output **behavior** change requiring no project edit, and
list any external tooling you flagged. If you did change external tooling, for each change
include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated) — this change is **behavior**.

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
