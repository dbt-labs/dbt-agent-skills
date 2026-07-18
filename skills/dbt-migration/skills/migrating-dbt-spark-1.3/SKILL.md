---
name: migrating-dbt-spark-1.3
description: Use when upgrading the dbt-spark adapter in a dbt project from dbt-spark 1.3 to the latest release track (entry point 1.8) so it runs on the dbt platform. Covers the dbt-spark-adapter-specific changes only; it is distinct from the dbt-core migration skill for 1.3 — run both for a full migration.
metadata:
    fromVersion: '1.3'
    toVersion: '1.8'
---

# Migrate the dbt-spark adapter from 1.3 to the latest release track

You are upgrading the **dbt-spark adapter** in a dbt project that currently targets
dbt-spark **1.3** to **1.8** (the entry point of the latest release track). This skill
covers only the changes specific to the dbt-spark adapter — the dbt-core changes for
this hop are covered separately by the `migrating-dbt-1.3` skill, which you should run
as well for a complete migration.

A 1.3 project takes five hops to reach 1.8 (1.3→1.4, 1.4→1.5, 1.5→1.6, 1.6→1.7,
1.7→1.8). Apply every change below that is present in the project, then continue down
the chain.

Work through the project systematically: read `profiles.yml` (all targets/outputs),
`macros/`, the `models/` SQL, `dbt_project.yml`, and `requirements.txt`, then apply the
fixes.

## Changes to apply

### 1. Review single-quote escaping for the `escape_single_quotes` switch (1.3→1.4, behavior)

In dbt-spark 1.4 the adapter added a `spark__escape_single_quotes` override. On 1.3
there was no override, so dbt-spark fell through to dbt-core's `default__escape_single_quotes`,
which escapes an apostrophe by **doubling** it (`'` → `''`). From 1.4 on, the Spark
override escapes with a **backslash** (`'` → `\'`) instead. The escaped output is
different across the hop.

`escape_single_quotes` is used wherever dbt-spark embeds a string literal containing an
apostrophe into SQL — e.g. `persist_docs` column/table comments and snapshot check-cols
values. This is a judgment change, not a mechanical rename:

- **Search the project** for direct calls to `escape_single_quotes` in macros or model
  SQL, and for any logic that depends on the doubled-quote (`''`) form — for example a
  macro that builds a literal and then compares it against a stored value, or that feeds
  the escaped string to a downstream system expecting `''`.
- Where the project relies on the old doubling behavior, update it to expect backslash
  escaping (`\'`), or stop depending on the specific escaping style.
- **Flag to the user** any apostrophe-bearing `persist_docs` comments or snapshot
  check-col string values, since the byte-level SQL those produce changes even though
  the intended value does not. Most projects need no change here — the point is to
  confirm nothing downstream is pinned to the `''` form.

### 2. Thread through an LDAP/thrift `password` if the profile uses one (1.3→1.4, behavior)

dbt-spark 1.4 added a `password` field to the Spark profile and now actually passes it
to the Spark server on the thrift/http connection path (SSL and plain). On 1.3 no
`password` was passed — a real LDAP password never reached the server (the SSL transport
fell back to the literal `"x"`).

This only affects profiles using a **thrift/http connection** (`method: thrift` /
`method: http`) with `auth: LDAP` (or otherwise password-authenticated). For such a
profile, confirm a `password` is set as intended: from the latest track on it is
genuinely sent to the server, so an authentication that "worked" on 1.3 by accident
(because the password was ignored) may now behave differently. Projects using the local
`session` connection method are unaffected — that path opens no thrift connection and
reads no password, so there is nothing to change.

### 3. Apply the 1.4→1.8 dbt-spark changes

The rest of this migration continues from the 1.4→1.8 dbt-spark hops. Read
`../migrating-dbt-spark-1.4/SKILL.md` now and apply every change in its "Changes to
apply" section (which continues onward to the 1.6→1.8 hops, where the
`server_side_parameters` change lives) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.4→1.8 dbt-spark hops, and it can change
independently of this skill.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. Profile
validation runs during parse, so a `server_side_parameters` change that would break on
the latest track surfaces here. A clean parse (no errors, no deprecation warnings) means
the migration succeeded.

The 1.3→1.4 dbt-spark changes in this skill are **not** observable through `dbt parse`:
the `escape_single_quotes` switch only shows up in the SQL text emitted when embedding a
string literal at runtime, and the LDAP/thrift `password` change only matters when
opening a live authenticated thrift connection. Both require a live Spark session (and,
for the password case, a thrift-server-backed cluster with LDAP) to observe. Do **not**
prescribe a live `dbt run`/`dbt build`/`dbt debug` to check them — without cluster
credentials such a command would fail to connect or silently no-op. Verify these two by
code-level review against the descriptions above, not by running against a warehouse.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, or
`dbt compile`, and do not query any warehouse. Those touch data and are validated
separately. `dbt parse` is purely static and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the project root
summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in terms of the
latest release track and the category above. Keep it concise and factual — one entry per
change.
