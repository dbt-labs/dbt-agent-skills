# LookML Generation — Ratio Metric (average_order_value)

## Background

The `customers` semantic model has a `type: ratio` metric (`average_order_value = lifetime_spend / count_lifetime_orders`). This tests correct ratio handling: `type: number` with `NULLIF` in the denominator, plus the associated warning message.

## Expected Outcome

The agent should:
1. Generate `customers.view.lkml` with three measures: two `sum` measures and one `number` ratio
2. Warn the user that `average_order_value` is a ratio metric and explain NULLIF protection
3. Use `type: number` with `NULLIF` for the ratio measure
4. Use BigQuery backtick-quoted `sql_table_name`

## Grading Criteria

- [ ] ratio_type_number: `average_order_value` measure has `type: number`
- [ ] ratio_has_nullif: The `average_order_value` SQL contains `NULLIF`
- [ ] ratio_warning_shown: Agent shows a warning or note about the ratio metric and division-by-zero protection
- [ ] numerator_sum_correct: `lifetime_spend_pretax` measure is `type: sum`
- [ ] denominator_sum_correct: `count_lifetime_orders` measure is `type: sum`
- [ ] bigquery_backtick_quoting: `sql_table_name` uses backtick format `` `jaffle_shop.marts.customers` ``
- [ ] model_file_generated: A `.model.lkml` file was written with `connection:` and `include:`
- [ ] no_table_dot_one: No `${TABLE}.1` in any file
