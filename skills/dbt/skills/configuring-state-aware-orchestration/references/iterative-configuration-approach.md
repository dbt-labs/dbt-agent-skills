# Iterative Configuration Approach

## Principle

Configure SAO incrementally — one layer or model at a time. This makes it easy to validate, debug, and rollback each change independently.

## Recommended Order

### Step 1: Configure Source Freshness

Start with sources — this captures upstream metadata that drives SAO decisions. Source freshness is recommended even when sources are actual tables (not views), as it improves Fusion's visibility.

First, check whether sources are tables or views (if warehouse access is available):

```sql
select table_name, table_type
from information_schema.tables
where table_schema = '<source_schema>'
  and table_name in ('<table1>', '<table2>')
```

Then configure freshness. Set defaults at the source level; override per-table as needed:

```yaml
sources:
  - name: raw_data
    config:
      freshness:
        warn_after: {count: 12, period: hour}
        error_after: {count: 24, period: hour}
      loaded_at_field: _etl_loaded_at    # default for all tables
    tables:
      - name: orders                      # inherits source-level config
      - name: events
        loaded_at_query: |                # override for this table
          select max(event_timestamp)
          from {{ this }}
```

**If a source is a view:** `loaded_at_field` or `loaded_at_query` is **required** — Fusion treats views as "always fresh" without it.

**If a source is a table:** `loaded_at_field` or `loaded_at_query` is **recommended** — Fusion can detect freshness from warehouse metadata automatically, but explicit config improves accuracy.

### Step 2: Project-Level Defaults

Set a conservative default in `dbt_project.yml`:

```yaml
models:
  +freshness:
    build_after:
      count: 4
      period: hour
      updates_on: all
```

This gives every model a baseline. You'll override or opt out where needed.

### Step 3: Evaluate Views as Control Points

Not all views should be opted out of `build_after`. Views that are **fan-out hubs** (many downstream dependents) or **coherence points** (joining multiple upstreams that should advance together) are SAO leverage points — configuring `build_after` on them throttles downstream churn.

**For simple passthrough views** (low fan-out, cheap downstream), opt them out:

```yaml
models:
  project_name:
    staging:
      +freshness: null       # most staging views are simple passthroughs
```

**For views that gate expensive downstream work**, configure them:

```yaml
# In schema.yml for the intermediate layer
models:
  - name: int_order_enriched    # joins orders + customers + FX rates, fans out to 5 marts
    config:
      freshness:
        build_after:
          count: 4
          period: hour
          updates_on: all       # wait for all inputs to advance together
```

**Decision heuristic for each view:**
1. Does it fan out to many downstream models? → configure `build_after`
2. Does it join multiple upstreams that should advance together? → configure with `updates_on: all`
3. Does it gate downstream incremental models, tests, or snapshots? → configure `build_after`
4. Is it a simple passthrough with cheap downstream? → opt out with `freshness: null`

### Step 4: Layer-Level Overrides

If a specific layer (e.g., marts) needs different settings than the project default:

```yaml
models:
  project_name:
    marts:
      +freshness:
        build_after:
          count: 2
          period: hour
```

### Step 5: Per-Model Overrides

For models that need special treatment (Category 2 or 3 from classification):

```yaml
models:
  - name: fct_critical_dashboard
    config:
      freshness:
        build_after:
          count: 30
          period: minute
          updates_on: any
```

### Step 6: Validate After Each Step

After each change:
1. Run `dbt compile` to check syntax
2. Review the compiled config for the affected models
3. Confirm with the user before moving to the next step

## Presenting Changes to the User

Before writing any file, show a clear diff:

```
I'll add the following to dbt_project.yml:

  models:
+   +freshness:
+     build_after:
+       count: 4
+       period: hour
+       updates_on: all

This sets a project-wide default: models only rebuild when ALL upstream
dependencies have fresh data, checking every 4 hours.

Shall I apply this?
```

## Rollback

If a config causes issues:

1. **Opt out the problematic model:** Set `freshness: null` on it
2. **Revert the file change:** Use git to restore the previous version
3. **Re-validate:** Run `dbt compile` to confirm the project is clean

## Measuring SAO Effectiveness

After SAO is deployed and jobs have run, use the dbt MCP Discovery and Admin API tools to check whether SAO is actually saving compute.

**Expected benchmarks:** Simply enabling SAO with no configs typically saves ~10% compute. With `build_after` and source freshness configured, expect ~30% savings. Fully tuned projects have seen 50%+ savings. If the numbers are significantly below these ranges, the configs may need tuning.

### Check Model Execution History

Use `get_model_performance` to see how often a model is being executed vs. skipped over recent runs:

```
Tool: get_model_performance
Input: model_name: <name>
```

Look for patterns in the execution history:
- **Runs where the model was skipped** (reused from a prior run) indicate SAO is working — the model didn't rebuild because upstream data hadn't changed
- **Runs where the model executed** indicate upstream freshness triggered a rebuild
- A high skip/reuse rate means SAO is saving compute effectively

### Check Model Health Signals

Use `get_model_health` to get a holistic view of a model's run status and source freshness:

```
Tool: get_model_health
Input: model_name: <name>
```

This surfaces run status, test results, and upstream source freshness together — useful for spotting models that are rebuilding too often (freshness threshold too low) or never skipping (may need source freshness config).

### Check Job Run Details

Use `get_job_run_details` to see overall job execution patterns:

```
Tool: get_job_run_details
Input: job_run_id: <id>
```

Compare run duration before and after SAO enablement. Shorter runs with the same model count suggest SAO is skipping models effectively.

Use `list_jobs_runs` to pull recent runs for a job and compare durations over time.

### Check Source Freshness Status

Use `get_all_sources` or `get_source_details` to verify source freshness is being tracked:

```
Tool: get_all_sources
```

```
Tool: get_source_details
Input: source_name: <name>
```

If source freshness status is missing or stale, SAO may not be getting the upstream signals it needs — revisit the source freshness configuration.

### Tuning Based on Results

| Observation | Likely Issue | Adjustment |
|-------------|-------------|------------|
| Model never skips | `build_after` interval too short, or source freshness not configured | Increase interval or add source freshness config |
| Model skips too often (data is stale for consumers) | `build_after` interval too long | Decrease interval or switch to `updates_on: any` |
| Job duration unchanged after SAO | Views not evaluated as control points, or all sources refresh every cycle | Check if key views are fan-out hubs worth configuring; focus on models with infrequent source updates |
| Source freshness shows "always fresh" | Source is a view without `loaded_at_field`/`loaded_at_query` | Add explicit freshness detection for view sources |

## When to Stop Iterating

Configuration is complete when:
- Sources have freshness configs (recommended for all, required for views)
- All materialized models (tables, incrementals) have appropriate `build_after` settings
- Views evaluated as control points (configured or opted out as appropriate)
- The user has confirmed the settings for any Category 3 models
- `dbt compile` passes cleanly
