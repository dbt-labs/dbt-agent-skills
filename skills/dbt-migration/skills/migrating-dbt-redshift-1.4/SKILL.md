---
name: migrating-dbt-redshift-1.4
description: Use when migrating a dbt project that uses the dbt-redshift adapter from 1.4 to the latest release track (entry point 1.8). Covers the dbt-redshift-adapter-specific changes only (removed profile fields, adapter parent class, connect_timeout, sslmode remap, autocommit) — apply it alongside the core migrating-dbt-1.4 skill, which handles the dbt-core changes.
metadata:
    fromVersion: '1.4'
    toVersion: '1.8'
---

# Migrate the dbt-redshift adapter from 1.4 to the latest release track

You are upgrading the **dbt-redshift-adapter-specific** parts of a dbt project that
currently targets dbt-redshift **1.4**, on its way to **1.8** (the entry point of the
latest release track). A 1.4 project takes four hops to reach 1.8 (1.4→1.5, 1.5→1.6,
1.6→1.7, 1.7→1.8), so this migration applies the redshift changes from every hop.

This skill is **adapter-specific and complements the core `migrating-dbt-1.4` skill** —
it does not repeat the dbt-core changes. For a full migration, apply both.

The 1.4→1.5 hop is where dbt-redshift switched its driver from **psycopg2 to
redshift_connector** and `RedshiftCredentials` stopped subclassing `PostgresCredentials`.
That single rewrite is the root of most of the cases below. Most are adapter-internal
behavior shifts, not project-code edits — apply a change only where the project actually
exercises it (a set connection field, an overridden adapter macro, or custom Python that
subclasses the adapter). Work through `profiles.yml`, `dbt_project.yml`, `macros/`, and
any Python plugin/hook code.

## Changes to apply

### 1. Remove `iam_duration_seconds`, `search_path`, `keepalives_idle` profile fields (1.4→1.5, breaking)

These three fields existed on `RedshiftCredentials` through 1.4 (inherited from
`PostgresCredentials`) and are **gone at 1.5**, when `RedshiftCredentials` stopped
subclassing `PostgresCredentials`. Remove any of them from the `outputs` blocks in
`profiles.yml`:

- `iam_duration_seconds` — no replacement on the redshift_connector path.
- `search_path` — no replacement; set the search path via a different mechanism if you
  relied on it.
- `keepalives_idle` — no replacement; TCP keepalive tuning is no longer a profile field.

**Critical verification caveat:** dbt-redshift **silently ignores unknown profile keys**
— leaving any of these three in `profiles.yml` on 1.5+ produces **no error and no
warning** (`dbt debug` still reports "All checks passed!"). So this is a *silent no-op*,
not a loud failure: the field is simply dropped and any behavior it configured is lost.
Do not rely on `dbt debug` to catch a leftover field — you must remove them by
inspection. Confirm the field set at the source level (see Verify).

### 2. Adapter parent class changed from `PostgresAdapter` to `SQLAdapter` (1.4→1.5, breaking)

Through 1.4, `RedshiftAdapter` (`dbt/adapters/redshift/impl.py`) derived from
`PostgresAdapter`; from 1.5 it derives from `SQLAdapter` directly and the
`dbt.adapters.postgres` import is removed. The MRO changes from
`RedshiftAdapter → PostgresAdapter → SQLAdapter → BaseAdapter → object` to
`RedshiftAdapter → SQLAdapter → BaseAdapter → object`.

This is a **Python-internals change, not expressible as project YAML/SQL**. It only needs
action if the project has custom code (dispatch macros, plugins, or monkeypatches) that
assumes Redshift inherits Postgres adapter behavior — e.g. importing
`dbt.adapters.postgres` or calling a `postgres__`-prefixed adapter method expecting it to
resolve through Redshift's inheritance. Find any such code and rework it to target
`SQLAdapter`/redshift-native behavior. A project with no such custom code needs no edit.

### 3. `connect_timeout` default changed (1.4→1.5, behavior)

Through 1.4, `connect_timeout` was inherited from `PostgresCredentials` with default
`10` (seconds, passed to psycopg2). At 1.5 a redshift-native
`connect_timeout: Optional[int] = None` field replaces it (passed to redshift_connector
as `timeout`), so the default becomes **unset** — the driver's own default applies. If
your project relied on the implicit 10-second timeout, set `connect_timeout` explicitly
in `profiles.yml` to keep the old behavior; otherwise no edit is needed.

> Boundary note (source vs Notion): the migration doc describes a "30-second
> `connect_timeout` default introduced at 1.5". Adapter source does **not** show a 30s
> default — it shows `10` (≤1.4, psycopg2) → `None` (1.5, redshift_connector). The "30s"
> value is unconfirmed and may reflect the redshift_connector driver's own internal
> default rather than a dbt-set value. Treat the change as "default 10 → unset"; flag to
> the user if a specific timeout matters.

### 4. `sslmode` `require`/`allow`/`prefer` now map to `verify-ca` (1.4→1.5, breaking)

With the redshift_connector rewrite, dbt-redshift introduced a `SSL_MODE_TRANSLATION`
map (`dbt/adapters/redshift/connections.py`) that collapses `allow`/`prefer`/`require`
to `verify-ca`, maps `disable` to no SSL, and leaves `verify-full` as-is. This means
`sslmode: require` now **enforces CA certificate verification** — a stricter behavior
that will **break the connection if the cluster's cert chain is not trusted** by the
client.

If `profiles.yml` sets `sslmode` to `require`, `allow`, or `prefer`, confirm the
cluster's CA chain is trusted (or provide the appropriate CA bundle). If you specifically
need the old non-verifying behavior, that mode no longer exists — decide between
`verify-ca`/`verify-full` (with proper certs) or `disable` (no SSL) with the user. No
project edit is required if `require` already connects cleanly against your cluster, but
the stricter semantics should be verified against a live connection before cutover.

> Boundary note (source vs Notion): the migration doc places this at 1.5→1.6. Adapter
> source shows the `SSL_MODE_TRANSLATION` map is **absent on 1.4** (import fails) and
> present and identical in **both 1.5 and 1.6**, so the change actually lands at 1.4→1.5.
> It is documented here at the hop where it is crossed.

### 5. Autocommit enabled by default (1.4→1.5, behavior)

At 1.5 an `autocommit` field was added to `RedshiftCredentials` with default `True`
(`autocommit: Optional[bool] = True`) and applied on the live connection. Before 1.5
there was no `autocommit` field (the psycopg2 path defaulted autocommit off). So DDL/DML
that previously ran inside an implicit transaction now **auto-commits by default** — a
mid-run error no longer rolls back statements that already ran.

If the project (or a custom materialization/hook) depended on statements being wrapped in
a rollback-able transaction, set `autocommit: false` explicitly in `profiles.yml` to
restore the old behavior. Otherwise no edit is needed — just be aware of the changed
transaction semantics.

> Boundary note (source vs Notion): the migration doc places this at 1.5→1.6. Adapter
> source shows the `autocommit` field is **absent on 1.4** and present with default
> `True` in **both 1.5 and 1.6**, so the change actually lands at 1.4→1.5. It is
> documented here at the hop where it is crossed.

### 6. Apply the 1.5→1.8 redshift changes

The rest of this migration continues from the 1.5→1.8 hop. Read
`../migrating-dbt-redshift-1.5/SKILL.md` now and apply every change in its "Changes to
apply" section (the Redshift-native rewrite of `list_relations_without_caching`, then the
1.6→1.8 redshift hops it chains onward to) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.5→1.8 redshift hops, and it can change
independently of this skill.

## Verify

Most of these are connection/runtime behaviors, not static-parse concerns, so `dbt parse`
alone will **not** exercise them. Verify at the lowest-cost level that actually observes
each change:

- **Removed profile fields (Change 1):** `dbt debug` is **not** a reliable probe — it
  silently passes with the removed fields still present. Instead confirm the field set at
  the source level against the target adapter version (no warehouse needed):
  ```bash
  python -c "import dataclasses; from dbt.adapters.redshift.connections import RedshiftCredentials as C; \
      names={f.name for f in dataclasses.fields(C)}; \
      print({n: n in names for n in ['iam_duration_seconds','search_path','keepalives_idle']})"
  ```
  Expect all `False` on 1.5+. Then grep `profiles.yml` to confirm you removed them.
- **Adapter parent class (Change 2):** source-level, no warehouse:
  ```bash
  python -c "from dbt.adapters.redshift.impl import RedshiftAdapter; print(RedshiftAdapter.__mro__)"
  ```
  Expect `PostgresAdapter` absent on 1.5+. The real check is that any custom code no
  longer depends on Postgres inheritance.
- **`connect_timeout` / autocommit defaults (Changes 3, 5):** inspect the dataclass field
  defaults the same way (`[f.default for f in dataclasses.fields(C) if f.name=='...']`).
  The runtime effect (socket timeout, transaction rollback) is **only observable against
  a live warehouse** — if credentials are unavailable, verify at the source/dataclass
  level and note the runtime behavior was not exercised.
- **`sslmode` remap (Change 4):** the `require`→`verify-ca` negotiation is **only
  observable against a live cluster** (`dbt debug`/`dbt run` succeeding or failing on cert
  trust). Without warehouse credentials, confirm the translation map exists at the source
  level and flag that the live cert-trust behavior must be checked before cutover:
  ```bash
  python -c "from dbt.adapters.redshift.connections import SSL_MODE_TRANSLATION as m; print({str(k):str(v) for k,v in m.items()})"
  ```
- Run `dbt parse` after all edits to confirm the project still parses cleanly. A clean
  parse does not prove the redshift behavior changes are handled.

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
