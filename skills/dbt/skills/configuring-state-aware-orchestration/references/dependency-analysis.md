# Dependency Analysis

## Overview

SAO effectiveness depends on understanding the model dependency graph. Models with many upstream dependencies benefit most from `updates_on: all` (wait for everything), while models in critical paths may need `updates_on: any` (react to anything).

## Analyzing the DAG

### Direct Dependencies

Read model SQL files and look for:
- `{{ ref('model_name') }}` — model-to-model dependency
- `{{ source('source_name', 'table_name') }}` — model-to-source dependency

### Dependency Counts

For each model, count:

| Metric | How to Get | Why It Matters |
|--------|-----------|----------------|
| Upstream parent count | `get_model_parents` or read SQL refs | More parents → more benefit from `updates_on: all` |
| Downstream child count | `get_model_children` | High fanout models affect many downstream — consider `any` if critical |
| Source dependency count | Count `source()` calls | Models directly on sources are most affected by source refresh frequency |
| Transitive depth | Trace full lineage | Deep models may already be "buffered" by intermediate layers |

### Dependency Patterns

**Fan-in (many parents → one model):**
```
stg_orders ──┐
stg_customers ─┤── fct_order_summary
stg_products ──┘
```
Best candidate for `updates_on: all` — wait for all sources before rebuilding.

**Fan-out (one model → many children):**
```
              ┌── report_daily_sales
fct_orders ───┤── report_weekly_summary
              └── dashboard_cache
```
If `fct_orders` is configured with `updates_on: all`, all downstream models wait too. Consider whether downstream consumers can tolerate the delay.

**Chain (linear dependency):**
```
source → stg_orders → int_order_metrics → fct_orders → report
```
In a simple chain, configure `build_after` on the models where the cost impact is highest. Views in the chain may still be useful control points if they gate expensive downstream work.

**Diamond (shared upstream):**
```
stg_a ──┐         ┌── fct_combined
        ├── int_x ─┤
stg_b ──┘         └── fct_other
```
Both fact models share `int_x`. If `int_x` uses `updates_on: all`, it won't rebuild until both `stg_a` and `stg_b` have new data — which cascades to both downstream facts.

## Which Models to Configure

**DO configure `build_after` on:**
- Table-materialized models (mart layer, facts, dimensions)
- Incremental models
- **Views that are DAG leverage points** — fan-out hubs, coherence points (joining multiple upstreams), or views that gate expensive downstream work. The value isn't skipping the view rebuild (views are cheap) — it's controlling when downstream models are triggered.
- Any model where skipping a rebuild saves meaningful compute

**Consider carefully before configuring:**
- Simple passthrough views with low fan-out — usually not worth it
- Views that aren't gating points in your job scopes

**DO NOT configure `build_after` on:**
- Ephemeral models — compiled inline; no separate build step
- Python models — not supported by SAO

## Analyzing Source Refresh Patterns

Ask the user or check documentation for:

1. **How often does each source get new data?** (hourly ELT, daily batch, real-time CDC)
2. **Is arrival time predictable?** (fixed schedule vs. variable)
3. **Are there late-arriving records?** (impacts `loaded_at_field` reliability)

This information directly determines appropriate `build_after` intervals:
- Sources refreshing hourly → `build_after` of 2-4 hours is reasonable
- Sources refreshing daily → `build_after` of 1 day
- Real-time/CDC sources → shorter intervals or `updates_on: any`
