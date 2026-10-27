# Snowflake semantic view metrics

## Goal
Test whether the agent defines non-additive metrics correctly in a Snowflake semantic view built with dbt, keeps materializations across runs, and writes a reconciliation test that can fail.

## Expected Behavior
The agent should:
1. Explain that averaging monthly averages and summing monthly distinct counts give wrong yearly figures
2. Define average order value as a derived metric over total revenue and total orders, and distinct customers as a `count(distinct …)` metric computed at the query's grain
3. Declare primary keys and relationships for the logical tables
4. Set `create_or_alter=true` (and `max_staleness`) because `CREATE OR REPLACE` drops materializations
5. Write a reconciliation test against fct_orders that uses `is distinct from` (or equivalent NULL-safe comparison)
6. Note that dbt descriptions do not reach the semantic view (`persist_docs`); comments belong in the DDL

## Evaluation Criteria
- **Correct**: Additivity and the materialization behaviour are described accurately
- **Complete**: Covers metrics, config and testing
- **Practical**: Gives a runnable model and test
