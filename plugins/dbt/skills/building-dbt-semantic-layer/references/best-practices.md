# Semantic Layer Best Practices

Synthesized from the [dbt Semantic Layer best practices guide](https://docs.getdbt.com/best-practices/how-we-build-our-metrics/semantic-layer-1-intro).

## Core Principles

1. **Prefer normalization** - Let MetricFlow denormalize dynamically for end users rather than pre-building wide tables
2. **Compute in metrics, not rollups** - Define calculations in measures and metrics instead of frozen aggregations
3. **Start simple** - Build simple metrics first before advancing to ratio and derived types

## Semantic Model Design

### Structure Order
Define components consistently: **entities → dimensions → measures**

### Entities
- Each semantic model needs exactly **one primary entity**
- Use singular naming (`order` not `order_id`) with `expr` for the column reference
- Foreign entities enable joins between semantic models

### Dimensions
- Always include a **primary time dimension** when the model has measures
- Use `expr` for computed dimensions (e.g., categorizing by thresholds)
- Set granularity at the column level for time dimensions

### Measures
- Create measures for quantitative values you'll aggregate
- Use `expr: 1` with `agg: sum` for counting records
- Measures are the building blocks for all metric types

## Metric Design

### Required Properties
Every metric needs: `name`, `description`, `label`, and `type`

### Type Progression
1. **Simple** - Single measure with optional filters (start here)
2. **Ratio** - Numerator divided by denominator
3. **Derived** - Calculations combining multiple metrics
4. **Cumulative** - Running totals or windowed aggregations

### Naming
- Use clear business-friendly labels for downstream tools
- Use double underscores to disambiguate dimensions (`orders__location`)

## File Organization

Two valid approaches:
1. **Co-located** - Semantic YAML alongside corresponding mart models
2. **Parallel folder** - Dedicated `semantic_models/` subfolder with `sem_` prefixes

Choose based on project scale and team preference.

## Development Workflow

```bash
# Refresh manifest after changes
dbt parse

# List available dimensions for a metric
dbt sl list dimensions --metrics <metric_name>   # dbt Cloud CLI
mf list dimensions --metrics <metric_name>       # MetricFlow CLI

# Test metric queries
dbt sl query --metrics <metric_name> --group-by <dimension>   # dbt Cloud CLI
mf query --metrics <metric_name> --group-by <dimension>       # MetricFlow CLI
```

## What to Avoid

| Anti-pattern | Better approach |
|--------------|-----------------|
| Building semantic models on dimension-only tables without measures | Only add primary entity for pure dimensional tables |
| Refactoring production code directly | Build in parallel, deprecate gradually |
| Pre-computing rollups in dbt models | Define calculations in metrics |
| Creating multiple time dimension buckets | Set minimum granularity, let MetricFlow handle the rest |

## When to Use Marts

Use intermediate marts strategically for:
- Grouping related tables
- Attaching measures to dimensional tables
- Complex joins that benefit from materialization

Build semantic models on staging when source data is already well-structured.
