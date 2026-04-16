# LookML Generation — Saved Query with `where:` Filter Conversion

## Background

The `gtm_bookings_total_l9fq` saved query has a `where:` clause using a Jinja Dimension ref:
```
{{ Dimension('opportunity_commission__is_last_9_fiscal_quarters') }} = True
```

This must be converted to a LookML `filters:` entry in the `explore_source` block:
```lookml
filters: [opportunity_commission.is_last_9_fiscal_quarters: "Yes"]
```

Boolean `= True` maps to `"Yes"`. The multi-line description must be collapsed to a single line.

## Expected Outcome

The agent should:
1. Generate the `gtm_bookings_total_l9fq.view.lkml` with a `explore_source` native derived table
2. Convert the `where:` Dimension ref to a `filters:` entry with the correct view.field format
3. Convert `= True` to `"Yes"` (LookML boolean filter syntax)
4. Collapse the multi-line YAML description to a single line
5. Not include `cache: enabled: false` as a persistence directive (no `persist_for`)

## Grading Criteria

- [ ] saved_query_view_generated: `gtm_bookings_total_l9fq.view.lkml` was written
- [ ] explore_source_used: The view uses `derived_table: { explore_source: opportunity_commission { ... } }`
- [ ] where_converted_to_filters: The `explore_source` block has a `filters:` entry (not a WHERE clause in SQL)
- [ ] filter_view_field_format: The filter uses `opportunity_commission.is_last_9_fiscal_quarters` format
- [ ] boolean_true_maps_to_yes: The filter value is `"Yes"` (not `"True"`, `true`, or `1`)
- [ ] description_collapsed: The multi-line `>` description is collapsed to a single line
- [ ] no_cache_persist: No `persist_for` or `sql_trigger_value` (cache disabled = no persistence)
- [ ] model_file_generated: A `.model.lkml` file was written
