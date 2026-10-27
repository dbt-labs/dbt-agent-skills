---
name: building-snowflake-semantic-views-with-dbt
description: Use when creating, changing or testing Snowflake semantic views from a dbt project with the semantic_view materialization (Snowflake-Labs/dbt_semantic_view) - writing TABLES, RELATIONSHIPS, FACTS, DIMENSIONS and METRICS, designing additive, distinct-count and ratio metrics, querying with SEMANTIC_VIEW(), configuring create_or_alter, copy_grants, max_staleness or materializations, and reconciling the metrics with their base tables. Not for the dbt Semantic Layer (MetricFlow).
user-invocable: false
metadata:
  author: dbt-labs
---

# Building Snowflake Semantic Views with dbt

**Core principle:** a Snowflake semantic view stores business meaning - tables, keys, relationships, facts, dimensions and metrics - as one object, and computes metrics **at query time, at the grain the query asks for**. Define every non-additive metric (a ratio, a distinct count) once, in the view, from its additive parts; never store it pre-aggregated and roll it up again.

## When to Use

- Creating or changing a Snowflake semantic view in a dbt project
- Deciding how a KPI should be defined: additive, distinct count, ratio, or a corrected metric next to the as-reported one
- Querying a semantic view from a downstream dbt model
- Adding materializations, grants or comments to a semantic view built by dbt
- Testing that a semantic view returns the same numbers as its base tables

**Do NOT use for:** the dbt Semantic Layer / MetricFlow (use `building-dbt-semantic-layer`), or general Snowflake setup (use `using-dbt-with-snowflake`).

## Prerequisites

- dbt with `dbt-snowflake`, and the package in `packages.yml` (check [the package page](https://hub.getdbt.com/Snowflake-Labs/dbt_semantic_view/latest/) for the current version), then `dbt deps`:

  ```yaml
  packages:
    - package: Snowflake-Labs/dbt_semantic_view
      version: [">=1.0.3", "<2.0.0"]
  ```

- The dbt role has `CREATE SEMANTIC VIEW` on the target schema and `SELECT` on every table the view uses.
- The tables the view uses are clean at their declared grain: unique keys, deduplicated. A semantic view aggregates duplicates faithfully; it does not repair grain.

## Reference Guides

| Guide | Use When |
|-------|----------|
| [references/semantic-view-ddl-and-querying.md](references/semantic-view-ddl-and-querying.md) | Writing the clauses of the view, querying it with `SEMANTIC_VIEW()` |
| [references/designing-semantic-view-metrics.md](references/designing-semantic-view-metrics.md) | Choosing additive, distinct-count and ratio metrics; corrections; reconciling with a BI tool |
| [references/semantic-view-materialization-config.md](references/semantic-view-materialization-config.md) | Model structure, config options, materializations, tests, grants and documentation |

## A semantic view as a dbt model

```sql
-- models/marts/semantic_views/sv_order_economics.sql
{{ config(materialized='semantic_view') }}

tables (
    customers as {{ ref('dim_customers') }} primary key (customer_id),
    orders    as {{ ref('fct_orders') }}    primary key (order_id)
)
relationships (
    orders_to_customer as orders (customer_id) references customers (customer_id)
)
facts (
    orders.order_amount as orders.amount
)
dimensions (
    customers.customer_segment as customers.segment,
    orders.order_month         as date_trunc('month', orders.order_date)
)
metrics (
    orders.total_orders       as count(distinct orders.order_id),
    orders.total_revenue      as sum(orders.order_amount),
    avg_order_value           as orders.total_revenue / orders.total_orders
)
comment = 'Order economics: revenue, orders and average order value'
```

- Use `ref()` and `source()` for every table, so lineage and build order are right.
- `avg_order_value` is a **derived metric**: no table prefix, built from other metrics, recomputed for every grain a query picks.
- Query it downstream with `select * from semantic_view({{ ref('sv_order_economics') }} metrics … dimensions …)`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| A ratio stored as a column and averaged in the BI tool | Define it as a derived metric over its parts in the view |
| Monthly `count(distinct customer_id)` summed to a year | Distinct counts are not additive; let the view count distinct at the query's grain |
| `count(*)` for entities when a child table has several rows per parent | `count(distinct <primary key>)` |
| No `primary key` on a logical table | Declare one on every table; relationships reference it |
| `FACTS` and `METRICS` in the same `SEMANTIC_VIEW()` query | Not allowed; query facts with dimensions, or metrics with dimensions |
| Materializations disappear after every `dbt run` | Set `create_or_alter=true`; `CREATE OR REPLACE` drops them |
| Column descriptions in dbt YAML expected in Snowflake | `persist_docs` does not reach the semantic view; write `comment = '…'` in the DDL |
| A reconciliation test with `where a != b` | A NULL on either side passes silently; use `is distinct from` |
