# The semantic_view Materialization: Config, Tests, Grants

The `Snowflake-Labs/dbt_semantic_view` package adds the `semantic_view` materialization. The model body is the semantic view definition after its name; dbt compiles it to `CREATE SEMANTIC VIEW`. The package passes the SQL through, so new Snowflake clauses work without a package upgrade.

## Folder and naming

- Keep semantic views in their own folder (`models/marts/semantic_views/`) with their own YAML file, and a prefix such as `sv_`.
- Reference a semantic view built by dbt with `ref()`; one created outside dbt with `source()`.

## Config options

| Option | Default | Use |
|---|---|---|
| `copy_grants` | `false` | keep grants when the view is replaced; applies to `CREATE OR REPLACE` only |
| `create_or_alter` | `false` | `CREATE OR ALTER` instead of `CREATE OR REPLACE`: non-destructive, keeps materializations and grants across runs; cannot be combined with `COPY GRANTS` |
| `max_staleness` | none | adds `MAX_STALENESS`; required with `sv_materializations`; do not also write the clause in the model body |
| `sv_materializations` | none | a YAML specification of the view's materializations |

**Warning:** `CREATE OR REPLACE` drops and recreates the view, which removes every materialization attached to it. Always set `create_or_alter=true` when you use `sv_materializations`.

## Materializations

```sql
{%- set sv_materializations_yaml -%}
materializations:
  - name: revenue_by_segment
    warehouse: {{ target.warehouse }}
    dimensions: [ { table: customers, name: customer_segment } ]
    metrics:    [ { table: orders,    name: total_revenue } ]
    filter_clause: "WHERE (orders.order_month >= '2025-01-01')"   # optional
{%- endset -%}

{{ config(
    materialized='semantic_view',
    create_or_alter=true,
    max_staleness='<staleness>',
    sv_materializations=sv_materializations_yaml
) }}
```

- On every run the package compares the declared materializations with the existing ones and adds, updates or drops only what changed.
- Build the YAML in a `{% set %}` block when it needs Jinja (the warehouse from the target, an environment variable).
- `filter_clause` starts with `WHERE (…)`; the query planner uses the materialization when a query's filter matches it or is stricter.
- `immutable_where` excludes rows that never change from refresh. It must use the materialization's **output column name**, that column must be one of its dimensions, and it cannot be combined with `filter_clause` on the same materialization.
- `refresh_mode` is ignored in the YAML; set it with `ALTER SEMANTIC VIEW … ADD MATERIALIZATION … REFRESH_MODE = …` instead.
- The package documents `max_staleness` as a string such as `'1 hour'`, while the Snowflake DDL reference documents `MAX_STALENESS` in seconds (minimum 120); check which form your Snowflake version accepts.

## Tests

The package ships two generic tests:

```yaml
models:
  - name: sv_order_economics
    data_tests:
      - dbt_semantic_view.materialization_exists:
          arguments: { materialization_name: revenue_by_segment }
      - dbt_semantic_view.materialization_is_active:
          arguments: { materialization_name: revenue_by_segment }
```

Add singular tests that compare the view with its inputs:

```sql
-- tests/sv_order_economics_revenue_matches_fact.sql
select 'mismatch' as failure
where (select sum(amount) from {{ ref('fct_orders') }})
      is distinct from
      (select total_revenue from semantic_view({{ ref('sv_order_economics') }} metrics orders.total_revenue))
-- is distinct from, not !=: with != a NULL on either side makes the test pass silently
```

A grand total cannot catch a ratio or a distinct count that is wrong per month, so test each non-additive metric at the grain it is used at:

```sql
-- tests/sv_order_economics_avg_order_value_by_month.sql
with from_view as (
    select order_month, avg_order_value
    from semantic_view({{ ref('sv_order_economics') }} dimensions orders.order_month metrics avg_order_value)
),
from_fact as (
    select date_trunc('month', order_date) as order_month,
           sum(amount) / nullif(count(distinct order_id), 0) as avg_order_value
    from {{ ref('fct_orders') }}
    group by 1
)
select coalesce(v.order_month, f.order_month) as order_month, v.avg_order_value as in_view, f.avg_order_value as in_fact
from from_view v
full outer join from_fact f
    on v.order_month = f.order_month
where v.avg_order_value is distinct from f.avg_order_value   -- also catches a month that exists on one side only
```

```sql
-- tests/sv_order_economics_has_comment.sql
select 'missing comment' as failure
where get_ddl('SEMANTIC_VIEW', '{{ ref('sv_order_economics') }}') not ilike '%comment%=%''order economics%'
-- ilike ignores case; the % around = allows spaces
```

## Grants and documentation

- **`persist_docs` does not apply:** model and column descriptions in dbt YAML do not reach the Snowflake object. Write descriptions in `comment = '…'` clauses in the model body; keep the YAML description for dbt docs.
- **Grants:** `+grants` may not cover semantic views. Use `copy_grants`, `create_or_alter`, or a `post_hook`: `grant select on semantic view {{ this }} to role <reader_role>`.
- **BI tools:** some tools list only tables and views. Check that the consuming tool can see semantic views before promising it.
- **Logging:** set `LOG_EVENT_LEVEL` on a materialization with a `post_hook`, for example `alter semantic view {{ this }} alter materialization <name> set log_event_level = 'INFO'`.
