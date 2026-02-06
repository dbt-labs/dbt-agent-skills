# Semantic Layer Skill Restructure: Multi-Version Spec Support

## Problem

The `building-dbt-semantic-layer` skill only covers the latest (new) YAML spec. It needs to support both the legacy and latest specs, since:

- **Legacy spec**: dbt Core 1.6 through 1.11
- **Latest spec**: dbt Core 1.12+ (both specs supported), Fusion (always latest)

The two specs share many concepts but differ in YAML structure.

## File Structure

```
skills/building-dbt-semantic-layer/
├── SKILL.md                              # Entry point + shared concepts
└── references/
    ├── best-practices.md                 # Shared, with conditional advice + minimal inline examples
    ├── time-spine.md                     # Unchanged
    ├── legacy-spec.md                    # Full legacy authoring guide (Core 1.6-1.11)
    └── latest-spec.md                    # Full latest authoring guide (Core 1.12+/Fusion)
```

All reference files are linked directly from SKILL.md. No nested cross-references between reference files. Each spec file is self-contained with all YAML examples needed to author for that spec.

## SKILL.md Content

### Kept from current SKILL.md (shared across both specs)

1. **Overview / concept definitions** - Semantic models, entities, dimensions, metrics
2. **Additional Resources** - Links to all 4 reference files
3. **Entry points** - Business Question First, Model First, Open Ended (unchanged)
4. **Metric type descriptions** - What simple, derived, cumulative, ratio, and conversion metrics are. When to use each. No YAML examples here; those live in the spec files.
5. **Filtering metrics syntax** - The Jinja template format for `Entity()`, `Dimension()`, `TimeDimension()`, `Metric()` (pending code review verification - see open questions)
6. **Validation section** - Two-stage process: `dbt parse` + semantic validation (pending code review verification - see open questions)
7. **Editing existing components** - Guidelines for modifying existing config
8. **Shared formatting rules and pitfalls** that apply to both specs

### New content: Version Routing Logic

This section goes after the overview and before the entry points. It determines which spec file to use.

```
1. Check for existing semantic layer config in the project
   - Look for top-level `semantic_models:` key (legacy) or `semantic_model:` nested on models (latest)

2. If semantic layer already exists:
   - Determine which spec is in use
   - Check dbt version for compatibility:
     a. Legacy spec + Core 1.6-1.11 → compatible, use legacy spec
     b. Legacy spec + Core 1.12+ or Fusion → compatible, but ask if they want
        to upgrade first (via `uvx dbt-autofix deprecations --semantic-layer`
        or migration guide: https://docs.getdbt.com/docs/build/latest-metrics-spec).
        They don't have to; continuing with legacy is fine.
     c. Latest spec + Core 1.12+ or Fusion → compatible, use latest spec
     d. Latest spec + Core <1.12 → incompatible. Help them upgrade to Core 1.12+.

3. If no semantic layer exists:
   - Core 1.12+ or Fusion → use latest spec (no need to ask)
   - Core 1.6-1.11 → ask if they want to upgrade to Core 1.12+ for the easier
     authoring experience. If yes, help upgrade. If no, use legacy spec.
```

### Removed from SKILL.md (moved to spec files)

- Implementation workflow (Steps 1-4)
- All YAML format reference examples
- Derived dimensions/entities syntax
- Advanced metric YAML examples
- Cross-model metrics YAML
- Spec-specific formatting rules and pitfalls

## latest-spec.md Content

Extracted from the current SKILL.md, enhanced with authoritative YAML from dbt docs. Self-contained authoring guide.

### Structure

1. **Implementation Workflow** (Steps 1-4 with latest spec YAML)
   - Step 1: Enable semantic model - `semantic_model: enabled: true` nested on model, `agg_time_dimension` at model level
   - Step 2: Define entities - `entity:` blocks on columns with `type` and `name`
   - Step 3: Define dimensions - `dimension:` blocks on columns, `granularity:` at column level for time dims
   - Step 4: Define simple metrics - `metrics:` array at model level with `type: simple`, `agg`, `expr`

2. **YAML Format Reference**
   - Complete semantic model spec
   - Derived dimensions and entities via `derived_semantics:` block
   - Advanced metric examples (all at model level or top-level `metrics:` for cross-model):
     - Derived: `expr` + `input_metrics` (with `alias`, `filter`, `offset_window`)
     - Cumulative: `input_metric` + top-level `window` / `grain_to_date` / `period_agg`
     - Ratio: top-level `numerator` / `denominator` (string or dict with `name`, `filter`, `alias`)
     - Conversion: top-level `entity`, `calculation`, `base_metric`, `conversion_metric`, `window`, `constant_properties`
   - Cross-model (top-level) metrics
   - Non-additive dimensions (via simple metric properties)
   - SCD Type II dimensions with `validity_params`

3. **Key Formatting Rules** (spec-specific)
   - `semantic_model:` block at model level with `enabled: true`
   - `agg_time_dimension:` at model level (not nested under `semantic_model`)
   - `entity:` and `dimension:` on columns
   - `granularity:` required at column level for time dimensions
   - `metrics:` array at model level for single-model metrics
   - Top-level `metrics:` key for cross-model metrics only

4. **Common Pitfalls** (spec-specific)

### Key YAML examples from dbt docs (latest spec)

**Complete semantic model:**
```yaml
models:
  - name: fact_transactions
    description: "Transaction fact table"
    semantic_model:
      enabled: true

    agg_time_dimension: transaction_date

    columns:
      - name: transaction_id
        entity:
          type: primary
          name: transaction

      - name: customer_id
        entity:
          type: foreign
          name: customer

      - name: transaction_date
        granularity: day
        dimension:
          type: time

      - name: order_country
        dimension:
          type: categorical
          name: transaction_location

    metrics:
      - name: transaction_total
        description: "The total value of the transaction."
        type: simple
        label: Transaction Total
        agg: sum
        expr: transaction_total

      - name: median_sales
        description: "The median sale of the transaction."
        type: simple
        label: Median Sales
        agg: median
        expr: transaction_total
```

**Derived semantics (expression-based dimensions/entities):**
```yaml
    derived_semantics:
      dimensions:
        - name: is_bulk
          type: categorical
          expr: "case when quantity > 10 then true else false end"
      entities:
        - name: user
          type: foreign
          expr: "substring(id_order from 2)"
```

**Simple metric with fill nulls and timespine join:**
```yaml
    metrics:
      - name: customers
        description: Count of customers
        type: simple
        label: Count of customers
        agg: count
        expr: customers
        fill_nulls_with: 0
        join_to_timespine: true
        filter: "{{ Dimension('customer__customer_total') }} >= 20"
```

**Derived metric with offset:**
```yaml
metrics:  # top-level or under model
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

**Cumulative metric:**
```yaml
metrics:
  - name: cumulative_order_total_mtd
    label: "Cumulative order total (MTD)"
    description: "The month-to-date value of all orders"
    type: cumulative
    grain_to_date: month
    input_metric: order_total
```

**Ratio metric with filter:**
```yaml
metrics:
  - name: frequent_purchaser_ratio
    description: Fraction of active users who qualify as frequent purchasers
    type: ratio
    numerator:
      name: distinct_purchasers
      filter: |
        "{{ Dimension('customer__is_frequent_purchaser') }}"
      alias: frequent_purchasers
    denominator:
      name: distinct_purchasers
```

**Conversion metric:**
```yaml
metrics:
  - name: visit_to_buy_conversion_rate_7d
    description: "Conversion rate from visiting to transaction in 7 days"
    type: conversion
    label: Visit to buy conversion rate (7-day window)
    entity: user
    calculation: conversion_rate
    base_metric:
      name: visits
      filter: "{{ Dimension('visits__referrer_id') }} = 'facebook'"
    conversion_metric: buys
    window: 7 days
    constant_properties:
      - base_property: product
        conversion_property: product
```

**SCD Type II:**
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
      - name: sales_person_id
        entity:
          type: natural
          name: sales_person
```

## legacy-spec.md Content

New file covering the legacy spec. Built from dbt docs source (`<VersionBlock lastVersion="1.99">`).

### Structure

1. **Implementation Workflow** (Steps 1-4 with legacy spec YAML)
   - Step 1: Define semantic model - top-level `semantic_models:` with `model: ref('...')`, `defaults.agg_time_dimension`
   - Step 2: Define entities - separate `entities:` array with `name`, `type`, `expr`
   - Step 3: Define dimensions - separate `dimensions:` array with `name`, `type`, `expr`, `type_params.time_granularity` for time dims
   - Step 4: Define measures and metrics - `measures:` array under semantic model, then top-level `metrics:` referencing measures via `type_params`

2. **YAML Format Reference**
   - Complete semantic model spec
   - Computed dimensions/entities via `expr` field
   - Measures: all agg types (`sum`, `min`, `max`, `average`, `sum_boolean`, `count_distinct`, `median`, `percentile`), `non_additive_dimension`, `create_metric`, `agg_params`
   - Metric examples (all top-level `metrics:` key):
     - Simple: `type_params.measure` (with `name`, `alias`, `filter`, `fill_nulls_with`, `join_to_timespine`)
     - Derived: `type_params.expr` + `type_params.metrics` (with `alias`, `filter`, `offset_window`)
     - Cumulative: `type_params.measure` + `type_params.cumulative_type_params` (`window`, `grain_to_date`, `period_agg`)
     - Ratio: `type_params.numerator` / `type_params.denominator` (string or dict with `name`, `filter`, `alias`)
     - Conversion: `type_params.conversion_type_params` (`entity`, `calculation`, `base_measure`, `conversion_measure`, `window`, `constant_properties`)
   - Cross-model metrics
   - SCD Type II dimensions with `validity_params` under `type_params`

3. **Key Formatting Rules** (spec-specific)
   - Top-level `semantic_models:` key
   - `model: ref('...')` required
   - `defaults.agg_time_dimension` for default time dimension
   - Entities, dimensions, measures as separate arrays
   - All metrics at top-level `metrics:` key, referencing measures via `type_params`

4. **Common Pitfalls** (spec-specific)

### Key YAML examples from dbt docs (legacy spec)

**Complete semantic model:**
```yaml
semantic_models:
  - name: transaction
    model: ref('fact_transactions')
    description: "Transaction fact table"
    defaults:
      agg_time_dimension: transaction_date

    entities:
      - name: transaction
        type: primary
        expr: transaction_id
      - name: customer
        type: foreign
        expr: customer_id

    dimensions:
      - name: transaction_date
        type: time
        type_params:
          time_granularity: day
      - name: transaction_location
        type: categorical
        expr: order_country

    measures:
      - name: transaction_total
        description: "The total value of the transaction."
        agg: sum
      - name: sales
        description: "The total sale of the transaction."
        agg: sum
        expr: transaction_total
      - name: median_sales
        description: "The median sale of the transaction."
        agg: median
        expr: transaction_total
```

**Simple metric referencing a measure:**
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

**Derived metric with offset:**
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

**Cumulative metric:**
```yaml
metrics:
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

**Ratio metric with filter:**
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

**Conversion metric:**
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
        constant_properties:
          - base_property: product
            conversion_property: product
```

**Non-additive dimension (MRR example):**
```yaml
    measures:
      - name: mrr
        description: Sum of all active subscription plans
        expr: subscription_value
        agg: sum
        non_additive_dimension:
          name: subscription_date
          window_choice: max
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

**Percentile measure:**
```yaml
    measures:
      - name: p99_transaction_value
        description: The 99th percentile transaction value
        expr: transaction_amount_usd
        agg: percentile
        agg_params:
          percentile: .99
          use_discrete_percentile: false
```

**SCD Type II:**
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

## best-practices.md Changes

Rewrite the existing file. Keep shared principles, add conditional advice, remove file organization section.

### Kept (shared)
- Core principles: prefer normalization, compute in metrics not rollups, start simple
- Entity design: one primary entity per semantic model, singular naming, foreign entities for joins
- Dimension guidelines: always include primary time dimension, set granularity
- Metric design: required properties, type progression (simple -> ratio -> derived -> cumulative), naming conventions
- Development workflow commands
- Anti-patterns table (updated wording)
- When to use marts

### Removed
- File organization section (two approaches: co-located vs parallel folder)

### Changed to conditional
- **Measures section** (legacy) vs **Simple metrics section** (latest):
  - Legacy: "Create measures for quantitative values you'll aggregate. Use `expr: 1` with `agg: sum` for counting records. Measures are the building blocks for all metric types."
  - Latest: "Define simple metrics directly on the semantic model for quantitative aggregations. Use `expr: 1` with `agg: count` or `agg: sum` for counting records. Simple metrics are the building blocks for advanced metric types."
- **Structure order**:
  - Legacy: "Define components consistently: entities -> dimensions -> measures"
  - Latest: "Define components consistently: entities (on columns) -> dimensions (on columns) -> simple metrics"

### Minimal inline examples
Where the advice differs by spec, include small inline YAML snippets (2-5 lines) rather than cross-referencing the spec files.

## time-spine.md

Unchanged. The time spine YAML configuration (`time_spine:` under `models:`) is the same across both specs. The only historical change was moving from a bare SQL file (`metricflow_time_spine.sql`) to YAML-configured time spines, which is orthogonal to the semantic model spec.

## Open Questions for Code Review

1. **Validation commands**: Are `dbt sl validate` and `mf validate-configs` correct for both specs? Specifically, does Fusion expose validation via `dbt sl validate`?
2. **Jinja filter template format**: Is the `{{ Dimension('entity__dim') }}`, `{{ Entity('...') }}`, `{{ TimeDimension('...', '...') }}`, `{{ Metric('...') }}` syntax identical across both specs?
3. **Non-additive dimensions in latest spec**: The dbt docs don't show a `non_additive_dimension` example for the latest spec. The simple metric parameter table lists it. Need to confirm the syntax.
4. **`create_metric` in latest spec**: The current SKILL.md has a commented-out note saying `create_metric` is not supported yet. Confirm this is still the case.
5. **Percentile in latest spec**: The simple metric parameter table shows `percentile` and `percentile_type` as direct keys. Need to confirm no `agg_params` wrapper is needed.

## Implementation Notes

- The current SKILL.md is 371 lines. After restructuring, SKILL.md will be shorter (shared concepts only), and the two spec files will each be roughly 200-300 lines.
- All YAML examples in the spec files are sourced from the dbt docs repo (`docs.getdbt.com`, `current` branch, checked 2026-02-06). Legacy examples come from `<VersionBlock lastVersion="1.99">` blocks, latest from `<VersionBlock firstVersion="2.0">` blocks.
- The `metadata: author: dbt-labs` in the frontmatter is valid per updated CLAUDE.md (metadata is an allowed field).
