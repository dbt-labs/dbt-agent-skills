# Cross-Project Collaboration

Cross-project collaboration allows downstream dbt projects to reference public models from upstream projects without installing their full source code. This is the core multi-project capability of dbt Mesh.

**Requirement:** dbt Cloud Enterprise (or dbt Cloud Enterprise+) is required for cross-project refs. Model governance features (contracts, access, groups, versions) work in dbt Core and all dbt Cloud tiers.

## Prerequisites

Before a downstream project can reference upstream models:

### Upstream Project

1. Models must have `access: public` (recommended: with `contract: {enforced: true}`)
2. At least one **successful production deployment job** must have run (generates the `manifest.json` metadata that dbt Cloud uses to resolve cross-project refs)
3. For Staging environments, a successful staging deployment job is also needed

### Downstream Project

1. The upstream project must be declared in `dependencies.yml`
2. SQL must use two-argument `ref()`: `ref('project_name', 'model_name')`

## Configuring `dependencies.yml`

Create `dependencies.yml` at the root of your downstream project:

```yaml
# dependencies.yml
projects:
  - name: core_platform  # Must exactly match the upstream project's dbt_project.yml 'name' field
```

You can combine project dependencies with package dependencies:

```yaml
# dependencies.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1

projects:
  - name: core_platform
  - name: marketing_platform
```

**The `name` field is case-sensitive** and must exactly match the `name` in the upstream project's `dbt_project.yml`.

## Using Cross-Project `ref()`

Reference upstream public models using the two-argument form:

```sql
-- models/marts/fct_combined_orders.sql
with platform_orders as (
    select * from {{ ref('core_platform', 'fct_orders') }}
),

marketing_attributions as (
    select * from {{ ref('marketing_platform', 'fct_attributions') }}
)

select
    p.order_id,
    p.customer_id,
    p.order_total,
    m.campaign_id,
    m.attribution_type
from platform_orders p
left join marketing_attributions m
    on p.order_id = m.order_id
```

### Referencing Versioned Models Cross-Project

```sql
-- Pin to a specific version
select * from {{ ref('core_platform', 'fct_orders', v=1) }}

-- Use the latest version (default)
select * from {{ ref('core_platform', 'fct_orders') }}
```

## Disambiguating Similarly-Named Models

When multiple upstream projects have models with the same name (e.g. `stg_customers`), the two-argument `ref()` resolves the ambiguity:

```sql
-- These are two different models from two different projects
with core_customers as (
    select * from {{ ref('core_platform', 'stg_customers') }}
),

marketing_customers as (
    select * from {{ ref('marketing_platform', 'stg_customers') }}
)

select ...
```

**Without the project argument, dbt cannot determine which `stg_customers` you mean** and will raise an error.

## Advantages Over Package Dependencies

| Aspect | Cross-Project Refs | Package Dependencies |
|--------|-------------------|----------------------|
| Code installed | Metadata only | Full source code |
| Can accidentally build upstream | No | Yes (common mistake) |
| Parse time impact | Minimal | Increases with package size |
| Model renames | Auto-resolved via metadata | Breaks downstream refs |
| Schema changes | Auto-resolved | Breaks downstream refs |

## Cross-Project Orchestration

### Job Completion Triggers

In dbt Cloud, configure downstream jobs to trigger when upstream jobs complete:

1. Go to the downstream project's job settings
2. Under **Triggers**, select **Job Completion**
3. Choose the upstream project and job that should trigger this job

This ensures downstream models always build against fresh upstream data.

### Staging Environment Protection

When both projects have staging environments configured, dbt Cloud automatically resolves cross-project refs against the staging environment's metadata — preventing staging development from reading production data.

## Bidirectional Dependencies

Two projects can depend on each other (e.g. `finance` uses models from `marketing` AND `marketing` uses models from `finance`). dbt allows this as long as there are no **node-level cycles**.

```
finance/fct_revenue → marketing/dim_campaigns  ✅ OK (project-level cycle)
finance/fct_revenue → marketing/dim_campaigns → finance/fct_revenue  ❌ Node-level cycle
```

When establishing bidirectional dependencies, deploy projects sequentially to build up the metadata each project needs to resolve the other's refs.

## Multi-Project Testing

You can write singular tests that reference models from different projects:

```sql
-- tests/assert_orders_have_valid_campaigns.sql
select *
from {{ ref('core_platform', 'fct_orders') }} o
left join {{ ref('marketing_platform', 'dim_campaigns') }} c
    on o.campaign_id = c.campaign_id
where o.campaign_id is not null
    and c.campaign_id is null
```

## Exploring Upstream Models

When working in a downstream project and you need to understand what's available upstream:

1. **Check `dependencies.yml`** for declared upstream projects
2. **Use the dbt Cloud Catalog** (if available) to browse public models across all projects
3. **Use `dbt ls`** to list available models:
   ```bash
   # List all models available from an upstream project
   dbt ls --resource-type model --output-keys name,access --select source:core_platform+
   ```
4. **Check upstream YAML files** for `access: public` models and their contract definitions

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using single-argument `ref()` for cross-project models | Always use `ref('project_name', 'model_name')` |
| Mismatched project name in `dependencies.yml` | Must exactly match the upstream `dbt_project.yml` `name` (case-sensitive) |
| No production job run in upstream project | Run at least one successful production deployment job before referencing |
| Referencing non-public upstream models | Only `access: public` models are available cross-project |
| Using `packages.yml` instead of `dependencies.yml` for project deps | Cross-project refs use `dependencies.yml`, not `packages.yml` |
| Forgetting to set up job completion triggers | Without orchestration, downstream may build against stale upstream data |
