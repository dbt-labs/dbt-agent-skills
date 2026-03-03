# Fusion Migration Triage — Category B: Dict meta_get Error

## Background

A user is migrating their dbt project to Fusion. A model retrieves the `meta` config as a plain dictionary (`config.get('meta', {})`), then incorrectly calls `.meta_get()` on that plain dict. Only `config` objects have `meta_get()` — plain dicts must use `.get()`.

## Expected Outcome

The agent should:
1. Classify the error as Category B (guided fix, needs approval)
2. Identify that `.meta_get()` is being called on a plain dict, not a config object
3. Suggest replacing `meta_config.meta_get('owner', 'unknown')` with `meta_config.get('owner', 'unknown')`
4. Show the diff and request approval before applying

## Grading Criteria

- [ ] correct_category: Classified as Category B (guided fix) — not A or D
- [ ] identified_root_cause: Understood that `.meta_get()` only exists on config objects, not plain dicts
- [ ] correct_fix_suggested: Suggested replacing with `.get()` for the plain dictionary
- [ ] requested_approval: Asked for user approval before applying the fix
- [ ] no_config_object_confusion: Did not confuse `config.get('meta')` (correct) with the `.meta_get()` call on the result
