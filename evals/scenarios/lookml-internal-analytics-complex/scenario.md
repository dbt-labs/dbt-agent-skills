# LookML Generation — Internal Analytics Complex Scenario

## Background

This is the adversarial integration test using representative fixtures from dbt Labs' own internal-analytics repo. It combines multiple challenges simultaneously:

1. **Cross-model Dimension refs in saved_query** — `Dimension('opportunity_commission__fiscal_quarter')` resolves through the `opportunity_commission` derived entity join path on the `all_days` time spine model
2. **`where:` → `filters:` conversion** — `{{ Dimension('opportunity_commission__is_last_9_fiscal_quarters') }} = True` must become `filters: [all_days.is_last_9_fiscal_quarters: "Yes"]`
3. **Untranslatable derived metric** — `opportunity_expansion_rate_renew_won` is `type: derived` with `input_metrics:` and a `{{ Metric(...) }}` filter — must be skipped with comment
4. **Multi-line YAML descriptions** — must be collapsed before writing to LookML
5. **`cache: enabled: false`** — no `persist_for` on the derived table

## Key Context

The `opportunity_commission` prefix in `Dimension('opportunity_commission__...')` refs is a derived entity join path on `all_days`, not a standalone model. So:
- `opportunity_commission__fiscal_quarter` → `all_days.fiscal_quarter`
- `opportunity_commission__is_last_9_fiscal_quarters` → `all_days.is_last_9_fiscal_quarters`

In LookML explore_source, the filter becomes:
```lookml
filters: [all_days.is_last_9_fiscal_quarters: "Yes"]
```

## Expected Outcome

The agent should:
1. Generate a view for the base opportunity model
2. Generate `gtm_bookings_total_l9fq.view.lkml` as a native derived table
3. Skip `opportunity_expansion_rate_renew_won` with a warning comment
4. Convert `where:` Dimension refs to `filters:` entries
5. Use `"Yes"` for boolean True filter
6. Collapse multi-line descriptions
7. Pass `uvx lkml` syntax validation on all output files
8. Generate a `.model.lkml` file

## Grading Criteria

- [ ] saved_query_view_generated: `gtm_bookings_total_l9fq.view.lkml` was written
- [ ] explore_source_used: Uses `derived_table: { explore_source: ... }` pattern
- [ ] where_converted_to_filters: The `where:` clause becomes a `filters:` entry in explore_source
- [ ] boolean_true_is_yes: Filter value is `"Yes"` not `"True"` or `true`
- [ ] derived_metric_skipped: No `measure: opportunity_expansion_rate_renew_won` in any output
- [ ] skip_comment_present: Comment block explains why the derived metric was skipped
- [ ] no_metricflow_jinja: No `{{ Metric(...) }}` or `{{ Dimension(...) }}` in any .lkml output file
- [ ] descriptions_collapsed: Multi-line YAML descriptions appear as single-line strings in LookML
- [ ] simple_metrics_generated: `opportunity_net_average_arr_won`, `opportunity_new_average_arr_won`, `count_of_opportunities_won` are generated as measures
- [ ] no_table_dot_one: No `${TABLE}.1` in any file (count_of_opportunities_won uses SUM(1) pattern)
- [ ] model_file_generated: A `.model.lkml` file with `connection:` and `include:` was written
- [ ] syntax_valid: All generated `.lkml` files pass `uvx lkml` syntax validation
