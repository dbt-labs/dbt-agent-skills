---
name: migrating-dbt-redshift-1.7
description: Use when migrating a dbt project that uses the dbt-redshift adapter from 1.7 to the latest release track (entry point 1.8). Documents that there are no dbt-redshift-adapter-specific changes for this hop — apply it alongside the core migrating-dbt-1.7 skill, which handles the dbt-core changes.
metadata:
    fromVersion: '1.7'
    toVersion: '1.8'
---

# Migrate the dbt-redshift adapter from 1.7 to the latest release track

You are upgrading the **dbt-redshift-adapter-specific** parts of a dbt project that
currently targets dbt-redshift **1.7**, on its way to **1.8** (the entry point of the
latest release track). This is a single hop (1.7→1.8) and it is the terminal skill in the
dbt-redshift migration chain.

This skill is **adapter-specific and complements the core `migrating-dbt-1.7` skill** —
it does not repeat the dbt-core changes. For a full migration, apply both.

## Changes to apply

**There are no dbt-redshift-adapter-specific changes for the 1.7→1.8 hop.**

The migration doc lists a catalog-macro restructuring under the 1.7→1.8 hop, but adapter
source shows that split actually landed at **1.6→1.7**: the dbt-redshift 1.7 and 1.8
`catalog/` directories are byte-identical (verified via `diff -rq` across the 1.7 and 1.8
wheels). So a project **starting at 1.7 already has the split in effect** and does not
encounter it on the way to 1.8. (If your project actually started before 1.7 and
overrides catalog macros, handle that in `../migrating-dbt-redshift-1.6/SKILL.md`, which
owns the 1.6→1.7 catalog change.)

The connection/profile fields whose validity changed in earlier hops
(`keepalives_idle`/`iam_duration_seconds`/`search_path` removed at 1.5;
`connect_timeout`/`autocommit` introduced at 1.5; the `sslmode`→`verify-ca` remap at 1.5)
are all **already settled at 1.7** and are not 1.7→1.8 changes — no action here.

Two things that are **not** dbt-redshift-specific and are therefore handled elsewhere:

- The Python dependency-pin bump (e.g. `dbt-redshift~=1.8.0` in `requirements.txt`) is
  handled by the **core `migrating-dbt-1.7` skill's** dependency-split step. Apply that
  skill.
- All dbt-core 1.7→1.8 changes (renamed `tests:` → `data_tests:`, built-in
  materialization override opt-in, and so on) are likewise in the core skill.

## Verify

There is no dbt-redshift-specific behavior to verify for this hop. As a sanity check that
the project is structurally valid after the core-skill changes are applied, run
**`dbt parse`**. A clean parse means the project is well-formed; it does not, by itself,
exercise any adapter behavior (there is none to exercise at this hop).

Do not run `dbt build`/`dbt run`/`dbt seed` or query a warehouse as part of this skill.

## Document the changes

Record in `migration_changes.md` (or append to a "dbt-redshift adapter" section if the
core skill already created one) that **no dbt-redshift-adapter-specific changes were
required for this hop**, and note that the catalog-macro split the migration doc labels
1.7→1.8 actually landed at 1.6→1.7 and is already in effect at 1.7. Keep it concise and
factual. Do not print a target version number — describe changes in terms of the latest
release track.
