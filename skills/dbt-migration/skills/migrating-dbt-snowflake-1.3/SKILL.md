---
name: migrating-dbt-snowflake-1.3
description: Use when migrating a dbt project on the dbt-snowflake adapter from dbt-snowflake 1.3 to the latest release track (entry point 1.8). Covers the dbt-snowflake-adapter-specific behavior change at the 1.3→1.4 hop only; it is separate from the dbt-core migration and must be applied alongside migrating-dbt-1.3.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate a dbt-snowflake project from dbt-snowflake 1.3 to the latest release track

You are upgrading a project that uses the **dbt-snowflake adapter**, currently on
**dbt-snowflake 1.3**, to **1.8** (the entry point of the latest release track).
This skill covers only the **dbt-snowflake-adapter-specific** change on that path.
It does **not** cover the dbt-core changes (renamed config keys, dependency split,
`require-dbt-version`, deprecations, etc.) — those are handled by the core
`migrating-dbt-1.3` skill. A full migration of a dbt-snowflake 1.3 project needs
**both**: apply `migrating-dbt-1.3` for the core changes and this skill for the
adapter change.

There is exactly **one** actionable dbt-snowflake case across the entire 1.3→1.8
range, and it lives at the **1.3→1.4** hop. The later hops (1.4→1.5, 1.5→1.6,
1.6→1.7, 1.7→1.8) have **no** dbt-snowflake-specific changes to apply, so there is
no `migrating-dbt-snowflake-1.4` (or later) skill — do not look for one. After you
apply the change below, the project has no further dbt-snowflake-specific work to
reach 1.8.

Work through the project systematically: read every incremental model
(`materialized='incremental'`) in `models/`, and check its `config()` for the
`predicates` key.

## Changes to apply

### 1. `predicates` on an incremental model starts being honored (1.3→1.4, Behavior / Deterministic)

Find every incremental model whose `config()` sets the **`predicates`** key, e.g.:

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    predicates=["DBT_INTERNAL_DEST.amount > 0"]
) }}
```

On dbt-core 1.3, the incremental materialization reads **only**
`incremental_predicates` — the legacy `predicates` key is **silently ignored**.
On 1.4, a backwards-compatible fallback was added
(`config.get('predicates', none) or config.get('incremental_predicates', none)`),
so `predicates` **starts being honored** again. `predicates` remains a valid alias
on 1.4+ — it is *not* deprecated and does *not* need renaming to keep working.

This is a **silent behavior change, not a syntax fix**. The correct action depends
on the model's `incremental_strategy`:

- **`merge` or `insert_overwrite`** — these strategies read the predicate. A
  `predicates` value that was a **no-op on 1.3 becomes active on 1.4**: it is
  injected into the merge/insert `ON`/join condition, which can change **which
  rows get matched, updated, or replaced**. This can change your data.
  **Do not silently "fix" this by renaming the key** — renaming to
  `incremental_predicates` changes nothing (the predicate applies either way on
  1.4+); the real event is that a previously-dead predicate turns on.
  **Flag it to the user and let them decide**, presenting both possibilities:
    - If the predicate was always *intended* to constrain the merge (the 1.3
      behavior was the bug), then upgrading simply starts doing the right thing —
      confirm that is the desired result.
    - If the predicate was written long ago and the pipeline has been running
      correctly *without* it for the entire time it was on 1.3, then turning it on
      may change results unexpectedly — the user may want to remove the
      `predicates` config instead of letting it activate.

  This decision needs a human; do not choose for them.

- **`delete+insert` (or any other strategy)** — these strategies never read the
  `predicates`/`incremental_predicates` config, on **any** dbt version. The config
  is **dead configuration**: it had no effect on 1.3 and has no effect on 1.4+, so
  there is **no behavior change across this hop**. Flag it to the user as inert
  config they can remove for clarity, but nothing about the upgrade changes this
  model's output.

When in doubt about which strategy a model uses, check the `incremental_strategy`
in its `config()` (and any project-level or `dbt_project.yml` default). The
strategy is what determines whether this is a real behavior change or dead config.

## Verify

This case is **purely behavioral** and **cannot be verified with `dbt parse`**.
`predicates` is syntactically valid config on every version, so a clean parse tells
you nothing about whether the predicate is being applied. The change is only
observable by running the model against a real Snowflake connection and inspecting
the **compiled** merge SQL — on 1.3 the predicate is absent from the `ON` clause;
on 1.4+ it appears in it. That live check is out of scope for a static migration
pass and is validated separately.

So do not claim this case is "verified" on the basis of a parse. What you *can* do
statically:

- Confirm you have found **every** incremental model using `predicates` and, for
  each, recorded its `incremental_strategy` and whether it is a behavior change
  (`merge`/`insert_overwrite`) or dead config (`delete+insert`/other).
- Optionally run **`dbt parse` only** to confirm your edits (if the user chose to
  remove a `predicates` config) leave the project parsing cleanly. Do **not** run
  `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or `dbt compile`,
  and do not query the warehouse.

Be explicit with the user that the actual behavior change can only be confirmed by
a live `dbt run` + compiled-SQL diff, which this pass does not perform.

## Document the changes

When you are done, create a `migration_changes.md` file at the project root
summarizing what you found. For each incremental model using `predicates` include:

- the file,
- its `incremental_strategy`,
- whether this is a **behavior change** (strategy reads the predicate, so it turns
  on across the hop — needs a user decision) or **dead config** (strategy never
  reads it — no change),
- the category of the latest release track upgrade it addresses (behavior),
- and, if the user made a decision (activate vs. remove the predicate), what was
  decided.

Do not print a target version number in this document — describe changes in terms
of the latest release track and the category above. Keep it concise and factual —
one entry per affected model.
