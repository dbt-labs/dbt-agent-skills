---
name: migrating-dbt-bigquery-1.3
description: Use when migrating a dbt project on the dbt-bigquery adapter from dbt 1.3 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative dbt-bigquery-adapter-specific behavior changes for a BigQuery project currently on 1.3. This is the adapter-specific companion to the core migrating-dbt-1.3 skill — run both for a full BigQuery migration.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate a dbt-bigquery project from dbt 1.3 to the latest release track

You are upgrading the **dbt-bigquery adapter** side of a dbt project that currently
targets **1.3**, on its way to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-bigquery-adapter-specific** changes. The dbt-core
changes for the same hops are covered separately by the `migrating-dbt-1.3` skill —
apply that one too for a complete migration.

A 1.3 BigQuery project crosses four boundaries (1.3→1.4, 1.4→1.5, 1.5→1.6, 1.6→1.7);
three of them carry a dbt-bigquery-specific change, and this skill chains through them.
Apply every change below that is present in the project. Make only the changes required
by this upgrade — do not refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, `profiles.yml`, the
`models/` (especially incremental models) and their configs, then apply the fixes.

## Changes to apply

### 1. Keep BigQuery job labels within 63 characters (1.3→1.4, behavior)

dbt-bigquery attaches labels to the BigQuery jobs it submits — for example when
`query-comment` sets `job-label: true`, the rendered comment becomes a job label, and
`+labels` model configs become job/table labels. BigQuery caps a label value at 63
characters, and the adapter sanitizes labels before sending them.

The behavior at this cap changed at 1.4:

- **On 1.3:** a label whose sanitized value exceeds 63 chars raises a hard error before
  any query runs (`Runtime Error: Job label length <n> is greater than length limit: 63`,
  from `connections.py::_sanitize_label`).
- **On 1.4 and later:** the same over-length label is **silently truncated** to 63 chars
  and the job runs.

The migration hazard is the silence: a label that used to fail loudly on 1.3 now gets
quietly cut off, which can drop information or make labels collide (e.g. several jobs
truncating to the same 63-char prefix). Find any label whose rendered value can exceed 63
characters after sanitization:

- `query-comment.comment` (in `dbt_project.yml`) when `query-comment.job-label: true`.
- `+labels` / `labels` configs in `dbt_project.yml`, model configs, or `config()` blocks.

Shorten the label so its rendered, sanitized value stays within 63 characters (keeping it
meaningful and, where it matters, unique), rather than relying on the new silent
truncation. This is a judgment change — the right shorter label depends on what the label
is used for downstream (cost attribution, job filtering in `INFORMATION_SCHEMA`). **Ask
the user to confirm** the replacement when the label feeds monitoring or billing queries.
Sanitization lower-cases and replaces disallowed characters, so count length on the
rendered value; if a label is built from a dynamic expression, check the longest value it
can produce.

### 2. Apply the 1.4→1.8 dbt-bigquery changes

The rest of this adapter migration continues from the 1.4→1.8 hops. Read
`../migrating-dbt-bigquery-1.4/SKILL.md` now and apply every change in its "Changes to
apply" section (the `insert_overwrite` NULL-partition handling change, then the 1.5→1.6
change it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it is
the single source of truth for the 1.4→1.8 dbt-bigquery hops, and it can change
independently of this skill.

## Verify

The static parts of this fix can be confirmed without a warehouse; the behavior itself
cannot.

- **Static check (no credentials):** run **`dbt parse`** to confirm the project still
  parses after your edits, and manually confirm every label you touched renders to ≤63
  characters. `dbt parse` does **not** submit jobs, so it will not surface the truncation
  behavior by itself — a clean parse only tells you the config is still valid.
- **Behavioral confirmation (needs a live BigQuery connection):** the label length is only
  exercised when a job is actually submitted. With real credentials configured, run
  `dbt seed` / `dbt run` and inspect the job labels in
  `region-<region>.INFORMATION_SCHEMA.JOBS_BY_USER` (the `labels` field) to confirm the
  label lands intact (≤63 chars, not truncated). Do **not** prescribe this step in an
  environment without credentials — it would fail to connect rather than no-op.

Do not run `dbt build`/`dbt test`/`dbt snapshot`/`dbt compile` as part of verification.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
(or append a "dbt-bigquery adapter" section if the core skill already created one)
summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated) — the job-label change is **behavior**.

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
