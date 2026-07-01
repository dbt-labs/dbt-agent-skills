# YAML Structure Reference

## Configuration Hierarchy

SAO freshness configs follow dbt's standard config inheritance. More specific configs override less specific ones:

```
dbt_project.yml (project-wide defaults)
  └── dbt_project.yml per-folder (layer overrides)
      └── model YAML schema.yml (per-model overrides)
          └── SQL config() block (inline override)
```

## Project-Level Defaults (`dbt_project.yml`)

Set broad defaults under the `models:` key using `+freshness`:

```yaml
models:
  +freshness:
    build_after:
      count: 4
      period: hour
      updates_on: all
```

### Per-Folder Overrides

Override for specific layers using the project name and folder path:

```yaml
models:
  +freshness:
    build_after:
      count: 4
      period: hour
      updates_on: all

  jaffle_shop:        # must match `name:` in dbt_project.yml
    staging:
      +freshness:     # simple passthrough views can opt out;
        null          # but evaluate fan-out hubs before blanket opt-out
    marts:
      +freshness:
        build_after:
          count: 1
          period: hour
          updates_on: any
```

**Important:** The folder name under `models:` must match the project `name:` field in `dbt_project.yml`, not the directory name on disk (though they're often the same).

## Model-Level YAML (`models/<layer>/schema.yml`)

Configure individual models using `config.freshness`:

```yaml
models:
  - name: dim_customers
    config:
      freshness:
        build_after:
          count: 12
          period: hour
          updates_on: all

  - name: fct_orders
    config:
      freshness:
        build_after:
          count: 1
          period: hour
          updates_on: any

  - name: always_rebuild_model
    config:
      freshness: null    # opt out of inherited build_after
```

**Note:** The `config:` wrapper is required in model YAML. This is `config.freshness.build_after`, NOT `freshness.build_after` at the top level of the model definition.

## SQL Config Block (`models/*.sql`)

Configure inline in the model's SQL file:

```sql
{{
    config(
        freshness={
            "build_after": {
                "count": 4,
                "period": "hour",
                "updates_on": "all"
            }
        }
    )
}}

select ...
```

Opt out inline:

```sql
{{ config(freshness=none) }}
```

## Source Freshness (`models/<layer>/schema.yml`)

Source-level freshness configuration for SAO:

```yaml
sources:
  - name: raw_data
    config:
      freshness:
        warn_after: {count: 12, period: hour}
        error_after: {count: 24, period: hour}
      loaded_at_field: _etl_loaded_at
    tables:
      - name: orders
        # Table-level overrides
        loaded_at_query: |
          select max(ingested_at)
          from {{ this }}
          where ingested_at >= current_timestamp - interval '3 days'
      - name: customers
        # Inherits source-level loaded_at_field
```

**Rules:**
- `loaded_at_field` OR `loaded_at_query` — never both on the same table
- `loaded_at_query` must return a single timestamp value
- Multi-line `loaded_at_query` requires YAML block format (`|`)
- `warn_after` and `error_after` are optional monitoring thresholds
- Both `count` and `period` required for `warn_after`/`error_after`

## Complete Example

A full project configuration combining all levels:

```yaml
# dbt_project.yml
name: jaffle_shop
version: '1.0.0'

models:
  # Project-wide default: rebuild after 4 hours, only when all upstream fresh
  +freshness:
    build_after:
      count: 4
      period: hour
      updates_on: all

  jaffle_shop:
    staging:
      # Views don't need build_after
      +freshness: null
    marts:
      # Marts rebuild more frequently
      +freshness:
        build_after:
          count: 2
          period: hour
          updates_on: all
```

```yaml
# models/marts/schema.yml
models:
  - name: fct_active_incidents
    description: Real-time incident tracker
    config:
      freshness:
        build_after:
          count: 30
          period: minute
          updates_on: any    # critical dashboard, rebuild ASAP
```

```yaml
# models/staging/schema.yml
sources:
  - name: raw_incidents
    config:
      freshness:
        warn_after: {count: 1, period: hour}
        error_after: {count: 4, period: hour}
      loaded_at_field: _loaded_at
    tables:
      - name: incidents
      - name: incident_updates
```

## Parameter Quick Reference

| Parameter | Location | Required | Values | Jinja |
|-----------|----------|----------|--------|-------|
| `build_after.count` | model config | Yes (with period) | Positive integer | Yes |
| `build_after.period` | model config | Yes (with count) | `minute`, `hour`, `day` | Yes |
| `build_after.updates_on` | model config | No (default: `any`) | `any`, `all` | **No** |
| `loaded_at_field` | source config | No | Column name string | Yes |
| `loaded_at_query` | source/table config | No | SQL returning timestamp | Yes |
| `warn_after.count` | source freshness | Yes (with period) | Positive integer | No |
| `warn_after.period` | source freshness | Yes (with count) | `minute`, `hour`, `day` | No |
| `error_after.count` | source freshness | Yes (with period) | Positive integer | No |
| `error_after.period` | source freshness | Yes (with count) | `minute`, `hour`, `day` | No |
| `freshness: null` | model config | — | Opts out of inherited config | — |
