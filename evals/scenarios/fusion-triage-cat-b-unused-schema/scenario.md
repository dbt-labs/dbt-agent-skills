# Fusion Migration Triage — Category B: Unused Schema Entry

## Background

A user is migrating their dbt project to Fusion. Their `schema.yml` defines two models (`stg_users` and `stg_orders`), but only `stg_orders` has a corresponding SQL file. Fusion flags the orphaned `stg_users` entry as dbt1005.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify that `stg_users` is defined in schema.yml but has no SQL file
3. Suggest removing the orphaned entry from schema.yml
4. Request approval since the user may want to create the missing SQL file instead

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix)
- [ ] identified_orphan: Recognized that `stg_users` has a schema entry but no SQL file
- [ ] correct_fix_suggested: Suggested removing the stg_users entry from schema.yml (or creating the SQL file)
- [ ] requested_approval: Asked for user approval — the user may prefer to create the missing model
- [ ] preserved_stg_orders: Did not suggest modifying or removing the valid stg_orders entry
