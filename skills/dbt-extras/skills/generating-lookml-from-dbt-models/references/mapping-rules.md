# dbt → LookML Mapping Rules

Complete reference for converting dbt Semantic Layer YAML to LookML. Source of truth: osi-tool `osi_to_lookml.py` + `expression_parser.py`.

---

## Entity Mapping

| dbt entity type | LookML output | Notes |
|----------------|--------------|-------|
| `primary` | `dimension { type: number; primary_key: yes; sql: ${TABLE}.col ;; }` | Always `type: number` |
| `foreign` | `dimension { type: number; sql: ${TABLE}.col ;; }` | No `primary_key` |
| `unique` | Same as `primary` | Treat as primary for LookML purposes |
| `natural` | `dimension { type: string; sql: ${TABLE}.col ;; }` | Natural key, no special treatment |

---

## Dimension Mapping

### Time dimensions

```yaml
# dbt
- name: ordered_at
  type: time
  expr: ordered_at
```

```lookml
# LookML
dimension_group: ordered_at {
  type: time
  timeframes: [raw, date, week, month, quarter, year]
  sql: ${TABLE}.ordered_at ;;
}
```

**Critical:** The dimension_group name must NOT include the grain suffix. `ordered_at_date` in dbt → group name `ordered_at` in LookML. The grain suffix (`_date`, `_week`, etc.) is appended automatically by Looker.

For Databricks: always add `datatype: timestamp` to dimension_group blocks.

### Categorical dimensions — type inference

| Field name pattern | LookML type | Example |
|-------------------|-------------|---------|
| `is_*` or `has_*` | `yesno` | `is_active`, `has_discount` |
| `*_id` | `number` | `customer_id`, `order_id` |
| Primary key column | `number` | Any pk column |
| `*price*`, `*cost*`, `*total*`, `*amount*`, `*revenue*`, `*spend*`, `*tax*`, `*profit*` | `number` | `list_price`, `order_total` |
| `*quantity*`, `*count*`, `*number*`, `*rate*` | `number` | `item_quantity` |
| Everything else | `string` | `status`, `country` |

---

## Measure / Metric Mapping

### Simple aggregations

| dbt expression | LookML `type:` | LookML `sql:` | Notes |
|----------------|---------------|--------------|-------|
| `SUM(col)` | `sum` | `${TABLE}.col` | |
| `SUM(1)` | `sum` | `1` | Literal — do NOT write `${TABLE}.1` |
| `COUNT(col)` | `count` | `${TABLE}.col` | |
| `COUNT(*)` | `count` | `*` | |
| `COUNT(DISTINCT col)` | `count_distinct` | `${TABLE}.col` | |
| `AVG(col)` | `average` | `${TABLE}.col` | |
| `MIN(col)` | `min` | `${TABLE}.col` | |
| `MAX(col)` | `max` | `${TABLE}.col` | |
| `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)` | `median` | `${TABLE}.col` | |
| `PERCENTILE_CONT(other) WITHIN GROUP (ORDER BY col)` | `number` | raw SQL | Non-median percentile |

### CASE WHEN patterns

| dbt expression | LookML `type:` | LookML `sql:` |
|----------------|---------------|--------------|
| `SUM(CASE WHEN cond THEN 1 ELSE 0 END)` | `sum` | `1` ← literal |
| `SUM(CASE WHEN cond THEN 1 END)` | `sum` | `1` ← literal |
| `SUM(CASE WHEN cond THEN col END)` | `sum` | `${TABLE}.col` |
| `SUM(CASE WHEN cond THEN col ELSE 0 END)` | `sum` | `${TABLE}.col` |

**The `${TABLE}.1` bug:** Never write `sql: ${TABLE}.1 ;;`. When the aggregated value is a literal `1`, `true`, `false`, or any numeric literal, write `sql: 1 ;;` (no `${TABLE}.` prefix).

Literal detection: a value is a literal if it matches `^\d+\.?\d*$` or is `true`, `false`, `null`, or `*`.

### Ratio metrics

```yaml
# dbt — ratio
type: ratio
numerator:
  name: order_total
denominator:
  name: count_of_orders
```

Or inline expression: `(order_total) / (count_of_orders)`

```lookml
# LookML
measure: average_order_value {
  type: number
  sql: (${TABLE}.order_total) / NULLIF((${TABLE}.count_of_orders), 0) ;;
  description: "..."
}
```

Always wrap denominator in `NULLIF(..., 0)` to prevent division-by-zero errors.

### Warehouse-specific safe division

When a metric expression uses warehouse-specific division functions, normalize to the target warehouse:

| Source function | BigQuery output | Databricks output | Redshift output | Snowflake output |
|----------------|----------------|------------------|----------------|-----------------|
| `DIV0(a, b)` | `SAFE_DIVIDE(a, b)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` | `DIV0(a, b)` |
| `SAFE_DIVIDE(a, b)` | `SAFE_DIVIDE(a, b)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` | `a / NULLIF(b, 0)` |

---

## sql_table_name Formatting

| Warehouse | Format | Example |
|-----------|--------|---------|
| BigQuery | `` `project.dataset.table` `` | `` `jaffle_shop.marts.orders` `` |
| Databricks (Unity Catalog) | `` `catalog.schema.table` `` | `` `main.marts.orders` `` |
| Databricks (Hive Metastore) | `` `schema.table` `` | `` `marts.orders` `` |
| Snowflake | `DATABASE.SCHEMA.TABLE` | `JAFFLE_SHOP.MARTS.ORDERS` |
| Redshift | `schema.table` | `marts.orders` |

---

## Metric → View Assignment (4-priority heuristic)

When a metric doesn't name its semantic model explicitly:

1. **Explicit qualifier** — `orders.order_cost` in expression → `orders` view
2. **Entity qualifier pattern** — `order_id__is_food_order` → entity `order_id` → find view that has `order_id` as primary entity
3. **Agg column match** — extracted column `amount` matches field `amount` on `order_items` view
4. **Token overlap** — field-name tokens from metric expression vs. all view fields; most matches wins

**Priority 0** (checked before all): metric name exactly equals a view name (e.g., metric `orders` with `SUM(1)` → `orders` view).

Unmatched metrics fall back to the first/primary view.

---

## Saved Query → Native Derived Table

```yaml
# dbt saved_query
- name: order_metrics
  query_params:
    metrics:
      - orders
      - order_total
    group_by:
      - Dimension('orders__ordered_at__date')
  exports:
    - name: order_metrics
      config:
        export_as: table
```

```lookml
view: order_metrics {
  derived_table: {
    explore_source: orders {
      column: ordered_at_date { field: orders.ordered_at_date }
      column: orders          { field: orders.orders }
      column: order_total     { field: orders.order_total }
    }
  }

  dimension_group: ordered_at {
    type: time
    timeframes: [raw, date, week, month, quarter, year]
    sql: ${TABLE}.ordered_at_date ;;
  }

  measure: orders {
    type: sum
    sql: ${TABLE}.orders ;;
  }

  measure: order_total {
    type: sum
    sql: ${TABLE}.order_total ;;
  }
}
```

### Resolving `group_by` dimension refs

dbt group_by syntax: `Dimension('model__field__grain')` or `Dimension('model__field')`

Resolution:
- `orders__ordered_at__date` → view: `orders`, field: `ordered_at`, grain: `date`
- In `explore_source`, reference as `field: orders.ordered_at_date`

### Resolving `where:` filter refs

```yaml
where:
  - "{{ Dimension('opportunity_commission__is_last_9_fiscal_quarters') }} = True"
```

Steps:
1. Extract model `opportunity_commission`, field `is_last_9_fiscal_quarters`
2. Look up which view in the explore exposes this field
3. Emit: `filters: [opportunity_commission.is_last_9_fiscal_quarters: "Yes"]`

Boolean mapping: `= True` → `"Yes"`, `= False` → `"No"`.
