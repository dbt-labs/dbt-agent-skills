# Latest Semantic Layer Inline Authoring

## Goal

Verify that the skill produces the model-embedded Semantic Layer YAML required by dbt Core v1.12.

## Expected Behavior

The response must contain one valid YAML block with:

- `models[].semantic_model.enabled: true`
- Model-level `agg_time_dimension: order_date`
- Entity and dimension annotations under model `columns`
- Column-level `granularity: day` for `order_date`
- A model-level `total_revenue` simple metric with direct `agg: sum` and `expr: amount`

The response must not contain:

- Top-level `semantic_models`
- `entities`, `dimensions`, or `measures` nested under `semantic_model`
- Any `measures` or `type_params`

## Grading

Mark the response unsuccessful with a score no higher than 2 if the YAML is invalid or contains any forbidden legacy construct.
