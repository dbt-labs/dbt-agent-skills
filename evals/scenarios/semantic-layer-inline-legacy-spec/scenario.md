# Legacy Semantic Layer Authoring

## Goal

Verify that the skill preserves valid legacy Semantic Layer YAML for dbt Core v1.11.

## Expected Behavior

The response must contain one valid YAML block with:

- Top-level `semantic_models` and `metrics`
- Semantic model `orders` backed by `ref('fct_orders')`
- `defaults.agg_time_dimension: order_date`
- Entity, dimension, and measure arrays under the semantic model
- `type_params.time_granularity: day` for `order_date`
- A `revenue` measure with `agg: sum` and `expr: amount`
- A `total_revenue` simple metric with `type_params.measure: revenue`

The response must not contain model-embedded `semantic_model`, column annotations, or direct `agg` and `expr` fields on `total_revenue`.

## Grading

Mark the response unsuccessful with a score no higher than 2 if the YAML is invalid, omits the default aggregation time dimension, or mixes in latest-spec syntax.
