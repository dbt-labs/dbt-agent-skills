---
name: migrating-dbt-1.5
description: Upgrade a dbt project from dbt-core 1.5 to the latest release track (entry point 1.8) so it runs on the dbt platform. Applies the cumulative breaking, behavior, and deprecated changes for a project currently on 1.5.
metadata:
    fromVersion: '1.5'
    toVersion: '1.8'
---

# Migrate a dbt project from dbt 1.5 to the latest release track

You are upgrading a dbt project that currently targets dbt-core **1.5** to **1.8**
(the entry point of the latest release track). A 1.5 project takes three hops to reach
1.8 (1.5→1.6, then 1.6→1.7, then 1.7→1.8), so this migration applies changes from all
three hops. Apply every change below that is present in the project, then verify the
project parses under 1.8. Make only the changes required by this upgrade — do not
refactor unrelated code.

Work through the project systematically: read `dbt_project.yml`, the `models/`
schema files, `macros/`, and `requirements.txt` (or `packages`/env files), then
apply the fixes.

## Changes to apply

### 1. Rewrite pre-1.6 flat metric definitions to the MetricFlow spec (1.5→1.6, breaking → parse error)

Before 1.6, a metric was defined with flat top-level keys directly under the metric —
`calculation_method`, `expression`, `timestamp`, `time_grains`, and `dimensions`. In
1.6 metrics were rewritten for MetricFlow, and the flat form no longer parses: 1.6
reports `'type' is a required property` and 1.7+ reports `Additional properties are not
allowed ('calculation_method', 'expression', 'timestamp', ...)`. Any project with a
flat `metrics:` block will fail `dbt parse` until it is migrated.

Find every flat metric (a `metrics:` entry with `calculation_method`/`expression`
directly on it) and rewrite it into the MetricFlow shape:

- A `semantic_models:` block that binds the metric's `model:` to entities, dimensions,
  and a measure. The old `calculation_method` + `expression` become a **measure**
  (e.g. `calculation_method: sum` + `expression: total_amount` → a measure with
  `agg: sum`, `expr: total_amount`). The old `timestamp` becomes a **time dimension**
  and the semantic model's `agg_time_dimension`. The old `dimensions` become entities
  or dimensions on the semantic model.
- A `metrics:` block where each metric uses `type:` + `type_params:` referencing a
  measure (a `calculation_method: sum` metric becomes `type: simple` with
  `type_params: {measure: <measure name>}`).
- If any metric keeps a time grain / time dimension, MetricFlow additionally requires a
  `metricflow_time_spine` model in the project (otherwise parse fails with
  `The semantic layer requires a 'metricflow_time_spine' model`). Add a model named
  `metricflow_time_spine` that produces a `date_day` column.

Example — before (flat, 1.5):

```yaml
metrics:
  - name: total_order_amount
    label: Total order amount
    model: ref('fct_orders')
    calculation_method: sum
    expression: total_amount
    timestamp: created_at
    time_grains: [day, week, month]
    dimensions:
      - customer_id
```

After (MetricFlow, parses on 1.6–1.8):

```yaml
semantic_models:
  - name: orders
    model: ref('fct_orders')
    defaults:
      agg_time_dimension: created_at
    entities:
      - name: customer
        type: primary
        expr: customer_id
    dimensions:
      - name: created_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: total_amount
        agg: sum
        expr: total_amount

metrics:
  - name: total_order_amount
    label: Total order amount
    type: simple
    type_params:
      measure: total_amount
```

plus a `models/metricflow_time_spine.sql`:

```sql
{{ config(materialized='table') }}

select cast('2020-01-01' as date) as date_day
```

This is a semantic-layer redesign, not a mechanical rename. **Confirm the mapping with
the user** — entity types (`primary`/`foreign`), the measure aggregation, and the time
spine's granularity depend on the underlying data. If a flat metric is unused and the
project is not adopting the semantic layer, removing the metric block is an acceptable
way to reach parseability; **ask the user before deleting** rather than assuming.

### 2. Apply the 1.6→1.8 changes

The rest of this migration is exactly the 1.6→1.8 upgrade. Read
`../migrating-dbt-1.6/SKILL.md` now and apply every change in its "Changes to apply"
section (the 1.6→1.7 `clean-targets` fix and contract numeric precision/scale, then the
full 1.7→1.8 hop it chains to: renaming `tests:` → `data_tests:`, the built-in
materialization override opt-in, removing spaces from resource names, deduplicating
`primary_key` constraints, the dbt-core/dbt-adapters dependency split, and widening
`require-dbt-version`) to this project.

Read that file directly rather than relying on prior knowledge of what it contains — it
is the single source of truth for the 1.6→1.8 hops, and it can change independently of
this skill. It in turn points to `../migrating-dbt-1.7/SKILL.md`; follow that pointer
and read that file too.

## Verify

After editing, confirm the project parses by running **`dbt parse` only**. A
clean parse (no errors, no deprecation warnings) means the migration succeeded.
If the parse fails, read the error and fix the specific resource it names, then
parse again.

Do **not** run `dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`,
or `dbt compile`, and do not query any warehouse. Those touch data and are
validated separately — they are out of scope here. `dbt parse` is purely static
and is the only verification you should run.

## Document the changes

When the migration is complete, create a `migration_changes.md` file at the
project root summarizing everything you did. For each change include:

- the file that changed,
- what changed (before → after),
- which category of the latest release track upgrade it addresses
  (breaking / behavior / deprecated).

Do not print a target version number in this document — describe changes in
terms of the latest release track and the category above. Keep it concise and
factual — one entry per change.
