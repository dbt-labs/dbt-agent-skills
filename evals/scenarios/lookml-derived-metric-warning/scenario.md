# LookML Generation — Derived Metric Warning (Graceful Skip)

## Background

The `opportunity_expansion_rate_renew_won` metric is `type: derived` with `input_metrics:` and a `{{ Metric(...) }}` filter. This is completely untranslatable to LookML — MetricFlow resolves input_metrics at query time. The agent must NOT emit broken SQL. Instead, it should skip with a warning comment and still generate LookML for the two translatable simple metrics.

This is the adversarial "don't break it" scenario.

## Expected Outcome

The agent should:
1. Generate LookML measures for the two simple metrics (`opportunity_expansion_average_arr_renew_won` and `opportunity_starting_arr_won_with_expansion`)
2. For `opportunity_expansion_rate_renew_won`: emit ONLY a warning comment block — no measure
3. The warning comment must identify the metric as `type: derived` with `input_metrics`
4. Collapse the multi-line YAML description to a single line where used
5. Handle `DIV0()` → Snowflake output keeps `DIV0` (or equivalent)

## Grading Criteria

- [ ] derived_metric_skipped: No `measure: opportunity_expansion_rate_renew_won {` block in any output file
- [ ] skip_comment_present: A comment block appears at the location with text about the metric being skipped
- [ ] comment_explains_reason: The comment mentions `type: derived` or `input_metrics` as the reason
- [ ] simple_metrics_generated: Measures for `opportunity_expansion_average_arr_renew_won` and `opportunity_starting_arr_won_with_expansion` ARE generated
- [ ] no_broken_sql: No MetricFlow Jinja syntax (`{{ Metric(...) }}`) appears in any LookML output file
- [ ] description_collapsed: If the multi-line description is used, it is collapsed to a single line
- [ ] model_file_generated: A `.model.lkml` file was written
