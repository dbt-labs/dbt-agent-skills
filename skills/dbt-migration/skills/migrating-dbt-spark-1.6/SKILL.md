---
name: migrating-dbt-spark-1.6
description: Use when upgrading the dbt-spark adapter in a dbt project from dbt-spark 1.6 to the latest release track (entry point 1.8) so it runs on the dbt platform. Covers the dbt-spark-adapter-specific changes only; it is distinct from the dbt-core migration skill for 1.6 — run both for a full migration.
metadata:
    fromVersion: '1.6'
    toVersion: '1.8'
---

# Migrate the dbt-spark adapter from 1.6 to the latest release track

You are upgrading the **dbt-spark adapter** in a dbt project that currently targets
dbt-spark **1.6** to **1.8** (the entry point of the latest release track). This skill
covers only the changes specific to the dbt-spark adapter — the dbt-core changes for
this hop are covered separately by the `migrating-dbt-1.6` skill, which you should run
as well for a complete migration.

A 1.6 project takes two hops to reach 1.8 (1.6→1.7, then 1.7→1.8). The only actionable
dbt-spark-adapter-specific change on this path lands at the 1.6→1.7 boundary; the
1.7→1.8 hop contributes **no** dbt-spark-adapter-specific changes, so this is the
terminal dbt-spark skill in the chain — there is nothing further to chain to.

Work through the project systematically: read `profiles.yml` (all targets/outputs),
`dbt_project.yml`, and `requirements.txt` (or equivalent), then apply the fix.

## Changes to apply

### 1. Quote non-string `server_side_parameters` values (1.6→1.7, behavior → profile-validation error)

In dbt-spark 1.7 the `server_side_parameters` field on the Spark profile was retyped
from `Dict[str, Any]` to `Dict[str, str]`, and `SparkCredentials` now coerces every
value with `str()`. Two consequences:

- **Validation break (migration-facing).** A `server_side_parameters` value written as
  an unquoted YAML boolean or number is accepted on 1.6 but is a hard profile-validation
  error on the latest track (`... is not of type 'string'`), raised as soon as the
  profile is loaded.
- **Value coercion.** Values that do load are coerced to strings — e.g. `True` becomes
  the string `"True"` (capital T), `5` becomes `"5"`. Any downstream logic that compares
  against the raw type sees a string instead.

Find every `server_side_parameters` block across all outputs in `profiles.yml` (and any
`server_side_parameters` set in `dbt_project.yml` / model configs). For each entry whose
value is a bare boolean or number, quote it so it is an explicit string:

```yaml
server_side_parameters:
    spark.sql.ansi.enabled: "true"      # was: true
    spark.sql.shuffle.partitions: "200" # was: 200
    spark.sql.session.timeZone: "America/New_York"
```

Quote the value only; leave the parameter key and the rest of the profile unchanged.
Preserve the intended Spark meaning — `true` becomes the string `"true"`, not `"True"`,
since it is passed through to Spark as a config string.

> Note: under the local `session` connection method, `server_side_parameters` were
> ignored entirely on ≤1.6 and are actually applied to the `SparkSession` on 1.7+. This
> means a value that was silently inert before now takes effect. If a parameter was left
> in the profile as a no-op, confirm it is still the value you want applied.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. Profile
validation runs during parse, so an unquoted non-string `server_side_parameters` value
that would break on the latest track surfaces here as a parse-time error — a clean parse
(no errors, no deprecation warnings) means the profile change is correct.

The *runtime* facets of this change — the `str()` coercion of values and
`server_side_parameters` actually being applied to the `SparkSession` under the `session`
method — are only observable when running against a live Spark session, and are not
something `dbt parse` exercises. Do **not** prescribe a live `dbt run`/`dbt build` to
check them: without Spark cluster/session credentials such a command would either fail to
connect or silently no-op. The static `dbt parse` check plus a code-level review of the
quoted values is the verification to perform here.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or
`dbt compile`, and do not query any warehouse. Those touch data and are validated
separately. `dbt parse` is purely static and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
(or append a "dbt-spark adapter" section if the core skill already created one)
summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
