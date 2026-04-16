# Edge Cases and Warnings

All edge cases discovered during dbt → LookML conversion research, with examples and recommended handling.

---

## Critical: `${TABLE}.1` Literal Bug

**Trigger:** Any metric with `SUM(1)` or `SUM(CASE WHEN ... THEN 1 END)`.

**Wrong:**
```lookml
measure: count_of_orders {
  type: sum
  sql: ${TABLE}.1 ;;  # BROKEN — .1 is not a column
}
```

**Correct:**
```lookml
measure: count_of_orders {
  type: sum
  sql: 1 ;;  # Literal — no ${TABLE}. prefix
}
```

**Detection:** A value is a literal if it matches the pattern `^\d+\.?\d*$` or is `true`, `false`, `null`, or `*`. When the aggregated expression resolves to a literal, emit it bare with no `${TABLE}.` prefix.

**Why it matters:** Looker will fail to generate SQL with `${TABLE}.1` — it's not valid column syntax.

---

## Critical: `dimension_group` Name With Grain Suffix

**Trigger:** dbt time dimension named `ordered_at_date`.

**Wrong:**
```lookml
dimension_group: ordered_at_date {  # WRONG — grain suffix in group name
  type: time
  ...
}
```

**Correct:**
```lookml
dimension_group: ordered_at {  # Strip the grain suffix
  type: time
  timeframes: [raw, date, week, month, quarter, year]
  sql: ${TABLE}.ordered_at ;;
}
```

**Why it matters:** Looker appends `_date`, `_week`, etc. automatically. A group named `ordered_at_date` creates fields like `ordered_at_date_date`, `ordered_at_date_week` — duplicated grain.

Strip any trailing `_date`, `_week`, `_month`, `_quarter`, `_year` from the dbt dimension name before using it as the `dimension_group` name.

---

## Critical: Ratio Metrics — Division by Zero

**Trigger:** Any metric with `type: ratio` or expression matching `(a) / (b)`.

**Wrong:**
```lookml
measure: average_order_value {
  type: number
  sql: ${TABLE}.order_total / ${TABLE}.count_of_orders ;;  # Zero division risk
}
```

**Correct:**
```lookml
measure: average_order_value {
  type: number
  sql: (${TABLE}.order_total) / NULLIF((${TABLE}.count_of_orders), 0) ;;
}
```

**Warning to surface:** "The metric `average_order_value` is a ratio. Generated as `type: number` with `NULLIF` in the denominator to prevent division by zero."

---

## Critical: Untranslatable Metric Types

These metric types require MetricFlow at query time and cannot be expressed in static LookML SQL.

**Never emit broken SQL.** Instead, emit this comment block:

```lookml
# ⚠️ SKIPPED: opportunity_expansion_rate_renew_won
# type: derived with input_metrics cannot be translated to LookML.
# Define this as a custom measure in Looker using pre-materialized values,
# or query it via the dbt Semantic Layer API.
```

### Untranslatable types

| Type | Why |
|------|-----|
| `type: derived` with `input_metrics:` | Requires MetricFlow to resolve input metrics at query time |
| `type: conversion` | Funnel window logic (conversion window, base/conversion measures) has no LookML analog |
| `type: cumulative` with `offset_window:` | Period-over-period window math requires MetricFlow |
| Any metric with `filter: "{{ Metric(...) }}"` | Metric-in-filter is MetricFlow-only; can't be expressed as a WHERE clause |

### Detection

```yaml
# Detect these patterns in metric YAML:
type: derived
input_metrics:
  - name: some_metric
```

```yaml
type: conversion
conversion_type_params:
  base_measure: ...
  conversion_measure: ...
```

```yaml
filter:
  - "{{ Metric('some_metric', ...) }} > 100"
```

---

## Grain Mismatch — Multi-Grain Explore

**Trigger:** User asks to join saved_query exports at different grains (e.g., daily order metrics + monthly revenue).

**Detection:** Compare the `group_by` dimensions of two saved_queries. If one groups by `__date` and another by `__month`, they're at different grains.

**Required acknowledgement before proceeding:**
> "Warning: `order_metrics` is at daily grain and `revenue_by_month` is at monthly grain. Joining them will produce misleading aggregations in Looker (daily measures fanned out to monthly denominator). Recommended: create separate explores per grain family. Continue anyway? [yes/no]"

**Recommended solution:** Create separate explores and warn about the architecture. See [composable-exports.md](./composable-exports.md).

---

## Multi-Hop Drill-Down Limitation

**Trigger:** User requests an explore with more than 2 join hops (e.g., orders → customers → accounts → segments).

**Detection:** Trace the join graph depth from the primary explore view. If any path exceeds 2 hops, flag it.

**Required acknowledgement before proceeding:**
> "This explore supports 2+ join levels. Looker users cannot drill below the grain declared in your saved_query exports without additional configuration. Do you want a drill link to a native LookML explore for detail? [yes/no]"

**If yes:** Generate a `link:` field on the relevant dimension that opens a filtered explore.

---

## Multi-Line YAML Descriptions

**Trigger:** dbt `description:` using YAML block scalar (`>`).

```yaml
description: >
  This is a very long description
  that spans multiple lines.
```

**Problem:** LookML `description:` must be a single-line string.

**Fix:** Collapse to one line, replacing line breaks with a space:
```lookml
description: "This is a very long description that spans multiple lines."
```

---

## `agg_time_dimension:` Not Surfaced

**Trigger:** dbt semantic model declares `agg_time_dimension: created_at` at the model level.

**What it means:** This is the default time dimension MetricFlow uses when no `group_by` time dim is specified.

**LookML action:** Add a comment in the generated view:
```lookml
# Note: dbt semantic model declares agg_time_dimension: created_at.
# This drives the default MetricFlow grain. In Looker, use 'created_at' as
# the primary time filter dimension for this view.
```

No structural change needed — it's metadata about intent, not a field.

---

## Saved Query — `explore_source` Must Exist

**Warning to surface:** Every saved_query's `explore_source:` target must exist as an `explore:` block in the same Looker project before the derived table can be materialized.

Show the user: "Saved query `order_metrics` targets explore `orders`. Make sure this explore is present in your project."

---

## Databricks: PERCENTILE_CONT Compatibility

**Trigger:** Metric using `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)` and target warehouse is Databricks.

**Warning to surface:** "Databricks runtime versions before 10.4 LTS do not support `PERCENTILE_CONT`. Your median metric will fail on older runtimes. Fall back to `PERCENTILE_APPROX(col, 0.5)` for broader compatibility? [yes/no]"

If yes, replace with:
```lookml
measure: median_order_value {
  type: number
  sql: PERCENTILE_APPROX(${TABLE}.order_value, 0.5) ;;
}
```

---

## Databricks: PDT Persistence Required

**Trigger:** Any derived table (saved_query converted to `explore_source`) when target warehouse is Databricks.

**Warning to surface:** "Databricks PDTs (persistent derived tables) require explicit persistence configuration. Add one of: `sql_trigger_value`, `persist_for`, or `datagroup_trigger` to the derived_table block."

Example:
```lookml
derived_table: {
  explore_source: orders { ... }
  persist_for: "24 hours"
}
```

---

## Model With No Semantic Layer Config

**Trigger:** `get_semantic_model_details` returns no results for a model.

**Ask user:**
> "Model `[name]` has no semantic layer config. Generate a bare view (sql_table_name only, no measures)? [yes/no]"

**If yes:**
```lookml
view: model_name {
  sql_table_name: `project.dataset.model_name` ;;
  # No semantic layer config found for this model.
  # Add entities, dimensions, and measures to your dbt semantic_models YAML to enable full conversion.
}
```

---

## Warehouse SQL Function Normalization

Some dbt expressions use warehouse-specific SQL. Normalize when converting:

| Expression in dbt | BigQuery | Databricks | Redshift | Snowflake |
|-------------------|----------|------------|----------|-----------|
| `DIV0(a, b)` | `SAFE_DIVIDE(a, b)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` | `DIV0(a, b)` |
| `SAFE_DIVIDE(a, b)` | `SAFE_DIVIDE(a, b)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` |
| `ZEROIFNULL(col)` | `IFNULL(col, 0)` | `COALESCE(col, 0)` | `COALESCE(col, 0)` | `ZEROIFNULL(col)` |
