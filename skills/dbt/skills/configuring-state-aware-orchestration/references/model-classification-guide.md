# Model Classification Guide

## Classification Framework

For each model, classify into one of three categories to determine the appropriate `updates_on` setting.

### Category 1: Cost-Optimized (`updates_on: all`)

**Use for most models.** Rebuild only when ALL upstream dependencies have fresh data.

**Signals:**
- Table or incremental materialization
- Multiple upstream dependencies (fan-in pattern)
- No real-time SLA requirements
- Not directly serving a live dashboard
- Analytical/reporting models with batch consumers
- Dimension tables that change infrequently

**Examples:**
- `dim_customers` — dimension table updated from batch source
- `fct_monthly_revenue` — aggregation model, consumers tolerate daily lag
- `int_order_enriched` (if materialized as table) — intermediate aggregation

### Category 2: Freshness-Priority (`updates_on: any`)

**Use selectively.** Rebuild when ANY upstream dependency has fresh data.

**Signals:**
- Serves a customer-facing dashboard with freshness SLA
- Has external consumers (APIs, exports, reverse ETL)
- Tagged as `critical`, `real-time`, or similar
- Has a contract with freshness guarantees
- Small model that's cheap to rebuild anyway
- Source of truth for operational decisions (not just analytics)

**Examples:**
- `fct_active_incidents` — operational dashboard, needs fastest refresh
- `dim_inventory_levels` — drives purchase decisions, needs near-real-time
- `fct_order_status` — customer-facing order tracker

### Category 3: Needs Human Review

**Escalate to the user.** You can recommend, but don't configure without confirmation.

**Signals:**
- Complex fan-out (many downstream dependents across different SLA tiers)
- Model serves both real-time and batch consumers
- Model has external consumers you don't have visibility into
- `access: public` with unknown downstream users
- Model is part of a cross-project dependency (dbt Mesh)
- Unclear source refresh patterns

**How to present:**
```
I'm unsure about `fct_orders`:
- It has 8 downstream dependents across mart and reporting layers
- It's marked `access: public`
- Some children seem analytical (batch OK), others may be operational

Recommendation: `updates_on: all` with `build_after: {count: 2, period: hour}`
But this depends on whether any downstream consumer needs sub-2-hour freshness.

What are the freshness requirements for models consuming `fct_orders`?
```

## Decision Tree

```
Is the model ephemeral?
├── Yes → SKIP (compiled inline, no build step)
└── No → Is it a view?
    ├── Yes → Is it a fan-out hub (many downstream dependents)?
    │   ├── Yes → Configure build_after (leverage point — throttles downstream churn)
    │   └── No → Does it join multiple upstreams that should advance together?
    │       ├── Yes → Configure with updates_on: all (coherence point)
    │       └── No → Usually SKIP (simple passthrough, low impact)
    └── No → Is the model materialized (table/incremental)?
        └── Yes → Does it serve a real-time dashboard or have an SLA?
            ├── Yes → updates_on: any (Category 2)
            └── No → Does it have complex fan-out or public access?
                ├── Yes → REVIEW with user (Category 3)
                └── No → updates_on: all (Category 1)
```

### Views as DAG Control Points

Setting `build_after` on a view doesn't skip "rebuilding" the view itself (views are cheap). The value is **controlling when that node is considered eligible to run, which gates everything downstream.** An intermediate view that fans out to many mart tables is a leverage point — configuring it can significantly reduce downstream churn.

**When to configure `build_after` on a view:**

| Signal | Why It Matters | Recommendation |
|--------|---------------|----------------|
| High fan-out (many downstream dependents) | Small upstream change causes large downstream recompute | Add `build_after` to throttle downstream frequency |
| Joins multiple upstreams (coherence point) | Rebuilding on any single upstream change produces partially-updated results | Set `updates_on: all` so all inputs advance together |
| Gates downstream incremental models, tests, or snapshots | View "rebuild" triggers expensive downstream work | Add `build_after` to reduce noisy downstream runs |
| SLO is slower than upstream change frequency | Upstream changes more often than consumers need | `build_after` encodes the actual SLO |

**When NOT to configure a view:**
- It's a simple passthrough with low fan-out and cheap downstream models
- It's not actually a gating point in your job scopes (job selects downstream directly)
- You're trying to work around unreliable upstream source freshness (fix the source config instead)

## Classification Checklist

For each model, check these attributes:

| Check | Where to Find | Impact on Classification |
|-------|---------------|------------------------|
| Materialization | `dbt_project.yml` or model `config()` | Ephemeral → skip; views → evaluate as control point; table/incremental → classify |
| Tags | Model YAML or `config(tags=[...])` | `critical`, `sla`, `real-time` → Category 2 |
| Access level | Model YAML `access:` | `public` → Category 3 (review) |
| Contract | Model YAML `contract: {enforced: true}` | Suggests stricter freshness needs |
| Group | Model YAML `group:` | Group membership may imply shared SLA |
| Downstream count | `get_model_children` | High fanout → Category 3 |
| Source dependencies | Read SQL for `source()` calls | Direct source models are first to benefit from SAO |
| Semantic model | Check if model is referenced in semantic model YAML | May serve metrics layer → discuss SLA |

## Choosing `build_after` Intervals

After classifying `updates_on`, choose the interval:

| Model Characteristic | Suggested Interval | Reasoning |
|---------------------|-------------------|-----------|
| Daily batch sources | `{count: 1, period: day}` | Match source cadence |
| Hourly ELT sources | `{count: 4, period: hour}` | Good balance of cost vs freshness |
| Near-real-time needs | `{count: 30, period: minute}` | Tight window, use sparingly |
| Slowly changing dimensions | `{count: 12, period: hour}` or `{count: 1, period: day}` | Dimensions rarely change |
| Heavy compute models | Longer intervals | Maximize savings on expensive rebuilds |

Always validate intervals against the job's cron schedule. A `build_after` shorter than the job interval has no effect.
