# Fusion Migration Triage — Category B: Unexpected Config Keys

## Background

A user is migrating their dbt project to Fusion. A model uses custom config keys (`my_custom_key`, `another_unexpected_key`) at the top level of the `config()` block. Fusion only accepts recognized dbt config keys at the top level — custom keys must be moved to the `meta:` section.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify the specific unexpected keys (`my_custom_key`, `another_unexpected_key`)
3. Suggest moving them to `meta:` within the config block
4. Show the before/after diff and request approval

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix)
- [ ] identified_unexpected_keys: Named the specific keys that need to be moved
- [ ] correct_fix_suggested: Suggested moving keys to `meta:` section (e.g., `config(materialized='table', meta={'my_custom_key': 'custom_value'})`)
- [ ] requested_approval: Asked for user approval before applying changes
- [ ] preserved_values: The suggested fix preserves the original key values
