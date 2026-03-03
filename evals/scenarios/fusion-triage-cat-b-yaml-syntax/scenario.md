# Fusion Migration Triage — Category B: YAML Syntax Error

## Background

A user is migrating their dbt project to Fusion. Their `dbt_project.yml` has a YAML syntax error: `vars::` (double colon) instead of `vars:` (single colon). This causes Fusion to flag it as dbt1060 (unexpected key) because the double colon creates an invalid YAML structure.

Note: The error is in `dbt_project.yml` itself, not in a model file.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify the double colon (`vars::`) as the syntax issue
3. Suggest fixing it to `vars:` (single colon)
4. Request approval before modifying `dbt_project.yml`

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix)
- [ ] identified_syntax_issue: Found the `vars::` double colon in dbt_project.yml
- [ ] correct_fix_suggested: Suggested changing `vars::` to `vars:`
- [ ] requested_approval: Asked for user approval before modifying dbt_project.yml
- [ ] correct_file_identified: Identified `dbt_project.yml` as the file with the error (not a model file)
