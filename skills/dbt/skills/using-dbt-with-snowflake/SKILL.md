---
name: using-dbt-with-snowflake
description: Use when building or running a dbt project on Snowflake - authenticating the dbt service user with a key pair, least-privilege roles and the secondary-roles trap, separating raw / test / prod databases with zero-copy clones as test data, keeping warehouse cost down (pruning, caches, sizing, query tags), or writing and debugging Snowflake SQL in dbt models (QUALIFY, NULL semantics, case folding).
user-invocable: false
metadata:
  author: dbt-labs
---

# Using dbt with Snowflake

**Core principle:** Snowflake bills **warehouse running time**, not bytes scanned, and gives you **zero-copy clones** and **Time Travel** for free safety. Use both: develop and test on clones of raw data, keep raw data read-only for dbt, and make every query read and compute as little as possible.

## When to Use

- Setting up `profiles.yml`, the dbt service user, roles and databases for a Snowflake project
- Giving developers or CI a safe, cheap copy of raw data (zero-copy clones as test data sets)
- A model or test is slow or expensive on Snowflake
- Writing or debugging Snowflake-specific SQL in models (`QUALIFY`, `GROUP BY ALL`, `EXCLUDE`, NULL handling)
- Proving what a role can or cannot do, or recovering from an accidental drop or delete

**Do NOT use for:** Snowflake semantic views (use the `building-snowflake-semantic-views-with-dbt` skill), or adapter-agnostic modeling and testing (use `using-dbt-for-analytics-engineering`).

## Prerequisites

- `dbt-snowflake` installed and a `profiles.yml` target for Snowflake
- A role that can create databases, roles and users for the one-time setup (an administrator runs it, not the agent)
- Optional: the Snowflake CLI (`snow`) for ad-hoc queries and admin scripts

## Reference Guides

| Guide | Use When |
|-------|----------|
| [references/authenticating-and-least-privilege.md](references/authenticating-and-least-privilege.md) | Setting up key-pair auth, the dbt service user and role, grants; checking what a role can do |
| [references/environments-and-zero-copy-clones.md](references/environments-and-zero-copy-clones.md) | Laying out raw / test / prod databases, cloning raw data as test data, recovering with Time Travel |
| [references/controlling-cost-and-query-performance.md](references/controlling-cost-and-query-performance.md) | Finding expensive queries, pruning, joins, caches, warehouse sizing |
| [references/snowflake-sql-in-dbt-models.md](references/snowflake-sql-in-dbt-models.md) | Snowflake SQL features and pitfalls in model code |

## Rules That Matter Most

1. **Keep credentials out of the project.** `profiles.yml` reads every credential and account identifier (account, user, key path) from environment variables (`{{ env_var('SNOWFLAKE_PRIVATE_KEY_PATH') }}`), and the dbt service user authenticates with a key pair, not a password. Object names (role, warehouse, database, schema) are not secrets and may be written in the file.
2. **dbt can only read raw data.** The dbt role has `SELECT` on the raw database and owns the test and prod databases. Load raw data with a separate loader role.
3. **Make the test environment the default target.** A plain `dbt build` should never reach production; prod is an explicit `--target prod`, run from CI on the main branch.
4. **Turn off secondary roles for the dbt connection.** Otherwise the session also has the privileges of every other role granted to the user, and a "read-only" setup can write.
5. **Prove permissions with `SHOW GRANTS`, never by trying a `DELETE` or `DROP`** on real data.
6. **Read less data.** Filter on plain column ranges (no functions on the filtered column), select only needed columns, and aggregate before joining.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| A password or a local key path written into `profiles.yml` | `env_var()` for every connection value; keep the key file outside the repository |
| Testing a read-only role by running `DELETE` on a real table | `show grants to role <role>`; if a write must be exercised, use a scratch object created for the test |
| `role: read_only` in `profiles.yml` (or `use role`) assumed to make the session read-only | Secondary roles still apply; set `default_secondary_roles = ()` on the service user or run `use secondary roles none` |
| Cloning a whole schema for the test data, then dbt cannot replace the tables | Clone table by table, so the creating role owns each clone |
| `where year(order_date) = 2026` on a large table | `where order_date >= '2026-01-01' and order_date < '2027-01-01'` so micro-partitions are pruned |
| Sizing the warehouse up "to be safe" | Size up only to stop spilling or meet a deadline; otherwise it costs the same or more |
| `count(case when c then 1 else 0 end)` | `count` counts non-NULL values; use `sum(case when c then 1 else 0 end)` or drop the `else` |
| `where flag != true` | NULL rows are dropped; use `where flag is distinct from true` |
