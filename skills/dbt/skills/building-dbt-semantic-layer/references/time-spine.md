# Add Time Spine for MetricFlow Semantic Layer

## Overview

A time spine is essential for time-based joins and aggregations in MetricFlow. It provides the foundation for time-based metrics and dimensions.

## When to Use

- Setting up a new dbt semantic layer project
- MetricFlow errors about missing time spine
- Adding time-based grouping to metrics
- Creating cumulative or time-window metrics

## Steps to Add Time Spine

### 1. Create the Time Spine Model

Create `models/marts/time_spine_daily.sql`.

**Using `dbt.date_spine` macro** (when supported by your adapter):

```sql
{{
    config(
        materialized = 'table',
    )
}}

with

base_dates as (
    {{
        dbt.date_spine(
            'day',
            "DATE('2000-01-01')",
            "DATE('2030-01-01')"
        )
    }}
),

final as (
    select
        cast(date_day as date) as date_day
    from base_dates
)

select *
from final
where date_day > dateadd(year, -5, current_date())
  and date_day < dateadd(day, 30, current_date())
```

> **Note**: `dbt.date_spine()` is not available for all adapters. If the macro isn't supported, use raw SQL with `generate_series` or your warehouse's equivalent date generation function instead.

### 2. Configure YAML for MetricFlow

Create `models/marts/_models.yml`:

```yaml
models:
  - name: time_spine_daily
    description: A time spine with one row per day, ranging from 5 years in the past to 30 days into the future.
    time_spine:
      standard_granularity_column: date_day
    columns:
      - name: date_day
        description: The base date column for daily granularity
        granularity: day
```

### 3. Build and Validate

```bash
# Build the time spine table
dbt run --select time_spine_daily

# Preview the model
dbt show --select time_spine_daily
```

Query with metrics (if metrics are defined):

```bash
# Local development (MetricFlow CLI)
mf validate-configs
mf query --metrics <your_metric> --group-by metric_time

# dbt Studio / dbt Cloud / dbt Cloud CLI
dbt sl query --metrics <your_metric> --group-by metric_time
```

## Using an Existing dim_date Model

If you have an existing date dimension model, configure it as a time spine:

```yaml
models:
  - name: dim_date
    description: An existing date dimension model used as a time spine.
    time_spine:
      standard_granularity_column: date_day
    columns:
      - name: date_day
        granularity: day
```

## Additional Granularities

### Yearly Time Spine

Create `models/marts/time_spine_yearly.sql`:

```sql
{{
    config(
        materialized = 'table',
    )
}}

with years as (
    {{
        dbt.date_spine(
            'year',
            "to_date('01/01/2000','mm/dd/yyyy')",
            "to_date('01/01/2025','mm/dd/yyyy')"
        )
    }}
),

final as (
    select cast(date_year as date) as date_year
    from years
)

select * from final
where date_year >= date_trunc('year', dateadd(year, -4, current_timestamp()))
  and date_year < date_trunc('year', dateadd(year, 1, current_timestamp()))
```

Add to `_models.yml`:

```yaml
models:
  - name: time_spine_yearly
    description: Time spine with one row per year
    time_spine:
      standard_granularity_column: date_year
    columns:
      - name: date_year
        granularity: year
```

Query with yearly granularity:

```bash
# Local development (MetricFlow CLI)
mf query --metrics orders --group-by metric_time__year

# dbt Studio / dbt Cloud / dbt Cloud CLI
dbt sl query --metrics orders --group-by metric_time__year
```

### Custom Calendars (Fiscal Year)

Create `models/marts/fiscal_calendar.sql`:

```sql
with date_spine as (
    select
        date_day,
        extract(year from date_day) as calendar_year,
        extract(week from date_day) as calendar_week
    from {{ ref('time_spine_daily') }}
),

fiscal_calendar as (
    select
        date_day,
        case
            when extract(month from date_day) >= 10
                then extract(year from date_day) + 1
            else extract(year from date_day)
        end as fiscal_year,
        extract(week from date_day) + 1 as fiscal_week
    from date_spine
)

select * from fiscal_calendar
```

Add to `_models.yml`:

```yaml
models:
  - name: fiscal_calendar
    description: A custom fiscal calendar with fiscal year and fiscal week granularities.
    time_spine:
      standard_granularity_column: date_day
      custom_granularities:
        - name: fiscal_year
          column_name: fiscal_year
        - name: fiscal_week
          column_name: fiscal_week
    columns:
      - name: date_day
        granularity: day
      - name: fiscal_year
        description: "Custom fiscal year starting in October"
      - name: fiscal_week
        description: "Fiscal week, shifted by 1 week from standard calendar"
```

Query with fiscal granularity:

```bash
# Local development (MetricFlow CLI)
mf query --metrics orders --group-by metric_time__fiscal_year

# dbt Studio / dbt Cloud / dbt Cloud CLI
dbt sl query --metrics orders --group-by metric_time__fiscal_year
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `semantic_models:` instead of `time_spine:` | Use the `time_spine:` property under `models:` |
| Missing `standard_granularity_column` | Required property to tell MetricFlow which column to use |
| Missing `granularity` on columns | Each time column needs a `granularity:` attribute |

## Reference

- [MetricFlow time spine](https://docs.getdbt.com/docs/build/metricflow-time-spine)
- [Time spine quickstart guide](https://docs.getdbt.com/guides/mf-time-spine)
