# Latest Semantic Layer YAML Spec

This is the authoring guide for the **latest** dbt Semantic Layer YAML spec, supported in **dbt Core 1.12+** and **Fusion** (always).

In the latest spec, semantic models are configured as metadata annotations on your dbt models rather than as separate top-level resources. Measures are replaced by simple metrics defined directly within models.

## Contents

- Implementation Workflow (Steps 1-4: enable semantic model, entities, dimensions, metrics)
- YAML Format Reference (derived semantics, simple metric options, advanced metrics)
- Advanced Metrics (derived, cumulative, ratio, conversion)
- Cross-Model (Top-Level) Metrics
- SCD Type II Dimensions
- Key Formatting Rules
- Common Pitfalls

## Implementation Workflow

### Step 1: Enable Semantic Model

Add a `semantic_model:` block to the model's YAML with `enabled: true`. Set `agg_time_dimension` at the model level to the primary time column. If the model does not have a time column, warn the user that it cannot contain time-based metrics. Ask the user if they want to create a derived time dimension.

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true
    agg_time_dimension: ordered_at
```

### Step 2: Define Entities

Identify the primary key column (check for `_id` suffix, uniqueness tests, or explicit config). Add an `entity:` block to that column's entry. If the model has foreign keys, define those as `entity: type: foreign`.

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true
    agg_time_dimension: ordered_at
    columns:
      - name: order_id
        entity:
          type: primary
          name: order
      - name: customer_id
        entity:
          type: foreign
          name: customer
```

Entity types: `primary`, `foreign`, `unique`, `natural` (SCD Type II only).

### Step 3: Define Dimensions

Scan columns for dimension candidates:
- Time columns -> `dimension: type: time` with `granularity` at the column level
- Categorical columns (strings, booleans) -> `dimension: type: categorical`

Present suggested dimensions to user for confirmation.

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true
    agg_time_dimension: ordered_at
    columns:
      - name: order_id
        entity:
          type: primary
          name: order

      - name: customer_id
        entity:
          type: foreign
          name: customer

      - name: ordered_at
        granularity: day
        dimension:
          type: time

      - name: order_status
        dimension:
          type: categorical
```

### Step 4: Define Simple Metrics

Create simple metrics for the model. For each metric, collect: name, description, label, aggregation type, and expression. Supported agg types: `sum`, `min`, `max`, `average`, `median`, `count`, `count_distinct`, `percentile`, `sum_boolean`.

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true
    agg_time_dimension: ordered_at
    columns:
      - name: order_id
        entity:
          type: primary
          name: order

      - name: customer_id
        entity:
          type: foreign
          name: customer

      - name: ordered_at
        granularity: day
        dimension:
          type: time

      - name: order_status
        dimension:
          type: categorical

    metrics:
      - name: order_count
        type: simple
        label: Order Count
        agg: count
        expr: 1

      - name: total_revenue
        type: simple
        label: Total Revenue
        agg: sum
        expr: amount

      - name: average_order_value
        type: simple
        label: Average Order Value
        agg: avg
        expr: amount
```

## YAML Format Reference

### Derived Dimensions and Entities

Use the `derived_semantics` block for dimensions or entities that are not a direct 1:1 mapping to a physical column. The `expr` field is required.

```yaml
models: 
  - name: orders
    [...]
    derived_semantics:
      dimensions:
        - name: order_size_bucket
          type: categorical
          expr: "case when amount > 100 then 'large' else 'small' end"
          label: "Order Size"

      entities:
        - name: user
          type: foreign
          expr: "substring(id_order from 2)"
```

### Simple Metric Options

Simple metrics support these additional properties:

```yaml
models: 
  - name: orders
    [...]
    metrics:
      - name: customers
        type: simple
        label: Count of customers
        agg: count
        expr: customers
        fill_nulls_with: 0                        # Replace nulls with this value
        join_to_timespine: true                    # Join to time spine to fill missing dates
        agg_time_dimension: my_other_time_column   # Override model's default time dimension
        filter: "{{ Dimension('customer__customer_total') }} >= 20"
```

For percentile aggregation:

```yaml
models: 
  - name: orders
    [...]
    metrics:
      - name: revenue_p95
        type: simple
        label: Revenue P95
        agg: percentile
        expr: amount
        percentile: 95.0
        percentile_type: discrete   # discrete or continuous
```

### Advanced Metrics

Simple metrics defined within a model serve as building blocks. Advanced metrics that reference simple metrics _within the same model_ go under the model's `metrics:` key. Advanced metrics that reference metrics _across different models_ go under the top-level `metrics:` key.

#### Derived Metrics

Combine multiple metrics using an expression.

```yaml
models: 
  - name: orders
    [...]
    metrics:
      - name: order_gross_profit
        description: "Gross profit from each order."
        label: Order gross profit
        type: derived
        expr: revenue - cost
        input_metrics:
          - name: order_total
            alias: revenue
          - name: order_cost
            alias: cost
```

With offset window (period-over-period):

```yaml
models: 
  - name: orders
    [...]
    metrics:
      - name: order_total_growth_mom
        description: "Percentage growth of orders compared to 1 month ago"
        label: Order total growth % M/M
        type: derived
        expr: (order_total - order_total_prev_month) * 100 / order_total_prev_month
        input_metrics:
          - name: order_total
          - name: order_total
            alias: order_total_prev_month
            offset_window: 1 month
```

With filter on input metric:

```yaml
models: 
  - name: orders
    [...]
    metrics:
      - name: food_order_gross_profit
        label: Food order gross profit
        type: derived
        expr: revenue - cost
        input_metrics:
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

Aggregate a metric over a running window or grain-to-date period. Requires a [time spine](time-spine.md).

```yaml
metrics:
  - name: cumulative_order_total
    label: "Cumulative order total (All-Time)"
    description: "The cumulative value of all orders"
    type: cumulative
    input_metric: order_total

  - name: cumulative_order_total_l1m
    label: "Cumulative order total (L1M)"
    description: "Trailing 1-month cumulative order total"
    type: cumulative
    window: 1 month
    input_metric: order_total

  - name: cumulative_order_total_mtd
    label: "Cumulative order total (MTD)"
    description: "The month-to-date value of all orders"
    type: cumulative
    grain_to_date: month
    input_metric: order_total
```

With `period_agg` for re-aggregation at non-default granularity:

```yaml
metrics:
  - name: cumulative_revenue
    description: "The cumulative revenue for all orders."
    label: "Cumulative revenue (all-time)"
    type: cumulative
    input_metric: revenue
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
    numerator: food_orders
    denominator: orders
```

With filter and alias:

```yaml
metrics:
  - name: frequent_purchaser_ratio
    description: Fraction of active users who qualify as frequent purchasers
    type: ratio
    numerator:
      name: distinct_purchasers
      filter: |
        {{ Dimension('customer__is_frequent_purchaser') }}
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
    entity: user
    calculation: conversion_rate   # conversion_rate (default) or conversions
    base_metric:
      name: visits
      filter: "{{ Dimension('visits__referrer_id') }} = 'facebook'"
    conversion_metric: buys
    window: 7 days
```

With constant properties (ensure same dimension value across base and conversion events):

```yaml
metrics:
  - name: view_item_detail_to_purchase_with_same_item
    description: "Conversion rate for users who viewed and purchased the same item"
    type: conversion
    label: View item detail > Purchase
    entity: user
    calculation: conversions
    base_metric: view_item_detail
    conversion_metric: purchase
    window: 1 week
    constant_properties:
      - base_property: product
        conversion_property: product
```

### Cross-Model (Top-Level) Metrics

For metrics depending on multiple semantic models, define them at the top-level `metrics:` key:

```yaml
metrics:
  - name: orders_per_session
    type: ratio
    numerator: orders
    denominator: sessions
    config:
      group: example_group
      tags:
        - example_tag
      meta:
        owner: "@someone"
```

### SCD Type II Dimensions

For slowly changing dimension tables, use `validity_params` on time dimensions and `natural` entity type:

```yaml
models:
  - name: sales_person_tiers
    semantic_model:
      enabled: true
    agg_time_dimension: tier_start
    primary_entity: sales_person
    columns:
      - name: start_date
        granularity: day
        dimension:
          type: time
          name: tier_start
          label: "Start date of tier"
          validity_params:
            is_start: true
      - name: end_date
        granularity: day
        dimension:
          type: time
          name: tier_end
          label: "End date of tier"
          validity_params:
            is_end: true
      - name: tier
        dimension:
          type: categorical
          name: tier
      - name: sales_person_id
        entity:
          type: natural
          name: sales_person
```

SCD Type II semantic models cannot contain simple metrics.

## Key Formatting Rules

- `semantic_model:` block at model level with `enabled: true`
- `agg_time_dimension:` at model level (not nested under `semantic_model:`)
- `entity:` and `dimension:` blocks on columns (a column can have one or the other, not both)
- `granularity:` required at column level for time dimensions
- `metrics:` array at model level for single-model metrics
- Top-level `metrics:` key for cross-model metrics (derived, ratio, cumulative, conversion only)
- Use `derived_semantics:` for computed dimensions/entities not tied to a single column

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Missing `agg_time_dimension` | Every semantic model needs a default time dimension |
| `granularity` inside `dimension:` block | Must be at column level, not nested under `dimension:` |
| Defining a column as both an entity and a dimension | A column can only be one or the other |
| Simple metrics in top-level `metrics:` | Top-level is only for cross-model advanced metrics |
| Using `window` and `grain_to_date` together | Cumulative metrics can only have one |
| Missing `input_metrics` on derived metrics | Must list metrics used in `expr` |
| Using `type_params` or `measures` | Those are legacy spec syntax; this spec uses direct keys |
