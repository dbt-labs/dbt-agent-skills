# Semantic Layer Best Practices

Synthesized from the [dbt Semantic Layer best practices guide](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-1-intro).

## Core Principles

1. **Prefer normalization** - Let MetricFlow denormalize dynamically for end users rather than pre-building wide tables
2. **Compute in metrics, not rollups** - Define calculations in metrics instead of frozen aggregations
3. **Start simple** - Build simple metrics first before advancing to ratio and derived types

## Semantic Model Design

### Entities
- Each semantic model needs exactly **one primary entity**
- Use singular naming (`order` not `order_id`) with `expr` for the column reference
- Foreign entities enable joins between semantic models

### Dimensions
- Always include a **primary time dimension** when the model has metrics or measures
- Set granularity appropriately for time dimensions
- Use computed expressions for derived dimensions (e.g., categorizing by thresholds)

### Measures (Legacy Spec) / Simple Metrics (Latest Spec)

**Legacy spec** (dbt Core 1.6-1.11):
- Create measures for quantitative values you'll aggregate
- Use `expr: 1` with `agg: sum` for counting records
- Measures are the building blocks for all metric types
- Define components consistently: **entities -> dimensions -> measures**

**Latest spec** (dbt Core 1.12+ / Fusion):
- Define simple metrics directly on the model for quantitative aggregations
- Use `expr: 1` with `agg: count` or `agg: sum` for counting records
- Simple metrics are the building blocks for advanced metric types
- Define components consistently: **entities (on columns) -> dimensions (on columns) -> simple metrics**

## Metric Design

### Required Properties
Every metric needs: `name`, `description`, `label`, and `type`

### Type Progression
1. **Simple** - Single aggregation with optional filters (start here)
2. **Ratio** - Numerator divided by denominator
3. **Derived** - Calculations combining multiple metrics
4. **Cumulative** - Running totals or windowed aggregations

### Naming
- Use clear business-friendly labels for downstream tools
- Use double underscores to disambiguate dimensions (`orders__location`)

## Development Workflow

```bash
# Refresh manifest after changes
dbt parse

# List available dimensions for a metric
dbt sl list dimensions --metrics <metric_name>   # dbt Cloud CLI / Fusion CLI when using the dbt platform
mf list dimensions --metrics <metric_name>       # MetricFlow CLI

# Test metric queries
dbt sl query --metrics <metric_name> --group-by <dimension>
mf query --metrics <metric_name> --group-by <dimension>
```

## What to Avoid

| Anti-pattern | Better approach |
|--------------|-----------------|
| Building full semantic models on dimension-only tables | Pure dimensional tables only need a primary entity defined |
| Refactoring production code directly | Build in parallel, deprecate gradually |
| Pre-computing rollups in dbt models | Define calculations in metrics |
| Creating multiple time dimension buckets | Set minimum granularity, let MetricFlow handle the rest |
| Mixing legacy and latest spec syntax in the same project | Pick one spec and use it consistently |

## When to Use Marts

Use intermediate marts strategically for:
- Grouping related tables
- Attaching metrics to dimensional tables
- Complex joins that benefit from materialization

Build semantic models on staging when source data is already well-structured.
