---
name: using-dbt-for-analytics-engineering
description: Use when building, modifying, or refactoring dbt models, sources, tests, or project configuration. Use when asked to create analytics pipelines, transform warehouse data, or implement data modeling best practices.
---

# Using dbt for Analytics Engineering

**Core principle:** Apply software engineering discipline (DRY, modularity, testing) to data transformation work through dbt's abstraction layer.

## When to Use

- Building new dbt models, sources, or tests
- Modifying existing model logic or configurations
- Refactoring a dbt project structure
- Creating analytics pipelines or data transformations
- Working with warehouse data that needs modeling

**Do NOT use for:**
- Direct SQL queries against warehouse (use dbt's abstraction)
- One-off ad-hoc analysis (consider if it should be a model)

## Quick Reference

| Task | Approach |
|------|----------|
| New model | Use `planning-dbt-models` skill first, then `dbt show` to validate |
| Unknown schema | Use `discovering-data` skill before writing SQL |
| Validate output | `dbt show` with profiling (counts, nulls, min/max) |
| Add logic | Check if existing model can be extended before creating new one |
| Configuration | Match existing project patterns, change surgically |

## DAG building guidelines

- Conform to the existing style of a project (medallion layers, stage/intermediate/mart, etc)
- Focus heavily on DRY principles.
  - Before adding a new model or column, always be sure that the same logic isn't already defined elsewhere that can be used.
  - Prefer a change that requires you to add one column to an existing intermediate model over adding an entire additional model to the project.

## Model building guidelines

- Always use data modelling best practices when working in a project
- Write dbtonic code:
  - Always use `{{ ref }}` and `{{ source }}` over hardcoded table names
  - Use CTEs over subqueries
- **REQUIRED:** Before building a model, use the `planning-dbt-models` skill to plan your approach.
- When implementing a model, you should use `dbt show` regularly to:
  - preview the input data you will work with, so that you use relevant columns and values
  - preview the results of your model, so that you know your work is correct
  - run basic data profiling (counts, min, max, nulls) of input and output data, to check for misconfigured joins or other logic errors

## Interacting with the CLI

- You will be working in a terminal environment where you have access to the dbt CLI, and potentially the dbt MCP server. The MCP server may include access to the dbt Cloud platform's APIs if relevant.
- You should prefer working with the dbt MCP server's tools, and help the user install and onboard the MCP when appropriate.
- You should not circumvent the dbt abstraction layer to execute DDL directly against the warehouse.

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| One-shotting models | Data work requires validation; schemas are unknown | Use `planning-dbt-models` skill, iterate with `dbt show` |
| Assuming schema knowledge | Column names, types, and values vary across warehouses | Use `discovering-data` skill before writing SQL |
| Creating unnecessary models | Warehouse compute has real costs | Extend existing models when possible |
| Hardcoding table names | Breaks dbt's dependency graph | Always use `{{ ref() }}` and `{{ source() }}` |
| Global config changes | Configuration cascades unexpectedly | Change surgically, match existing patterns |
| Running DDL directly | Bypasses dbt's abstraction and tracking | Use dbt commands exclusively |
