# LookML Generation — Saved Query to Native Derived Table

## Background

The user has a `order_metrics` saved_query that groups three metrics by `ordered_at__date`. This tests converting a dbt saved_query to a LookML native derived table using `explore_source:`.

## Expected Outcome

The agent should:
1. Generate `orders.view.lkml` for the base model
2. Generate `order_metrics.view.lkml` as a native derived table using `explore_source: orders`
3. Generate `explores.explore.lkml` with an `orders` explore (required before the derived table can work)
4. Generate a `.model.lkml` file
5. Warn the user that `explore_source: orders` requires the `orders` explore to exist in the same project

## Grading Criteria

- [ ] saved_query_view_generated: `order_metrics.view.lkml` was written
- [ ] uses_explore_source: The `order_metrics` view uses `derived_table: { explore_source: orders { ... } }`
- [ ] explore_exists: `explores.explore.lkml` has `explore: orders {`
- [ ] columns_referenced: The `explore_source` block references `orders`, `order_total`, and `new_customer_orders` fields
- [ ] time_dim_in_derived: The `order_metrics` view has a `dimension_group: ordered_at { type: time ... }`
- [ ] explore_source_warning: Agent warns that `explore_source: orders` must exist in the Looker project
- [ ] no_table_dot_one: No `${TABLE}.1` in any file
- [ ] model_file_generated: A `.model.lkml` file was written
