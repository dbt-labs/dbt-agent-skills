---
name: working-with-dbt-mesh
description: Implements dbt Mesh governance features (model contracts, access modifiers, groups, versioning) and multi-project collaboration with cross-project refs. Use when implementing dbt Mesh governance, setting up cross-project refs with dependencies.yml, disambiguating similarly-named models across projects, or splitting a monolithic dbt project into multiple mesh projects.
metadata:
  author: dbt-labs
  user-invocable: false
---

# Working with dbt Mesh

**Core principle:** In a mesh project, upstream data comes through `ref()`, not `source()`. Every cross-project reference requires the project name. When in doubt, read `dependencies.yml` first.

## When to Use

- Working in a dbt project that references models from other dbt projects
- Resolving ambiguity when multiple upstream projects have similarly-named models (e.g. multiple `stg_` models)
- Adding model contracts, access modifiers, groups, or versioning
- Setting up cross-project references with `dependencies.yml`
- Splitting a monolithic dbt project into multiple mesh projects

**Do NOT use for:**

- General model building or debugging (use the `using-dbt-for-analytics-engineering` skill)
- Unit testing models (use the `adding-dbt-unit-test` skill)
- Semantic layer work (use the `building-dbt-semantic-layer` skill)

## First: Orient Yourself in a Multi-Project Setup

Before writing or modifying any SQL in a project that uses dbt Mesh, follow these steps:

### 1. Read `dependencies.yml`

This file at the project root tells you which upstream projects exist:

```yaml
# dependencies.yml
projects:
  - name: core_platform
  - name: marketing_platform
```

If this file has a `projects:` key, you are in a multi-project mesh setup. Every model you reference from those upstream projects **must** use cross-project `ref()`.

### 2. Understand how upstream data gets into this project

In a mesh setup, upstream project models replace what would alternatively be sources:

| Alternative | Mesh multi-project |
|---|---|
| `{{ source('stripe', 'payments') }}` | `{{ ref('core_platform', 'stg_payments') }}` |
| Data comes from raw database tables | Data comes from another dbt project's public models |
| Defined in `sources.yml` | Declared in `dependencies.yml` |

The upstream project has already staged and transformed the raw data. Your project builds on top of their public models, not their raw sources.

### 3. Disambiguate similarly-named models

When multiple upstream projects have models with the same name (e.g. `stg_customers` in both `core_platform` and `marketing_platform`), you **must** use the two-argument `ref()`:

```sql
-- Correct: explicit project name, no ambiguity
select * from {{ ref('core_platform', 'stg_customers') }}
select * from {{ ref('marketing_platform', 'stg_customers') }}

-- WRONG: dbt cannot determine which project's stg_customers you mean
select * from {{ ref('stg_customers') }}
```

### 4. Check existing patterns in the codebase

Before writing new SQL:
- Search for existing two-argument `ref()` calls to see which upstream projects and models are already in use
- Look at the upstream project's YAML for `access: public` models — only these are referenceable cross-project
- The first argument of `ref()` must exactly match the `name` field in the upstream project's `dbt_project.yml` (case-sensitive)

### 5. Know what you can and cannot reference

| Upstream model access | Can you `ref()` it cross-project? |
|---|---|
| `access: public` | Yes |
| `access: protected` (default) | No — only within the same project |
| `access: private` | No — only within the same group |

If you need a model that isn't `public`, coordinate with the upstream team to widen its access.

## Cross-Project Refs Require dbt Cloud Enterprise

Cross-project `ref()` and the `projects:` key in `dependencies.yml` are only available on **dbt Cloud Enterprise or Enterprise+** plans. Before setting up any cross-project collaboration, verify plan eligibility:

1. **If `dependencies.yml` already has a `projects:` key and the project is actively using cross-project refs** — Enterprise is already in place. Proceed.
2. **Otherwise** — ask the user to confirm they are on dbt Cloud Enterprise or Enterprise+ before adding `projects:` to `dependencies.yml` or writing new two-argument `ref()` calls.

If the user cannot confirm the plan level, or confirms they are on a plan below Enterprise, **do not set up cross-project refs**. Explain that this feature requires upgrading to Enterprise or Enterprise+ and suggest they use the intra-project governance features (groups, access modifiers, contracts) instead.

## Cross-Project `ref()` Syntax

```sql
-- Reference an upstream model (latest version)
select * from {{ ref('upstream_project', 'model_name') }}

-- Reference a specific version
select * from {{ ref('upstream_project', 'model_name', v=2) }}
```

For full cross-project setup details (dependencies.yml, prerequisites, orchestration), see [references/cross-project-collaboration.md](references/cross-project-collaboration.md).

## Governance Features

dbt Mesh includes four governance features. These work independently and can be adopted incrementally:

| Feature | Purpose | Key Config | Reference |
|---------|---------|------------|-----------|
| **Model Contracts** | Guarantee column names, types, and constraints at build time | `contract: {enforced: true}` | [references/model-contracts.md](references/model-contracts.md) |
| **Groups** | Organize models by team/domain ownership | `group: finance` | [references/groups-and-access.md](references/groups-and-access.md) |
| **Access Modifiers** | Control which models can `ref` yours | `access: public / protected / private` | [references/groups-and-access.md](references/groups-and-access.md) |
| **Model Versions** | Manage breaking changes with migration windows | `versions:` with `latest_version:` | [references/model-versions.md](references/model-versions.md) |

### YAML placement rule

In model property YAML files, `access`, `group`, and `contract` are **configs** and must always be nested under the `config:` key — never placed as top-level model properties. Placing them at the top level may appear to work in dbt Core but causes parse errors in dbt's Fusion engine.

```yaml
# ✅ CORRECT — all governance configs under `config:`
models:
  - name: fct_orders
    config:
      group: finance
      access: public
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: int

# ❌ WRONG — governance configs as top-level properties (breaks Fusion)
models:
  - name: fct_orders
    access: public          # WRONG — not under config:
    group: finance          # WRONG — not under config:
    contract:               # WRONG — not under config:
      enforced: true
    columns:
      - name: order_id
        data_type: int
```

This applies to property YAML files only. In `dbt_project.yml`, use the `+` prefix for directory-level assignment (e.g. `+group: finance`, `+access: private`). In SQL files, use `{{ config(access='public', group='finance') }}`.

### Adoption order

```
1. Groups & Access  →  2. Contracts  →  3. Versions  →  4. Cross-Project Refs
   (organize teams)     (lock shapes)    (manage changes)  (split projects)
```

- **Groups & Access** — no schema changes needed, start here
- **Contracts** — require declaring every column and data type in YAML
- **Versions** — only needed when a contracted model must introduce a breaking change
- **Cross-Project Refs** — require **dbt Cloud Enterprise or Enterprise+** and a successful upstream production job. Do not set up cross-project refs if you cannot confirm the plan level is Enterprise or higher.

## Contracts vs. Tests

| | Contracts | Data Tests |
|---|---|---|
| **When** | Build-time (pre-flight) | Post-build (post-flight) |
| **What** | Column names, data types, constraints | Data quality, business rules |
| **Failure** | Model does not materialize | Model exists but test fails |
| **Use for** | Shape guarantees for downstream consumers | Content validation and anomaly detection |

Contracts are enforced **before** tests run. If a contract fails, the model is not built, and no tests execute.

## Decision Framework

### Should this model have a contract?

Use a contract when:
- The model is `access: public` (especially if referenced cross-project)
- Other teams depend on this model's schema stability
- The model feeds an exposure (dashboard, ML pipeline, reverse ETL)
- External consumers (other dbt projects, BI dashboards, reverse ETL) query the table directly and would break from column renames or removals

Do NOT add a contract when:
- **Staging models** (`stg_*`) — these are internal implementation details, not consumer-facing APIs
- **The model is still evolving** — if the user says they are iterating on the design, advise waiting until the schema stabilizes
- **No external consumers exist** — in a single-project setup with no cross-project refs, no BI tools depending on the schema, and no exposures, contracts add maintenance overhead without benefit. Ask about consumers before recommending contracts.
- **Dynamic/pivot columns** — models that use `pivot()`, `unpivot()`, or dynamically generate columns are poor candidates because the column list isn't fixed and the contract will break whenever the dynamic values change
- **Ephemeral models** — contracts are not supported on ephemeral materializations

**If the user asks for a contract on a model that matches the "do NOT add" criteria above, advise against it and explain why.** Do not simply comply — the user may not realize the contract is inappropriate. Suggest alternatives (e.g., data tests for staging models, waiting for schema stability, or switching materialization for ephemeral models).

### Should this model be versioned?

Version a model when:
- It has an enforced contract AND you need to introduce a breaking change (column removal, rename, type change)
- Downstream consumers need a migration window before the old shape goes away

Do NOT version a model:
- For additive changes (new columns) — these are non-breaking
- For bug fixes — fix in place
- Preemptively "just in case" — version only when a breaking change is actually needed

### What access level should this model have?

```
Is it referenced cross-project?
  └─ Yes → public (with contract recommended)
  └─ No
      Is it referenced outside its group?
        └─ Yes → protected (default)
        └─ No
            Is it internal to a small team?
              └─ Yes → private
              └─ No → protected (default)
```

**Best practice:** Default new models to `private` and widen access only when needed. The default `protected` is permissive — be intentional.

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| Using single-argument `ref()` in multi-project setups | Ambiguous — dbt may not resolve to the intended project | Always use `ref('project_name', 'model_name')` for cross-project refs |
| Using `source()` for upstream project data | In mesh, upstream data comes through public models, not raw sources | Use `ref('upstream_project', 'model_name')` instead |
| Not reading `dependencies.yml` first | You won't know which upstream projects exist or what they're called | Always read `dependencies.yml` before writing cross-project SQL |
| Making all models `public` | Exposes internal implementation details cross-project | Only mark models `public` that are intentional APIs for other teams |
| Skipping contracts on public models | Downstream consumers can break silently when schema changes | Always enforce contracts on `access: public` models |
| Versioning for non-breaking changes | Creates unnecessary maintenance burden and warehouse cost | Only version for breaking changes (column removal, type change, rename) |
| Forgetting `dependencies.yml` | Cross-project refs fail without declaring the upstream project | Add upstream project to `dependencies.yml` before using two-argument `ref()` |
| Referencing non-public models cross-project | Only `public` models are available to other projects | Set `access: public` on models intended for cross-project consumption |
| Placing `access`, `group`, or `contract` as top-level model properties in YAML | Breaks Fusion engine parsing; top-level placement is not valid config | Always nest under `config:` — e.g. `config: { access: public }` |
| Adding contracts to staging models | Staging models are internal — contracts add friction without protecting external consumers | Advise against it; suggest data tests instead |
| Adding contracts to models with dynamic/pivot columns | Column list changes with data, breaking the contract | Advise against it; explain why the column list isn't fixed |
| Adding contracts without establishing external consumers | Contracts protect a schema boundary — no consumers means no boundary to protect | Ask who depends on this model before adding a contract |
| Making a model `private` that is already referenced outside its group | Existing refs break with a `DbtReferenceError` | Widen access to `protected` or refactor callers into the same group first |
| Setting up cross-project refs without confirming dbt Cloud Enterprise | Cross-project `ref()` is unavailable on lower plan tiers | Confirm the plan level before adding `projects:` to `dependencies.yml` or writing two-argument `ref()` calls |
| Adding `dependencies.yml` without a successful upstream production job | dbt Cloud resolves cross-project refs via the upstream `manifest.json` — no job run means no manifest | Run at least one successful production deployment in the upstream project first |
