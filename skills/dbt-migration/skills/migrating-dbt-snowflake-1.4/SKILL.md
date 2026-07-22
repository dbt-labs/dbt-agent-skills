---
name: migrating-dbt-snowflake-1.4
description: Use when migrating a dbt project on the dbt-snowflake adapter from dbt-snowflake 1.4 to the latest release track (entry point 1.8). Covers the dbt-snowflake-adapter-specific behavior change at the 1.4→1.5 hop only; it is separate from the dbt-core migration and must be applied alongside migrating-dbt-1.4.
metadata:
    fromVersion: '1.4'
    toVersion: '1.8'
---

# Migrate a dbt-snowflake project from dbt-snowflake 1.4 to the latest release track

You are upgrading a project that uses the **dbt-snowflake adapter**, currently on
**dbt-snowflake 1.4**, to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-snowflake-adapter-specific** change on that path.
It does **not** cover the dbt-core changes (environment variable renames, `log-path`
/ `target-path` deprecation, etc.) — those are handled by the core `migrating-dbt-1.4`
skill. A full migration of a dbt-snowflake 1.4 project needs **both**: apply
`migrating-dbt-1.4` for the core changes and this skill for the adapter change.

There is exactly **one** actionable dbt-snowflake case across the entire 1.4→1.8
range, and it lives at the **1.4→1.5** hop. The later hops (1.5→1.6, 1.6→1.7,
1.7→1.8) have **no** dbt-snowflake-specific changes to apply, so there is no
`migrating-dbt-snowflake-1.5` (or later) skill — do not look for one. After you
apply the change below, the project has no further dbt-snowflake-specific work to
reach 1.8.

Work through the project systematically: read every macro override, hook
(`pre-hook`/`post-hook`, `on-run-start`/`on-run-end`), and any custom Python
plugin code that issues raw SQL against the Snowflake connection.

## Changes to apply

### 1. Review standalone `BEGIN`/`COMMIT`/`ROLLBACK` statements issued outside dbt's normal transaction handling (1.4→1.5, behavior)

From 1.5, dbt-snowflake's connection layer added a check that detects and warns on
a query whose entire text is just a standalone transaction-control statement —
`BEGIN`, `COMMIT`, or `ROLLBACK` issued on its own, outside dbt's normal
materialization-driven transaction wrapping. On 1.4 no such warning existed.

Find any custom macro, hook, or override that runs a raw `BEGIN`, `COMMIT`, or
`ROLLBACK` via a `run_query`/`statement` block (dbt already wraps model builds in
a transaction automatically, so most projects don't do this deliberately —
search for it rather than assuming it's absent).

- If none are found, no action is needed — note that explicitly so the review is
  documented as complete.
- If one is found, confirm with the user whether the standalone transaction
  control is still intentional (e.g. custom transaction-scoping logic spanning
  several models). This is a **warning, not an error** — the code keeps working
  either way — but the user should decide whether to keep it, since Snowflake's
  session-level transaction semantics are what the new warning is calling out.
- If it's a leftover from an older pattern that no longer serves a purpose, it
  can be removed with the user's confirmation.

## Verify

This case is a **runtime warning**, not a parse-time or compile-time construct —
`dbt parse` cannot observe it. What you *can* do statically:

- Confirm you have found every macro/hook that issues a standalone transaction-control
  statement by searching `macros/` and the hooks in `dbt_project.yml` and model
  `config()` blocks.
- Run **`dbt parse` only** to confirm your edits (if any) leave the project parsing
  cleanly. Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`,
  `dbt snapshot`, or `dbt compile`, and do not query the warehouse.

Be explicit with the user that observing the warning itself requires a live
`dbt run`/`dbt build` against a real Snowflake connection, which this pass does
not perform.

## Document the changes

When you are done, create a `migration_changes.md` file at the project root (or
append a "dbt-snowflake adapter" section if the core skill already created one)
summarizing what you found. Include:

- whether any standalone transaction-control statements were found, and where,
- what was decided (kept, removed, or confirmed intentional),
- the category of the latest release track upgrade it addresses (behavior).

Do not print a target version number in this document — describe changes in terms
of the latest release track and the category above. Keep it concise and factual.
