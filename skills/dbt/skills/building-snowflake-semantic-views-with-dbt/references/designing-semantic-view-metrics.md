# Designing Semantic View Metrics

## Additive, distinct-count and ratio metrics

| Kind | Example | Rule |
|---|---|---|
| additive | `sum(amount)`, `count(*)` | can be rolled up over any dimension |
| distinct count | `count(distinct customer_id)` | **not additive**: a customer active in two months counts twice if monthly results are summed. Let the view count distinct at the query's grain |
| ratio | average order value, orders per customer | never pre-aggregate and re-sum or re-average; define as a derived metric over its parts |

```sql
metrics (
  orders.total_orders        as count(distinct orders.order_id),
  orders.total_revenue       as sum(orders.order_amount),
  orders.distinct_customers  as count(distinct orders.customer_id),
  avg_order_value            as orders.total_revenue / orders.total_orders,
  orders_per_customer        as orders.total_orders / orders.distinct_customers
)
```

Define the customer count on the **orders** table (the foreign key `orders.customer_id`), not on the customers table: a metric can only be grouped by dimensions of its own table or of tables at the same or a coarser grain, so `orders.distinct_customers` can be sliced by `orders.order_month`, while `customers.total_customers` cannot. Put a metric on the customers table only when it is sliced by customer attributes.

The division is recomputed for whatever dimensions a query picks. A stored `avg_order_value` column averaged by a dashboard gives the wrong week, month or segment.

## A corrected metric next to the as-reported one

When late corrections are booked in a separate adjustments table (for example an append-only ledger of deltas for already-reported orders), keep the original metric and add the corrected one:

```sql
adjustments.total_adjustments as sum(adjustments.adjustment_amount),
true_avg_order_value as (orders.total_revenue + coalesce(adjustments.total_adjustments, 0)) / orders.total_orders
```

- **Decide which month a correction belongs to, and say it in the metric's `COMMENT`.** Through the relationship adjustments → orders, a query by order month credits each correction to the order's original month: a restated view. A ledger usually books it in the month it was recognised, which keeps closed periods unchanged. For that view, define a separate metric on the adjustments table (`adjustments.recognized_adjustments as sum(adjustments.adjustment_amount)`) and query it by a dimension of the same table (`adjustments.recognized_month`); metrics of the orders table cannot be grouped by a dimension of the finer-grained adjustments table. Combine the two results by month in a downstream model.
- Keep the as-reported metric (`avg_order_value`) next to the corrected one and name the difference.
- `coalesce` once, in the derived metric: a group without adjustments has no adjustment rows.

## Relationship chains

`adjustments → orders → customers` is a two-step chain. A metric on the parent side combined with one from the child side is evaluated per table at its own grain and joined by the engine. Still:

- Declare a primary key on every logical table.
- Count entities with `count(distinct <primary key>)`; `count(*)` over joined rows is wrong when the child has several rows per parent.
- A fact table that is not unique at its declared key inflates every metric. Fix and test the grain in the dbt model, not in the view.

## Reconciling with the BI tool

When the same KPI exists in the semantic view and in a BI tool's own semantic layer:

1. Keep a metric catalog (a seed or a table): metric name, definition, grain, owner, where it is implemented.
2. Write a singular dbt test per key metric that compares the semantic view with a trusted query for a few dimension slices, and fails above a tolerance.
3. Change a definition on purpose once and check that the test goes red; a test that cannot fail proves nothing.
4. Decide which layer is the source of truth; the other is generated from it or tested against it.

## Checklist

- Every metric labelled additive, distinct count or ratio; ratios are derived metrics.
- Primary keys declared; entity counts use `count(distinct …)`.
- Corrected and as-reported variants named clearly; the month of a correction stated.
- A reconciliation test per key metric at two or more grains.
- Descriptions in `COMMENT`.
