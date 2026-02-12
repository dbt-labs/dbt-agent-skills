# Legacy Semantic Layer YAML Spec

This is the authoring guide for the **legacy** dbt Semantic Layer YAML spec, supported in **dbt Core 1.6 through 1.11**. dbt Core 1.12+ also supports this spec but the [latest spec](latest-spec.md) is recommended for new projects.

In the legacy spec, semantic models are defined as top-level resources separate from dbt model definitions. Measures are a core concept used as building blocks for metrics.

## Contents

- Implementation Workflow (Steps 1-4: semantic model, entities, dimensions, measures/metrics)
- YAML Format Reference (complete spec, measure properties, percentile, non-additive dimensions)
- Metrics (simple, derived, cumulative, ratio, conversion)
- SCD Type II Dimensions
- Key Formatting Rules
- Common Pitfalls

## Implementation Workflow

### Step 1: Define Semantic Model

Create a top-level `semantic_models:` entry that references the dbt model via `ref()`. Set `defaults.agg_time_dimension` to the primary time column. If the model does not have a time column, warn the user that it cannot contain time-based measures or metrics. Ask the user if they want to create a derived time dimension.

```yaml
semantic_models:
  - name: orders
    model: ref('orders')
    defaults:
      agg_time_dimension: ordered_at
```

### Step 2: Define Entities

Identify the primary key column. Add it to the `entities:` array with `type: primary`. Use `expr` to reference the actual column name when the entity name differs from it. If the model has foreign keys, define those as `type: foreign`.

```yaml
semantic_models:
  - name: orders
    model: ref('orders')
    defaults:
      agg_time_dimension: ordered_at
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
```

Entity types: `primary`, `foreign`, `unique`, `natural` (SCD Type II only).

If the model has no physical primary key column, use the `primary_entity` property:

```yaml
semantic_models:
  - name: bookings_monthly_source
    model: ref('bookings_monthly_source')
    defaults:
      agg_time_dimension: ds
    primary_entity: booking_id
```

### Step 3: Define Dimensions

Scan columns for dimension candidates:
- Time columns -> `type: time` with `type_params.time_granularity`
- Categorical columns (strings, booleans) -> `type: categorical`

Use `expr` to reference the actual column name when the dimension name differs from it.

```yaml
semantic_models:
  - name: orders
    model: ref('orders')
    defaults:
      agg_time_dimension: ordered_at
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
    dimensions:
      - name: ordered_at
        type: time
        type_params:
          time_granularity: day
      - name: order_status
        type: categorical
```

Computed dimensions use `expr`:

```yaml
semantic_models: 
  - name: orders
    [...]
    dimensions:
      - name: is_bulk_transaction
        type: categorical
        expr: case when quantity > 10 then true else false end
```

### Step 4: Define Measures and Metrics

Add a `measures:` array under the semantic model for aggregations. Then define top-level `metrics:` that reference those measures via `type_params`.

Supported agg types: `sum`, `min`, `max`, `average`, `sum_boolean`, `count_distinct`, `median`, `percentile`.

```yaml
semantic_models:
  - name: orders
    model: ref('orders')
    defaults:
      agg_time_dimension: ordered_at
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
    dimensions:
      - name: ordered_at
        type: time
        type_params:
          time_granularity: day
      - name: order_status
        type: categorical
    measures:
      - name: order_count
        agg: sum
        expr: 1
      - name: total_revenue
        agg: sum
        expr: amount
      - name: average_order_value
        agg: average
        expr: amount

metrics:
  - name: order_count
    type: simple
    label: Order Count
    type_params:
      measure: order_count
  - name: total_revenue
    type: simple
    label: Total Revenue
    type_params:
      measure: total_revenue
```

## YAML Format Reference

### Complete Semantic Model Spec

```yaml
semantic_models:
  - name: the_name_of_the_semantic_model   # Required
    description: same as always             # Optional
    model: ref('some_model')                # Required
    defaults:                               # Required
      agg_time_dimension: dimension_name    # Required if model contains measures
    entities:                               # Required
      - name: entity_name
        type: primary | foreign | unique | natural
        expr: column_name_or_sql_expression  # Optional, defaults to name
    dimensions:                             # Required
      - name: dimension_name
        type: categorical | time
        expr: column_name_or_sql_expression  # Optional, defaults to name
        type_params:                         # Required for time dimensions
          time_granularity: day
    measures:                               # Optional
      - name: measure_name
        agg: sum | min | max | average | sum_boolean | count_distinct | median | percentile
        expr: column_name_or_sql_expression  # Optional, defaults to name
    primary_entity: entity_name             # Required if no primary entity in entities array
```

### Measure Properties

| Property | Description | Required |
|----------|-------------|----------|
| `name` | Unique across all semantic models | Yes |
| `agg` | Aggregation type | Yes |
| `description` | Human-readable explanation | No |
| `expr` | Column name or SQL expression | No (defaults to name) |
| `label` | Display name in downstream tools | No |
| `create_metric` | Auto-generate a simple metric (`true`/`false`) | No |
| `agg_time_dimension` | Override default time dimension | No |
| `agg_params` | Extra params for specific agg types (e.g. percentile) | No |
| `non_additive_dimension` | For measures that shouldn't aggregate across time | No |
| `config` | Supports `meta` dictionary | No |

### Percentile Measures

```yaml
semantic_models: 
  - name: orders
    [...]
    measures:
      - name: p99_transaction_value
        description: The 99th percentile transaction value
        expr: transaction_amount_usd
        agg: percentile
        agg_params:
          percentile: .99
          use_discrete_percentile: false
```

### Non-Additive Dimensions

For measures like account balances or MRR that shouldn't be summed across time:

```yaml
semantic_models: 
  - name: orders
    [...]
    measures:
      - name: mrr
        description: Sum of all active subscription plans
        expr: subscription_value
        agg: sum
        non_additive_dimension:
          name: subscription_date
          window_choice: max   # max (period end) or min (period start)
      - name: user_mrr
        description: Each user's MRR
        expr: subscription_value
        agg: sum
        non_additive_dimension:
          name: subscription_date
          window_choice: max
          window_groupings:
            - user_id
```

### Metrics

All metrics are defined at the top-level `metrics:` key, referencing measures via `type_params`.

#### Simple Metrics

```yaml
metrics:
  - name: customers
    description: Count of customers
    type: simple
    label: Count of customers
    type_params:
      measure:
        name: customers
        fill_nulls_with: 0
        join_to_timespine: true
        alias: customer_count
        filter: "{{ Dimension('customer__customer_total') }} >= 20"
```

Shorthand when no extra attributes needed:

```yaml
metrics:
  - name: total_revenue
    type: simple
    label: Total Revenue
    type_params:
      measure: total_revenue
```

#### Derived Metrics

Combine multiple metrics using an expression.

```yaml
metrics:
  - name: order_gross_profit
    description: Gross profit from each order.
    type: derived
    label: Order gross profit
    type_params:
      expr: revenue - cost
      metrics:
        - name: order_total
          alias: revenue
        - name: order_cost
          alias: cost
```

With offset window (period-over-period):

```yaml
metrics:
  - name: order_total_growth_mom
    description: "Percentage growth of orders total compared to 1 month ago"
    type: derived
    label: Order total growth % M/M
    type_params:
      expr: (order_total - order_total_prev_month)*100/order_total_prev_month
      metrics:
        - name: order_total
        - name: order_total
          offset_window: 1 month
          alias: order_total_prev_month
```

With filter on input metric:

```yaml
metrics:
  - name: food_order_gross_profit
    label: Food order gross profit
    type: derived
    type_params:
      expr: revenue - cost
      metrics:
        - name: order_total
          alias: revenue
          filter: |
            {{ Dimension('order__is_food_order') }} = True
        - name: order_cost
          alias: cost
          filter: |
            {{ Dimension('order__is_food_order') }} = True
```

#### Cumulative Metrics

Aggregate a measure over a running window or grain-to-date period. Requires a [time spine](time-spine.md).

```yaml
metrics:
  - name: cumulative_order_total
    label: Cumulative order total (All-Time)
    description: The cumulative value of all orders
    type: cumulative
    type_params:
      measure:
        name: order_total

  - name: cumulative_order_total_l1m
    label: Cumulative order total (L1M)
    description: Trailing 1-month cumulative order total
    type: cumulative
    type_params:
      measure:
        name: order_total
      cumulative_type_params:
        window: 1 month

  - name: cumulative_order_total_mtd
    label: Cumulative order total (MTD)
    description: The month-to-date value of all orders
    type: cumulative
    type_params:
      measure:
        name: order_total
      cumulative_type_params:
        grain_to_date: month
```

With `period_agg` for re-aggregation at non-default granularity:

```yaml
metrics:
  - name: cumulative_revenue
    description: The cumulative revenue for all orders.
    label: Cumulative revenue (all-time)
    type: cumulative
    type_params:
      measure: revenue
      cumulative_type_params:
        period_agg: first   # first | last | average. Defaults to first.
```

`window` and `grain_to_date` cannot be used together.

#### Ratio Metrics

Create a ratio between two metrics. Numerator and denominator can be strings (metric name) or dicts (with `name`, `filter`, `alias`).

```yaml
metrics:
  - name: food_order_pct
    description: "The food order count as a ratio of the total order count"
    label: Food order ratio
    type: ratio
    type_params:
      numerator: food_orders
      denominator: orders
```

With filter and alias:

```yaml
metrics:
  - name: frequent_purchaser_ratio
    description: Fraction of active users who qualify as frequent purchasers
    type: ratio
    type_params:
      numerator:
        name: distinct_purchasers
        filter: |
          {{Dimension('customer__is_frequent_purchaser')}}
        alias: frequent_purchasers
      denominator:
        name: distinct_purchasers
```

#### Conversion Metrics

Measure how often one event leads to another for a specific entity within a time window.

```yaml
metrics:
  - name: visit_to_buy_conversion_rate_7d
    description: "Conversion rate from visiting to transaction in 7 days"
    type: conversion
    label: Visit to buy conversion rate (7-day window)
    type_params:
      conversion_type_params:
        base_measure:
          name: visits
          fill_nulls_with: 0
          filter: "{{ Dimension('visits__referrer_id') }} = 'facebook'"
        conversion_measure:
          name: buys
        entity: user
        window: 7 days
```

With constant properties:

```yaml
metrics:
  - name: view_item_detail_to_purchase_with_same_item
    description: "Conversion rate for users who viewed and purchased the same item"
    type: conversion
    label: View item detail > Purchase
    type_params:
      conversion_type_params:
        calculation: conversions
        base_measure:
          name: view_item_detail
        conversion_measure: purchase
        entity: user
        window: 1 week
        constant_properties:
          - base_property: product
            conversion_property: product
```

### SCD Type II Dimensions

For slowly changing dimension tables, use `validity_params` under `type_params` and `natural` entity type:

```yaml
semantic_models:
  - name: sales_person_tiers
    description: SCD Type II table of tiers for salespeople
    model: ref('sales_person_tiers')
    defaults:
      agg_time_dimension: tier_start
    primary_entity: sales_person
    dimensions:
      - name: tier_start
        type: time
        label: "Start date of tier"
        expr: start_date
        type_params:
          time_granularity: day
          validity_params:
            is_start: True
      - name: tier_end
        type: time
        label: "End date of tier"
        expr: end_date
        type_params:
          time_granularity: day
          validity_params:
            is_end: True
      - name: tier
        type: categorical
    entities:
      - name: sales_person
        type: natural
        expr: sales_person_id
```

SCD Type II semantic models cannot contain measures.

## Key Formatting Rules

- Top-level `semantic_models:` key (not nested under `models:`)
- `model: ref('...')` required on each semantic model without curly braces
- `defaults.agg_time_dimension` for default time dimension
- Entities, dimensions, and measures are separate arrays under the semantic model
- All metrics at the top-level `metrics:` key, referencing measures via `type_params`
- Use `expr` on dimensions/entities for computed values or column name aliasing

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Missing `defaults.agg_time_dimension` | Every semantic model with measures needs a default time dimension |
| `time_granularity` outside `type_params` | Must be nested under `type_params` for time dimensions |
| Missing `model: ref('...')` | Required for every semantic model |
| Metrics without `type_params` | All metrics must reference measures through `type_params` |
| Using `window` and `grain_to_date` together | Cumulative metrics can only have one |
| Missing `type_params.metrics` on derived metrics | Must list metrics used in `expr` |
| Using `semantic_model:` on models or `agg` on metrics | Those are latest spec syntax; this spec uses `semantic_models:` and `measures` |
