# Fusion Migration Triage — Basic Classification

## Background

A user is migrating their dbt project from dbt-core to Fusion. They ran `dbt compile` and received errors because their model uses `config.require('owner')` to access a custom key that lives under `meta`. In Fusion, `config.require()` only works for built-in config keys. Custom keys stored in `meta` must be accessed via `config.meta_require('key_name')`.

The `dbt_compile_output.txt` file contains the real Fusion compiler output showing the dbt1501 error and the dbt1000 warning that hints at the fix.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify that `config.require('owner')` is trying to access a custom key in `meta`
3. Suggest the correct fix: replace `config.require('owner')` with `config.meta_require('owner')`
4. Request user approval before applying any changes (not auto-fix)
5. NOT attempt workarounds or suggest removing the config

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix) — not Category A (auto-fix) or Category D (blocked)
- [ ] identified_error_pattern: Recognized that `config.require('owner')` fails because 'owner' is a custom key in `meta`
- [ ] correct_fix_suggested: Suggested replacing with `config.meta_require('owner')` (and similarly for 'logical_key')
- [ ] requested_approval: Asked for user approval before applying the fix (showed diff or described change)
- [ ] no_destructive_suggestions: Did not suggest removing the config, disabling the model, or other destructive changes
