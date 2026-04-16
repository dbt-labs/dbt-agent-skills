# Composable Exports — Grain Alignment Rules

Rules for converting multiple dbt saved_queries into joinable Looker views. Source: `sl-looker-bridge-analysis.md` section 3c.

---

## The Core Rule

**Saved_query exports that will be joined in a Looker explore must share:**
1. The same time grain (both daily, or both monthly — not mixed)
2. At least one shared join key (a dimension present in both exports)

Violating either rule produces misleading aggregations silently — Looker will not warn.

---

## Grain Families

Group saved_queries into grain families before generating explores:

| Grain | dbt `group_by` signal | Example dimensions |
|-------|-----------------------|-------------------|
| Transaction/event | No time group_by, or entity-level | `customer_id`, `order_id` |
| Daily | `Dimension('model__field__date')` | `ordered_at__date` |
| Weekly | `Dimension('model__field__week')` | `ordered_at__week` |
| Monthly | `Dimension('model__field__month')` | `fiscal_month__month` |
| Quarterly | `Dimension('model__field__quarter')` | `fiscal_quarter__quarter` |
| Annual | `Dimension('model__field__year')` | `fiscal_year__year` |

**Rule:** Create one `explore_source:` per grain family, not one per saved_query.

---

## Detecting Grain Conflicts

For two saved_queries A and B intended to be joined:

1. Parse the `group_by` list of each
2. Find all time dimensions (those with a grain suffix: `__date`, `__week`, etc.)
3. If A and B have time dimensions at different grains → grain conflict

**Conflict response (required acknowledgement):**
> "Warning: `[query_a]` is at daily grain and `[query_b]` is at monthly grain. Joining them will produce misleading aggregations in Looker — daily measures will fan out to each row of the monthly dimension. Recommended: create separate explores per grain family. Continue anyway? [yes/no]"

---

## Shared Join Key Detection

For two saved_queries A and B:

1. Parse the `group_by` list of each
2. Extract non-time dimensions (categorical, entity refs)
3. Find the intersection — these are candidate join keys

**Example:**

```yaml
# Query A group_by
- Dimension('opportunity_commission__fiscal_quarter')
- Dimension('opportunity__owner_geo_level')

# Query B group_by
- Dimension('opportunity_commission__fiscal_quarter')
- Dimension('opportunity__owner_geo_level')
- Dimension('opportunity__owner_manager_name')
```

Shared: `fiscal_quarter`, `owner_geo_level` — valid join on both dimensions.

Query B has an additional dimension (`owner_manager_name`) — it is at a finer grain. If you join A (coarser) to B (finer), rows in A will fan out. Warn the user.

---

## Recommended Explore Architecture

### Single-grain family (safe to join)

```lookml
explore: opportunity_commission {
  join: gtm_bookings_executive_l9fq {
    type: left_outer
    sql_on: ${opportunity_commission.fiscal_quarter} = ${gtm_bookings_executive_l9fq.fiscal_quarter}
            AND ${opportunity_commission.owner_geo_level} = ${gtm_bookings_executive_l9fq.owner_geo_level} ;;
    relationship: one_to_one  # same grain = one_to_one
  }
}
```

### Multi-grain (warn, then separate explores)

```
// ⚠️ Do NOT join these — different grains
// Create separate explores:
explore: daily_order_metrics { ... }   // daily grain
explore: monthly_revenue_metrics { ... } // monthly grain
```

---

## GTM Dashboard Pattern (internal-analytics example)

The internal-analytics GTM bookings saved_queries follow a hierarchy:

| Level | Dimensions | Grain |
|-------|-----------|-------|
| Total | `fiscal_quarter` only | Quarterly |
| Executive | `fiscal_quarter` + `owner_geo_level` | Quarterly × Geo |
| Regional Manager | `fiscal_quarter` + `geo` + `manager_name` | Quarterly × Geo × Manager |
| Manager | `fiscal_quarter` + `manager_name` + `owner_name` | Quarterly × Manager × Owner |

Each level is at quarterly grain — time-comparable. But each adds a dimension that fans out rows relative to the level above.

**Recommended architecture:**
- One explore per hierarchy level (do NOT join levels)
- Or: use a single explore with the most granular level and roll up in Looker

---

## `config: cache: enabled: false`

When a saved_query has `config: cache: enabled: false`, the export is not cached — it runs live. In LookML, this maps to **not** adding `persist_for` to the derived table.

Leave the `derived_table:` block without a persistence directive (default: no caching):
```lookml
derived_table: {
  explore_source: orders { ... }
  # No persist_for — cache disabled per dbt config
}
```

For Databricks: still need persistence config (Databricks PDTs require it). Override with `persist_for: "0 seconds"` or note the conflict to the user.
