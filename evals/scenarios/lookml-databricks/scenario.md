# LookML Generation — Databricks Unity Catalog

## Background

The user is on Databricks Unity Catalog. This tests Databricks-specific LookML requirements: 3-part backtick quoting, `datatype: timestamp` on dimension_groups, PERCENTILE_CONT compatibility warning, and count_distinct scale note.

## Expected Outcome

The agent should:
1. Generate `orders.view.lkml` with correct Databricks Unity Catalog `sql_table_name`
2. Add `datatype: timestamp` to the `ordered_at` dimension_group
3. Warn about PERCENTILE_CONT compatibility on older Databricks runtimes (for the median metric)
4. Offer PERCENTILE_APPROX fallback for the median
5. Note count_distinct scale consideration for `distinct_customers`

## Grading Criteria

- [ ] databricks_backtick_quoting: `sql_table_name` uses backtick 3-part format `` `main.marts.orders` ``
- [ ] datatype_timestamp: The `ordered_at` dimension_group has `datatype: timestamp`
- [ ] percentile_warning: Agent warns that PERCENTILE_CONT may not work on older Databricks runtimes
- [ ] percentile_approx_offered: Agent offers `PERCENTILE_APPROX` as a fallback for the median metric
- [ ] count_distinct_note: Agent mentions count_distinct HyperLogLog approximation or APPROX_COUNT_DISTINCT option
- [ ] model_file_generated: A `.model.lkml` file was written
- [ ] no_table_dot_one: No `${TABLE}.1` in any file
