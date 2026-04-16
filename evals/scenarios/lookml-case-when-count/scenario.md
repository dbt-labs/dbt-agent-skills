# LookML Generation — CASE WHEN Count (SUM(1) and SUM(CASE WHEN ... THEN 1))

## Background

This scenario tests the critical `${TABLE}.1` bug. The `orders` metric uses `agg: count` with `expr: "1"` (a literal), and `new_customer_orders` uses `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. Both should produce `sql: 1 ;;` — not `sql: ${TABLE}.1 ;;`.

The `food_orders` metric uses `SUM(CASE WHEN is_food_order THEN order_total END)` — this should extract the column `order_total` and produce `sql: ${TABLE}.order_total ;;`.

## Expected Outcome

The agent should:
1. Generate `orders.view.lkml` with three measures
2. For `orders` (count expr: "1"): `type: sum` or `type: count` with `sql: 1 ;;` (no `${TABLE}.1`)
3. For `new_customer_orders` (CASE WHEN ... THEN 1): `type: sum` with `sql: 1 ;;`
4. For `food_orders` (CASE WHEN ... THEN col): `type: sum` with `sql: ${TABLE}.order_total ;;`
5. Warn the user about the SUM(1) pattern and why `sql: 1` is used

## Grading Criteria

- [ ] no_table_dot_one: No `${TABLE}.1` in any generated file (critical — this is the adversarial check)
- [ ] orders_literal_sql: The `orders` measure has `sql: 1 ;;` (or is `type: count`)
- [ ] new_customer_orders_literal_sql: The `new_customer_orders` measure has `sql: 1 ;;`
- [ ] food_orders_col_sql: The `food_orders` measure has `sql: ${TABLE}.order_total ;;`
- [ ] sum_when_literal_warning: Agent surfaces a note explaining why `sql: 1` is used (not a column ref)
- [ ] redshift_table_format: `sql_table_name: marts.orders` (bare, lowercase, 2-part)
- [ ] model_file_generated: A `.model.lkml` file was written
