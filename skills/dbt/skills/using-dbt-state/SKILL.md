---
name: using-dbt-state
description: Use when a user is enabling, configuring, optimizing, or debugging dbt State (the server-backed reuse mechanism that clones or skips nodes instead of rebuilding them). Use when they conflate dbt State with the `state:modified` selector or `--state` deferral. Use when asked about models rebuilding unexpectedly, views with `select *` rebuilding, volatile SQL (`current_timestamp()`, `random()`) rebuilding or not, cross-developer cloning, lag_tolerance.
metadata:
  author: dbt-labs
---

# Using dbt State

dbt State is a **server-backed reuse mechanism**. It should not be conflated with dbt's `state:modified` selector or `--state` deferral.

Before building each selected node, dbt asks the dbt State server whether the object can be **skipped** (reuse from the target schema), **cloned** (reuse from another schema), or must be **built**. It is the successor to State-Aware Orchestration, but works in dbt Core, in development, and in CI — not just Fusion in production.

dbt State is a paid product, but it does not require a dbt platform (fka dbt Cloud) subscription.

## Common Misconceptions

| Misconception | Reality |
|---|---|
| "dbt State is just `state:modified` / `--state`" | **No.** `state:modified` hashes **file contents** against a manifest *you* manage and rebuilds `state:modified+` (all descendants). dbt State manages state automatically on a server, **parses SQL into a syntax tree and compares semantic hashes**, considers **upstream data freshness**, and rebuilds a descendant **only if it actually depends on the change** (not the whole `+` subtree). |
| "It's Fusion-only / production-only" | Works in dbt **Core, the dbt platform, and Fusion**, across **dev, CI, and production**, with any orchestrator. |
| "dbt Core users can't use it" | They can. dbt Core **1.7–1.11** require `pip install dbt-state`. It's **baked into dbt Core 1.12 / v2.0 and Fusion**. |
| "It's free / it's local" | It calls the dbt State **server** and requires authentication via a **dbt platform account** or a **standalone dbt State account** ([app.state.dbt.com](https://app.state.dbt.com)). Reuse is metered in **DATTs — daily active target tables** (see Billing below). |
| "It sends my data to dbt Labs" | It sends **last-modified timestamps** and **SQL text**. The SQL is **hashed then discarded** — dbt Labs cannot read query contents after hashing, and can never access raw data. |

## How the reuse decision works

For each selected node, dbt State picks the cheapest valid option:

1. **Skip** — object exists in the **target schema**, its semantic hash is unchanged, and no parent has fresher data beyond `lag_tolerance`. Does nothing.
2. **Clone** — a matching object (same hash, fresh data) exists in **another schema** (e.g. production, or a teammate's dev schema). Clones it, marked **Reused**. Uses zero-copy clone if supported by the warehouse, or runs a CTAS statement to copy the transformed data from elsewhere if not. Test results are reused too — a **failing test still surfaces** even though it wasn't re-executed.
3. **Build** — no valid reuse. Builds normally, auto-deferring unselected upstream nodes.

If a node is selected for execution but its inputs do not exist in the target schema, dbt State uses deferral as normal. If a `manifest.json` is present it will use that, otherwise it will make a [best-effort guess](https://docs.getdbt.com/reference/resource-configs/defer-to-target#caveats-to-dbt-state-without-a-manifest) at the correct FQN based on the `generate_*_name` macros. Deferral does not consume DATTs. The `defer_to_target` config in `profiles.yml` can be used to specify which schema to defer to for self-managed users. It is not necessary for dbt platform users.

To get freshness, dbt fetches warehouse metadata (or `loaded_at_field`/`loaded_at_query`) for each input relation. For views without a `loaded_at` config, it traverses upstream until it finds a real table.

## Query normalization & why models rebuild

dbt State hashes a **parsed syntax tree**, so it ignores cosmetic changes — whitespace, comments, table aliases, `dbt lint --fix` reformatting. A model rebuilds only when its **logic or data** changes.

**Volatile SQL** (`current_timestamp()`, `getdate()`, `random()`): by default treated as **logic** — the hash uses the function *name*, not its runtime value, so it does **not** invalidate the model every run (otherwise nothing downstream of `getdate()` could ever be reused). To make a model rebuild when the value changes:
- Set `evaluate_volatile_sql: true` (preferred — covers all functions in the model, inheritable like any config). dbt State emulates the function's value into the hash.
- Or use a **Jinja** equivalent (e.g. `{{ run_started_at }}`) — Jinja renders *before* parsing, so it changes the compiled SQL each run.

**Non-deterministic Jinja** (e.g. `dbt_utils.get_relations_by_pattern` returning relations in varying order) produces a different compiled hash and triggers rebuilds even when logic is unchanged.

**Config changes:** only **build-relevant** configs affect the hash (`materialized`, `on_schema_change`, `severity`, …). Cosmetic configs (`meta`, `tags`) are ignored. If a post-hook mutates tables based on ignored fields (e.g. applying `meta` as warehouse tags), set `execute_hooks_on_any_reuse: true` so hooks run on reuse.

## Configs quick reference

Set under `models: +state:` in `dbt_project.yml`, in `schema.yml` `config.state`, or in `{{ config(state={...}) }}`.

| Config | Default | Purpose |
|---|---|---|
| `lag_tolerance` | `45m` | How stale data may be before a node is eligible to rebuild. **Data freshness only** — SQL changes rebuild regardless. |
| `require_fresh_data_from` | `any` | Whether `any` or `all` direct parents need fresh data to trigger a rebuild. |
| `evaluate_volatile_sql` | `false` | Hash the runtime *value* of volatile functions instead of the name. |
| `pre_clone` | `if_missing` | Pre-populate incremental models/snapshots by cloning prod before a run (`never` / `if_missing` / `always`). |
| `execute_hooks_on_any_reuse` | `false` | Run pre/post-hooks even when a node is reused. |
| `defer_to_target` | `prod` | (Self-managed only, profile) Which profile target to defer/clone from. |
| `metadata_warehouse` | profile `warehouse` | (Snowflake only, profile) Separate warehouse for metadata lookups. |

Supported warehouses: Snowflake, Databricks, BigQuery, Redshift.

## Billing: daily active target tables (DATT)

dbt State usage is metered in **DATTs (daily active target tables)**, not by "models built".

- A **target table** is a database object managed by your project (per database + schema): seeds, snapshots, models (incl. incremental), **and each distinct test** — even tests not stored in the database (`store_failures` off). Example: `dim_customers` with `not_null` and `unique` on `id` = **3 target tables** (the model + 2 tests).
- A target table becomes a **DATT** when dbt State performs at least one **skip, clone, or test reuse** on it on a given day (UTC). **All reuses of the same target table in one day count as a single DATT.** A full build is not a reuse.
- Views are never billed as DATTs, even if reused or cloned. Tests attached to a view will be billed as normal.

If asked about pricing details, refer the user to https://www.getdbt.com/product/dbt-state.


## Optimizations for best results

- **`lag_tolerance` per environment** — in dev, set it high (e.g. a week) so dbt does nothing when data is only slightly stale; cloning is cheap but doing nothing is cheaper. Example:
  ```yaml
  #dbt_project.yml
  models:
    +state:
      lag_tolerance: "{{ '4h' if target.name == 'prod' else '7d' }}"
  ```
- **Keep using selectors in development.** Any target table dbt State reuses **counts as a DATT** for that day (even one inside its lag-tolerance window). Select only the nodes you're working on so plain deferral handles the rest — untouched, unselected nodes incur no dbt State usage.
- **Reduce complex selector usage in production.** dbt State makes most jobs collapse toward plain `dbt build`; let it decide what to rebuild instead of hand-tuning per-job selection. Specify lag_tolerance to prevent overbuilding.
- **Specify columns instead of `select *` to increase likelihood of reuse**. If dbt State can't prove a `table.*` or similar has the same column set, it will rebuild to be sure. This is particularly relevant for views. Fusion's static analysis is not currently used for this.

## Diagnosing confusing behavior

| Symptom | Cause / fix |
|---|---|
| A model with `current_timestamp()` keeps rebuilding | Likely `evaluate_volatile_sql: true` somewhere, or a Jinja value (e.g. `run_started_at`) changing the compiled SQL. If you *want* reuse, leave volatile SQL as default (logic). |
| Model rebuilds despite "no change" | Cosmetic change isn't the cause (those are normalized away). Look for non-deterministic Jinja (unordered macro output), a build-relevant config change, or fresher upstream data past `lag_tolerance`. Metadata tables can consider a table modified by an insert command even if no new rows were added. Consider using `loaded_at_field`, but this may be more costly in the warehouse - metadata queries are often free but `loaded_at_field` will be a standard paid query. |
| Post-hooks didn't run on a reused model | Hooks don't run on reuse by default — set `execute_hooks_on_any_reuse: true`. |
| Want to know *why* a node was reused/rebuilt | Use the **`dbt-state explain`** command (dbt v1.7–1.12) to inspect the decision. |
| Need authentication / access | Log in via your **dbt platform** account or a **standalone dbt State** account. For an org, set `state-org-id` under `dbt-cloud:` in `dbt_project.yml`. |

## v1 (Python) vs v2 (Rust/Fusion)

| | dbt Core 1.7–1.11 | dbt Core 1.12 / v2.0 | Fusion |
|---|---|---|---|
| Install | `pip install dbt-state` required | Built in | Built in |

- dbt v1.7-1.11 users must install the separate `dbt-state` package to use dbt State. 
- dbt v1.12+ users have the `dbt-state` package included automatically.
- dbt v2.0+ (either Core or Fusion distributions) have the Rust implementation of the client logic built in, so no separate install is needed.

The reuse behavior, configs, and query normalization are server-side and behave consistently across all engines. The main v1 difference is the separate `dbt-state` install for 1.7–1.11. The `dbt-state explain` diagnostic is not available in dbt v2.

## Related docs

- Overview: `/docs/deploy/dbt-state-about`
- Setup: `/docs/deploy/dbt-state-setup` · Examples: `/docs/deploy/dbt-state-examples`
- Monitor activity: `/docs/deploy/dbt-state-interface` · Deferral: `/docs/deploy/dbt-state-deferral` · CI/CD: `/docs/deploy/dbt-state-cicd`
- Configs: `/reference/resource-configs/dbt-state-configs` · `lag_tolerance` · `defer_to_target`
