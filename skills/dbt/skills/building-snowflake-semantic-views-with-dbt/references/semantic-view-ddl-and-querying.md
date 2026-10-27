# Semantic View DDL and Querying

Full syntax: the Snowflake reference for [`CREATE SEMANTIC VIEW`](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view). This guide covers the shape and the rules that matter in practice.

## Clauses, in order

The clause order matters: `TABLES` (required), then `RELATIONSHIPS`, `FACTS`, `DIMENSIONS`, `METRICS` (at least one of dimensions or metrics), then optional `COMMENT`, `MAX_STALENESS`, the AI clauses (`AI_SQL_GENERATION`, `AI_QUESTION_CATEGORIZATION`, `AI_VERIFIED_QUERIES`), `TAG` and `COPY GRANTS`.

```sql
create or replace semantic view <db>.<schema>.sv_order_economics
  tables (
    customers   as <db>.<schema>.dim_customers         primary key (customer_id),
    orders      as <db>.<schema>.fct_orders            primary key (order_id),
    adjustments as <db>.<schema>.fct_order_adjustments primary key (adjustment_id)
  )
  relationships (
    orders_to_customer   as orders (customer_id)  references customers (customer_id),
    adjustments_to_order as adjustments (order_id) references orders (order_id)
  )
  facts (
    orders.order_amount           as orders.amount,
    adjustments.adjustment_amount as adjustments.amount_delta
  )
  dimensions (
    customers.customer_segment as customers.segment,
    orders.order_month         as date_trunc('month', orders.order_date)
  )
  metrics (
    orders.total_orders  as count(distinct orders.order_id),
    orders.total_revenue as sum(orders.order_amount),
    avg_order_value      as orders.total_revenue / orders.total_orders
  )
  comment = 'Order economics';
```

- **`TABLES`:** logical alias `as` physical table, with `primary key (…)` and optional `unique (…)`. Relationships reference these keys.
- **`RELATIONSHIPS`:** `name as child (fk) references parent (pk)`. Chains are allowed; a query joins only the tables it needs. `USING (relationship)` on a metric picks the path when there are several.
- **`FACTS`:** row-level expressions at a table's grain, the inputs of metrics. A fact can be `private` (usable in metrics, not queryable).
- **`DIMENSIONS`:** attributes to group and filter by; they may be expressions.
- **`METRICS`:** aggregates (`table.name as agg(…)`) and **derived metrics** without a table prefix that combine other metrics. `NON ADDITIVE BY (…)` marks a metric that must not be summed over certain dimensions, such as a balance over time.
- **`COMMENT`:** on the view and on each table, fact, dimension and metric. This is where descriptions live.
- **`MAX_STALENESS`:** required before materializations can be added. The DDL reference gives it in seconds (minimum 120); check the form your Snowflake version accepts.
- **`CREATE OR ALTER SEMANTIC VIEW`** accepts the same clauses except `TAG` and `COPY GRANTS`; a property left out of the statement (for example `COMMENT`) is unset.

Inspect an existing view with `describe semantic view <name>` and `get_ddl('SEMANTIC_VIEW', '<db>.<schema>.<name>')`.

## Querying

```sql
select * from semantic_view(
    <db>.<schema>.sv_order_economics
    dimensions customers.customer_segment, orders.order_month
    metrics    orders.total_revenue, avg_order_value
    where      orders.order_month >= '2026-01-01'
);
```

- Name `METRICS`, `DIMENSIONS` or `FACTS` (at least one). **`FACTS` and `METRICS` cannot be combined** in one query.
- The output columns follow the clause order: put `DIMENSIONS` first to get the dimension columns first.
- A dimension used with a metric must come from a related table at the same or a coarser grain; `show semantic dimensions for metric` lists the valid ones.
- Metrics are computed at the grain of the query, so a ratio is right per segment, per month and in total. Do not wrap the result in another `sum()` or `avg()`.
- Join the output of `semantic_view(…)` to other tables only after it has returned its grain.
