# SAO Fundamentals

## What Is State-Aware Orchestration?

State-Aware Orchestration (SAO) is a Fusion engine feature that tracks metadata about when models and sources were last updated. On each job run, SAO checks whether upstream dependencies have new data — if not, it skips the model rebuild entirely, saving compute costs.

### Expected Savings

| Configuration Level | Typical Compute Savings |
|---|---|
| SAO enabled with no freshness configs | ~10% |
| SAO with `build_after` and source freshness configured | ~30% |
| Fully tuned (optimized intervals, `updates_on: all` where appropriate) | 50%+ possible |

Simply enabling SAO on a deploy job provides baseline savings with zero config changes. Adding `build_after` rules and source freshness configs significantly increases the skip rate by giving Fusion better metadata to make decisions.

## How It Works

1. **Fusion tracks metadata state** — timestamps of when each model/source last had new data
2. **On job run**, SAO compares current upstream freshness against `build_after` thresholds
3. **If upstream is stale** (no new data within the `build_after` window), the model is skipped
4. **If upstream is fresh**, the model rebuilds normally

## Core Concepts

### `build_after`

A time interval that defines how long to wait before considering upstream data "stale enough" to skip a rebuild.

| Parameter | Values | Jinja Support |
|-----------|--------|---------------|
| `count` | Positive integer | Yes |
| `period` | `minute`, `hour`, `day` | Yes |
| `updates_on` | `any`, `all` | **No** (must be literal) |

Both `count` and `period` are required together.

### `updates_on`

Controls the trigger logic for when a model should rebuild:

- **`any` (default):** Rebuild when ANY upstream dependency has fresh data. More frequent rebuilds, fresher data, higher cost.
- **`all`:** Rebuild only when ALL upstream dependencies have fresh data. Fewer rebuilds, lower cost, slight latency trade-off.

**Recommendation:** Default to `all` for cost optimization. Use `any` only when business requirements demand the freshest possible data (e.g., real-time dashboards, SLA-bound reports).

### Source Freshness Detection

SAO needs to know when source data was last updated. Configuring source freshness is **recommended** — it captures metadata that drives SAO all the way upstream, giving Fusion better visibility into data changes.

**Tables vs. Views:** When `loaded_at_field` and `loaded_at_query` are not set, SAO and `dbt source freshness` fall back to adapter-specific warehouse metadata to detect when source data changed. This only works for actual tables — **database views are treated as "always fresh"** because warehouse metadata cannot determine view freshness.

**Warehouse metadata used for automatic freshness detection:**

| Warehouse | Metadata Table | Column |
|-----------|---------------|--------|
| BigQuery | `INFORMATION_SCHEMA.TABLE_STORAGE` | `storage_last_modified_time` |
| Databricks | `system.information_schema.tables` | `last_altered` |
| Redshift | `SHOW TABLES FROM SCHEMA` | `last_modified_time` |
| Snowflake | `INFORMATION_SCHEMA.TABLES` | `LAST_ALTERED` |

You cannot tell from YAML alone whether a source is a table or view — query `information_schema.tables` (or the equivalent for your warehouse) if access is available.

| Source Type | Freshness Detection | `loaded_at_field`/`loaded_at_query` Needed? |
|-------------|--------------------|--------------------------------------------|
| Table | Automatic via warehouse metadata (see table above) | Recommended (improves accuracy), not strictly required |
| View | None (treated as "always fresh") | **Required** for SAO to work correctly |

**Two mechanisms for explicit freshness detection:**

**`loaded_at_field`** — A column in the source table whose max value indicates the last load time:
```yaml
sources:
  - name: raw_data
    config:
      freshness:
        warn_after: {count: 12, period: hour}
        error_after: {count: 24, period: hour}
      loaded_at_field: _etl_loaded_at    # applies to all tables in this source
```

**`loaded_at_query`** — Custom SQL returning a single timestamp:
```yaml
sources:
  - name: raw_data
    tables:
      - name: orders
        loaded_at_query: |               # per-table override
          select max(ingested_at)
          from {{ this }}
          where ingested_at >= current_timestamp - interval '3 days'
```

**Freshness config inheritance:** Settings defined at the source level (`loaded_at_field`, `warn_after`, `error_after`) flow down to all tables under that source. Table-level settings override the source-level defaults.

**Rules:**
- Use `loaded_at_field` or `loaded_at_query` per table, never both
- `loaded_at_query` is better for late-arriving data (use a lookback window)
- `loaded_at_field` is simpler and works well for append-only tables with reliable timestamps
- At least `warn_after` or `error_after` must be set for freshness checks to execute
- Use a `filter` config for expensive full-table scans

### Freshness SLAs (`warn_after` / `error_after`)

Optional thresholds that alert when source data hasn't been updated within expected windows:

```yaml
freshness:
  warn_after: {count: 12, period: hour}
  error_after: {count: 24, period: hour}
```

These are monitoring tools — they don't control whether models rebuild.

### Opting Out

Set `freshness: null` on a model to disable inherited `build_after` rules. The model falls back to default behavior: rebuild whenever there's any upstream code or data change.

```yaml
models:
  - name: always_rebuild_model
    config:
      freshness: null
```

## SAO and Job Types

| Job Type | SAO Supported | Notes |
|----------|---------------|-------|
| Deploy job | Yes | Primary target for SAO |
| CI job | No | Runs on PR; always builds |
| Merge job | No | Runs on merge; always builds |

## SAO and Model Types

| Model Type | SAO Supported | Notes |
|------------|---------------|-------|
| SQL model | Yes | Full support |
| Python model | No | Not supported |

## Relationship Between `build_after` and Job Schedule

The `build_after` interval should be calibrated to the job's cron schedule. If a job runs every hour, a `build_after` of 4 hours means a model will only rebuild every ~4 hours (when the cumulative freshness exceeds the threshold), even though the job itself runs hourly.

**Example:** Job runs hourly. Model has `build_after: {count: 4, period: hour}`. Sources update every 6 hours.
- Hours 1-3: SAO skips the model (no new source data)
- Hour 4+: If source updated, model rebuilds
- Result: Model rebuilds ~once per source refresh instead of every hour
