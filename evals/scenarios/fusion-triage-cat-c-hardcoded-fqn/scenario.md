# Fusion Migration Triage — Category C: Hardcoded FQN Permission Error

## Background

A user is migrating their dbt project to Fusion. A model uses a hardcoded fully-qualified name (`prod.raw.orders`) instead of `{{ ref() }}` or `{{ source() }}`. This triggers a permission/access error because the development environment doesn't have access to the production database.

The correct fix depends on what `prod.raw.orders` actually is — a dbt model, a source table, or a truly external table — which only the user knows.

## Expected Outcome

The agent should:
1. Classify the error as Category C (needs user input)
2. Identify the hardcoded FQN `prod.raw.orders` as the problem
3. Present multiple options and ask the user which applies:
   - If it's a dbt model: use `{{ ref('orders') }}`
   - If it's a source table: use `{{ source('raw', 'orders') }}`
   - If it's truly external: keep the FQN but fix permissions
4. NOT apply any fix without first getting the user's answer

## Grading Criteria

- [ ] correct_category: Classified as Category C (needs input) — not B (should not auto-suggest a single fix)
- [ ] identified_hardcoded_fqn: Found `prod.raw.orders` as the hardcoded reference
- [ ] presented_options: Presented at least 2 of the 3 options (ref, source, external)
- [ ] asked_user: Explicitly asked the user which option applies before proceeding
- [ ] no_premature_fix: Did NOT apply a fix without knowing what `orders` is
