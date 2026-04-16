# LookML Generation — Simple Orders Model

## Background

A user has a dbt `orders` semantic model with two simple metrics (`orders` count and `order_total` sum) and wants to generate LookML from it. This is the baseline happy-path scenario — no edge cases.

The semantic model YAML is in `orders_semantic_model.yml`. Warehouse is Snowflake.

## Expected Outcome

The agent should:
1. Read the semantic model YAML from `orders_semantic_model.yml`
2. Generate `orders.view.lkml` with correct field definitions
3. Generate `explores.explore.lkml` with an orders explore
4. Generate `jaffle_shop.model.lkml` with connection and includes
5. NOT ask unnecessary clarifying questions — all intake info is in the prompt

## Grading Criteria

- [ ] view_file_generated: `orders.view.lkml` was written
- [ ] explore_file_generated: `explores.explore.lkml` was written
- [ ] model_file_generated: A `.model.lkml` file was written with `connection:` and `include:`
- [ ] primary_key_correct: The `order_id` entity maps to a dimension with `primary_key: yes`
- [ ] foreign_key_correct: The `customer_id` entity maps to a dimension without `primary_key`
- [ ] time_dim_is_dimension_group: `ordered_at` becomes `dimension_group: ordered_at { type: time ... }`
- [ ] no_grain_suffix_in_group_name: The dimension_group is named `ordered_at` not `ordered_at_date`
- [ ] yesno_dimension: `is_food_order` is `type: yesno`
- [ ] orders_measure_type_count: The `orders` measure is `type: count` or `type: sum` with `sql: 1`
- [ ] sql_table_name_snowflake: `sql_table_name: JAFFLE_SHOP.MARTS.ORDERS` (uppercase, no backticks)
- [ ] no_table_dot_one: No `${TABLE}.1` appears in any generated file
