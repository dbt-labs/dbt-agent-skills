# LookML Generation — Grain Mismatch Warning

## Background

The user has two saved_queries at different grains (daily vs. monthly) and wants to join them in a single explore. The correct behavior is to raise a grain mismatch warning and require acknowledgement before proceeding — not to silently generate a broken explore.

## Expected Outcome

The agent should:
1. Detect that `daily_order_metrics` is at daily grain and `monthly_revenue_metrics` is at monthly grain
2. Surface a grain mismatch warning BEFORE writing any files
3. Ask the user to confirm before continuing (or suggest separate explores)
4. NOT silently join the two views in a single explore

## Grading Criteria

- [ ] grain_mismatch_detected: Agent identifies that the two queries are at different grains (daily vs monthly)
- [ ] warning_before_write: Grain mismatch warning appears BEFORE any LookML files are written
- [ ] acknowledgement_required: Agent asks for user confirmation or explicitly recommends against joining
- [ ] recommendation_separate_explores: Agent recommends separate explores per grain family (or equivalent)
- [ ] no_silent_join: Agent does NOT quietly generate a single explore joining the two different-grain views
