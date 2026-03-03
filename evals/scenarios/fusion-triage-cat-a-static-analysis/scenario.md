# Fusion Migration Triage — Category A: Static Analysis in Analyses

## Background

A user is migrating their dbt project to Fusion. They have an analysis file (`analyses/explore_data.sql`) that uses PostgreSQL-specific functions (`array_to_string`, `array_agg`) and references a non-existent column (`invalid_sql`). This triggers static analysis errors (dbt0209/dbt0227) in Fusion.

Since this is in the `analyses/` directory (not a production model), the fix is straightforward and low-risk: add `{{ config(static_analysis='off') }}` at the top of the file.

## Expected Outcome

The agent should:
1. Classify the error as Category A (auto-fixable, safe)
2. Recognize that static analysis errors in `analyses/` are low-risk
3. Suggest adding `{{ config(static_analysis='off') }}` at the top of the file
4. Apply the fix without requiring detailed user approval (Category A = safe)

## Grading Criteria

- [ ] correct_category: Classified as Category A (auto-fixable) — not B, C, or D
- [ ] identified_analyses_context: Recognized this is in `analyses/` (not a model) making it low-risk
- [ ] correct_fix_suggested: Suggested `{{ config(static_analysis='off') }}`
- [ ] low_risk_assessment: Communicated that analyses are optional and this is a safe change
- [ ] no_overengineering: Did not suggest rewriting the SQL or removing the analysis file
