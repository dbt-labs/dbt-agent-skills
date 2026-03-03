# Fusion Migration Triage — Basic Classification

## Background

A user is migrating their dbt project from dbt-core to Fusion. They ran `dbt compile` and received errors related to the deprecated `config.require('meta')` API. The project uses `config.require('meta').key_name` which must be replaced with `config.meta_require('key_name')` in Fusion.

The `dbt_compile_output.txt` file contains the pre-captured compiler output showing dbt1501 errors.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify the dbt1501 error code and the deprecated `config.require('meta')` pattern
3. Suggest the correct fix: replace with `config.meta_require()`
4. Request user approval before applying any changes (not auto-fix)
5. NOT attempt workarounds or suggest removing the config

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix) — not Category A (auto-fix) or Category D (blocked)
- [ ] identified_error_pattern: Recognized `config.require('meta')` as a deprecated API pattern
- [ ] correct_fix_suggested: Suggested replacing with `config.meta_require('key_name')`
- [ ] requested_approval: Asked for user approval before applying the fix (showed diff or described change)
- [ ] no_destructive_suggestions: Did not suggest removing the config, disabling the model, or other destructive changes
