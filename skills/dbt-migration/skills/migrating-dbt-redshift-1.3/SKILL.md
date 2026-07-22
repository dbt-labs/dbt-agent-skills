---
name: migrating-dbt-redshift-1.3
description: Use when migrating a dbt project that uses the dbt-redshift adapter from 1.3 to the latest release track (entry point 1.8). Covers the dbt-redshift-adapter-specific changes only (connection defaults, profile fields, adapter internals, macros) — apply it alongside the core migrating-dbt-1.3 skill, which handles the dbt-core changes.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate the dbt-redshift adapter from 1.3 to the latest release track

You are upgrading the **dbt-redshift-adapter-specific** parts of a dbt project that
currently targets dbt-redshift **1.3**, on its way to **1.8** (the entry point of the
latest release track). A 1.3 project takes five hops to reach 1.8 (1.3→1.4, 1.4→1.5,
1.5→1.6, 1.6→1.7, 1.7→1.8), so this migration applies the redshift changes from every
hop.

This skill is **adapter-specific and complements the core `migrating-dbt-1.3` skill** —
it does not repeat the dbt-core changes (renamed keys, `require-dbt-version`, etc.). For
a full migration, apply both: the core skill for dbt-core changes and this chain for
dbt-redshift changes.

Most dbt-redshift changes are **adapter-internal behavior shifts, not project-code
edits**. Apply a change only where the project actually exercises it — a set connection
field, an overridden adapter macro, or custom Python that subclasses the adapter. Work
through `profiles.yml`, `dbt_project.yml`, `macros/`, and any Python plugin/hook code,
and make only the changes this upgrade requires.

## Changes to apply

### 1. `keepalives_idle` connection default changed 240 → 4 seconds (1.3→1.4, behavior)

`keepalives_idle` is a field on `RedshiftCredentials`. Its **default** dropped from
`240` seconds (1.3) to `4` seconds (1.4), so a profile that does **not** set
`keepalives_idle` explicitly gets much more aggressive idle TCP keepalive probing from
1.4 on. This is a pure connection-behavior change — nothing in the project needs editing
to "fix" it, but be aware the socket behavior changes if you relied on the old default.

Important downstream note: `keepalives_idle` is **removed entirely at the next hop**
(1.4→1.5) when `RedshiftCredentials` stops subclassing `PostgresCredentials` — see the
`migrating-dbt-redshift-1.4` skill, Case "profile fields removed". So the durable action
for a project going all the way to 1.8 is to **stop setting `keepalives_idle` in
`profiles.yml`**, because it becomes an unknown key. If your profile sets it, plan to
remove it (the 1.4 skill covers this); if it doesn't, no edit is needed here.

### 2. Apply the 1.4→1.8 redshift changes

The rest of this migration continues from the 1.4→1.8 hop. Read
`../migrating-dbt-redshift-1.4/SKILL.md` now and apply every change in its "Changes to
apply" section (the removal of `iam_duration_seconds` / `search_path` / `keepalives_idle`
profile fields, the adapter parent-class change to `SQLAdapter`, the `connect_timeout`
default change, the `sslmode` → `verify-ca` remapping, and the autocommit-by-default
change, then the 1.5→1.8 redshift hops it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.4→1.8 redshift hops, and it can change
independently of this skill.

## Verify

Most of the dbt-redshift changes in this chain are connection/runtime behaviors, not
static-parse concerns, so `dbt parse` alone will **not** exercise them. Verify at the
lowest-cost level that actually observes each change:

- **This hop (`keepalives_idle` default):** not observable from `dbt parse` and not
  observable without a live socket. Confirm the field's default at the source level
  instead (no warehouse needed), against the target adapter version:
  ```bash
  python -c "import dataclasses; from dbt.adapters.redshift.connections import RedshiftCredentials as C; \
      print([f.default for f in dataclasses.fields(C) if f.name=='keepalives_idle'])"
  ```
  On 1.5+ the field is gone entirely (empty list), which is the real end-state — confirm
  your profile no longer sets it.
- **Chained hops:** apply the verification each chained skill prescribes.
- Run `dbt parse` after all edits to confirm the project still parses cleanly. Note a
  clean parse does **not** prove the redshift behavior changes are handled — it only
  proves the project is structurally valid.

Do not run `dbt build`/`dbt run`/`dbt seed` against a warehouse as part of this skill
unless a case explicitly calls for a live connection and warehouse credentials are
available; those are validated separately.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
(or append a "dbt-redshift adapter" section if the core skill already created one)
summarizing everything you did. For each change include:

- the file that changed (or "no file change — adapter behavior only" where applicable),
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
