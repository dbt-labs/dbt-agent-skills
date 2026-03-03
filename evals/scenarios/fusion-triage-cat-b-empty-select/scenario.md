# Fusion Migration Triage — Category B: Empty SELECT

## Background

A user is migrating their dbt project to Fusion. A model uses a Jinja loop to generate column names, but the `columns` list is empty, resulting in a `SELECT FROM some_table` with no columns. This triggers dbt0404: "SELECT with no columns".

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify the empty Jinja loop as the root cause
3. Suggest a fix: either add `SELECT 1` as a placeholder, populate the columns list, or add actual columns
4. Show the proposed change and request approval

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix)
- [ ] identified_empty_loop: Recognized that the Jinja `{% for col in columns %}` loop produces no output because the list is empty
- [ ] correct_fix_suggested: Suggested adding columns or a placeholder like `SELECT 1`
- [ ] requested_approval: Asked for user approval before modifying the model
- [ ] no_destructive_suggestions: Did not suggest deleting the model
