# Example YAML Error

## Background

A user has broken indentation in their schema.yml file, causing dbt parse to fail.

## Expected Outcome

Claude should:
- Identify this as a YAML parsing error
- Find the exact file and line with the issue
- Fix the indentation without removing content

## Grading Criteria

- [ ] identified_error_type: Correctly identified as YAML/parsing error
- [ ] found_correct_location: Found the right file and line
- [ ] fix_preserves_intent: Fix keeps the original test/config
- [ ] no_destructive_suggestions: Did not suggest removing the config
