---
name: build-dbt-semantic-layer
description: Use when creating or modifying dbt Semantic Layer components including semantic models, metrics, and dimensions leveraging MetricFlow.
---

# Building the dbt Semantic Layer

This skill guides the creation and modification of dbt Semantic Layer components: semantic models, entities, dimensions, and metrics.

## TODO 
    - add new semantic layer note
    - point to docs pages in order to reduce the length of the skill
    - how do we validate the semantic layer? ensure that's 


## Entry Points

### Business Question First

When the user describes a metric or analysis need (e.g., "I need to track customer lifetime value by segment"):

1. Search project models or existing semantic models by name, description, and column names for relevant candidates
2. Present top matches with brief context (model name, description, key columns)
3. User confirms which model(s) / semantic models to build on / extend / update
4. Work backwards from users need to define entities, dimensions, and metrics

### Model First

When the user specifies a model to expose (e.g., "Add semantic layer to `customers` model"):

1. Read the model SQL and existing YAML config
2. Identify the grain (primary key / entity)
3. Suggest dimensions based on column types and names
4. Ask what metrics the user wants to define

Both paths converge on the same implementation workflow.

### Open Ended

User asks to build the semantic layer for a project or models that are not specified. ("Build the semantic layer for my project")

1. Identify high importance models in the project
2. Suggest some metrics and dimensions for those models
3. Ask the user if they want to create more metrics and dimensions or if there are any other models they want to build the semantic layer on


## Implementation Workflow

### Step 1: Enable Semantic Model

Decide which dbt model to build the semantic model on. Add `semantic_model:` block to the model's YAML with `enabled: true`. Set `agg_time_dimension` to the primary time column. If the model does not have a time column, warn user that the model cannot contain metrics that are time-based. Ask the user if they want to create a derived time dimension.

Example YAML:

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true # enable the semantic model
    agg_time_dimension: ordered_at # set the primary time column (this is a column in the dbt model)
```

### Step 2: Define Entities

Identify the primary key column (check for `_id` suffix, uniqueness tests, or explicit config). Add `entity: \n\t type: primary` block to that column's entry. If the model has foreign keys, define those as `entity: type: foreign`.

```yaml
models:
  - name: orders
    semantic_model:
      enabled: true # enable the semantic model
    agg_time_dimension: ordered_at # set the primary time column (this is a column in the dbt model)
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

### Step 3: Define Dimensions

Scan columns for dimension candidates. These would be useful columns to group by when querying a metrics:
- Time columns → `dimension: type: time` with appropriate `granularity` (set at the column level)
- Categorical columns (strings, booleans) → `dimension: type: categorical`

Present suggested dimensions to user for confirmation.

Example YAML:
```yaml
models:
  - name: orders
    semantic_model:
      enabled: true # enable the semantic model
    agg_time_dimension: ordered_at # set the primary time column (this is a column in the dbt model)
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
        granularity: day # set the granularity of the time column
        dimension:
          type: time

      - name: order_status
        dimension:
          type: categorical
```

### Step 4: Define Metrics

Create some simple metrics for the model.  For each metric, collect: name, description, label, aggregation type, and expression. Support metric types: `simple`, `derived`, `cumulative`, `conversion`, `ratio`. 
```yaml
models:
  - name: orders
    semantic_model:
      enabled: true # enable the semantic model
    agg_time_dimension: ordered_at # set the primary time column (this is a column in the dbt model)
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
        granularity: day # set the granularity of the time column
        dimension:
          type: time

      - name: order_status
        dimension:
          type: categorical

    metrics:
      - name: order_count
        type: simple
        agg: count
        expr: 1

      - name: total_revenue
        type: simple
        agg: sum
        expr: amount

      - name: average_order_value
        type: simple
        agg: avg
        expr: amount
```

## Validation

After writing YAML, validate in two stages:

1. **Parse Validation**: Run `dbt parse` to confirm YAML syntax and references
2. **Semantic Layer Validation**: Run `dbt sl validate` to check all metric configurations

Do not consider work complete until both validations pass.

## Editing Existing Components

When modifying existing semantic layer config:

- Check if the model's YAML already has `semantic_model:` block
- Read existing entities, dimensions, and metrics before making changes
- Preserve all existing YAML content not being modified
- After edits, run full validation to ensure nothing broke

## YAML Format Reference

### Model-level configuration

```yaml
models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: fct_orders_semantic_model  # optional override

    agg_time_dimension: order_date  # required, at model level
    columns:
      # Shorthand
      - name: order_id
        entity: primary

      # Full form
      - name: order_id
        entity:
          type: primary
          name: order
          description: "Primary entity for orders"
          label: "Order"

      # Foreign entity
      - name: customer_id
        entity:
          type: foreign
          name: customer

      # Unique entity
      - name: transaction_id
        entity: unique

      # Categorical dimension - shorthand
      - name: order_status
        dimension: categorical

      # Categorical dimension - full form
      - name: order_status
        description: "Order status dimension"
        dimension:
          type: categorical
          name: status
          label: "Status"

      # Time dimension - granularity at column level
      - name: ordered_at
        granularity: day
        dimension:
          type: time
          name: order_date
          is_partition: true
          label: "Order Date"
```

### Derived Dimensions and Entities

if the user wants to create a derived dimension or entity that is not a column within the dbt model, then we can use the `derived_semantics` block.

```yaml
    derived_semantics:
      dimensions:
        - name: order_size_bucket
          type: categorical
          expr: case when amount > 100 then 'large' else 'small' end
          label: "Order Size"

      entities:
        - name: order_customer_key
          type: foreign
          expr: "order_id || '-' || customer_id"
```

### Simple Metrics

```yaml
    metrics:
      - name: total_orders
        description: Count of all orders
        type: simple
        label: Total Orders
        agg: count
        expr: order_id

```

### Derived Metrics

```yaml
      - name: revenue_per_order
        type: derived
        description: Average revenue per order
        label: Revenue per Order
        expr: total_revenue / total_orders
        input_metrics:
          - name: total_revenue
          - name: total_orders

      # With offset window
      - name: revenue_growth
        type: derived
        expr: total_revenue - revenue_last_week
        input_metrics:
          - name: total_revenue
          - name: total_revenue
            alias: revenue_last_week
            offset_window: 1 week
            filter: "{{ Dimension('order__status') }} = 'completed'"
```

### Cumulative Metrics

```yaml
      - name: cumulative_revenue
        type: cumulative
        description: Running total of revenue
        label: Cumulative Revenue
        input_metric: total_revenue
        grain_to_date: week
        period_agg: first

      # With window
      - name: trailing_7d_revenue
        type: cumulative
        input_metric: total_revenue
        window: 7 days
```

### Ratio Metrics

```yaml
      - name: conversion_rate
        type: ratio
        description: Orders divided by visits
        label: Conversion Rate
        numerator: total_orders
        denominator: total_visits

      # With filters
      - name: premium_conversion_rate
        type: ratio
        numerator:
          name: total_orders
          filter: "{{ Dimension('order__customer_segment') }} = 'premium'"
          alias: premium_orders
        denominator: total_visits
```

### Conversion Metrics

```yaml
      - name: signup_to_purchase
        type: conversion
        description: Rate of signups converting to purchase
        label: Signup to Purchase
        entity: customer
        calculation: conversion_rate
        base_metric: signups
        conversion_metric: purchases
        window: 7 days
        constant_properties:
          - base_property: signup_channel
            conversion_property: purchase_channel
```

### Top-level Metrics (Cross-model)

```yaml
# For metrics depending on multiple semantic models
metrics:
  - name: cross_model_ratio
    type: ratio
    numerator:
      name: metric_from_model_a
      filter: "{{ Dimension('entity__dim') }} > 10"
    denominator:
      name: metric_from_model_b
    config:
      group: example_group
      tags:
        - example_tag
      meta:
        owner: "@someone"
```

## Key Formatting Rules

- `semantic_model:` block at model level with `enabled: true`
- `agg_time_dimension:` at model level (not nested under `semantic_model`)
- `entity:` and `dimension:` on columns (can use shorthand or full form)
- `granularity:` required at column level for time dimensions
- `metrics:` array at model level for single-model metrics
- Top-level `metrics:` key for cross-model metrics (derived, ratio, cumulative, conversion only)

## Best Practices

- **Start with entities** - Identify the grain before defining dimensions or metrics
- **Use shorthand where possible** - `entity: primary` instead of full nested form for simple cases
- **Name metrics for business users** - Use clear `label` values for non-technical users
- **Keep metrics close to their data** - Simple metrics on their semantic model; top-level only for cross-model
- **Set appropriate granularity** - Match the actual data grain (usually `day`)

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Missing `agg_time_dimension` | Every semantic model needs a default time dimension |
| `granularity` inside `dimension:` block | Must be at column level |
| Both `entity` and `dimension` on same column | A column can only be one or the other |
| Simple metrics in top-level `metrics:` | Top-level is only for cross-model metrics |
| Using `window` and `grain_to_date` together | Cumulative metrics can only have one |
| Missing `input_metrics` on derived metrics | Must list metrics used in `expr` |
