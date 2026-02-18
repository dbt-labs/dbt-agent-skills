---
name: using-dbt-for-analytics-engineering
description: Use when doing any dbt work - building or modifying models, debugging errors, exploring unfamiliar data sources, writing tests, or evaluating impact of changes. Use for analytics pipelines, data transformations, and data modeling.
user-invocable: false
metadata:
  author: dbt-labs
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

- Querying the semantic layer (use the `answering-natural-language-questions-with-dbt` skill)

## Reference Guides

This skill includes detailed reference guides for specific techniques. Read the relevant guide when needed:

| Guide | Use When |
|-------|----------|
| [references/planning-dbt-models.md](references/planning-dbt-models.md) | Building new models - work backwards from desired output and use `dbt show` to validate results |
| [references/discovering-data.md](references/discovering-data.md) | Exploring unfamiliar sources or onboarding to a project |
| [references/writing-data-tests.md](references/writing-data-tests.md) | Adding tests - prioritize high-value tests over exhaustive coverage |
| [references/debugging-dbt-errors.md](references/debugging-dbt-errors.md) | Fixing project parsing, compilation, or database errors |
| [references/evaluating-impact-of-a-dbt-model-change.md](references/evaluating-impact-of-a-dbt-model-change.md) | Assessing downstream effects before modifying models |
| [references/writing-documentation.md](references/writing-documentation.md) | Write documentation that doesn't just restate the column name |
| [references/managing-packages.md](references/managing-packages.md) | Installing and managing dbt packages |

## DAG building guidelines

- Conform to the existing style of a project (medallion layers, stage/intermediate/mart, etc)
- Focus heavily on DRY principles.
  - Before adding a new model or column, always be sure that the same logic isn't already defined elsewhere that can be used.
  - Prefer a change that requires you to add one column to an existing intermediate model over adding an entire additional model to the project.

**When users request new models:** Always ask "why a new model vs extending existing?" before proceeding. Legitimate reasons exist (different grain, precalculation for performance), but users often request new models out of habit. Your job is to surface the tradeoff, not blindly comply.

## Model building guidelines

- Always use data modelling best practices when working in a project
- Follow dbt best practices in code:
  - Always use `{{ ref }}` and `{{ source }}` over hardcoded table names
  - Use CTEs over subqueries
- Before building a model, follow [references/planning-dbt-models.md](references/planning-dbt-models.md) to plan your approach.
- Before modifying or building on existing models, read their YAML documentation:
  - Find the model's YAML file (can be any `.yml` or `.yaml` file in the models directory, but normally colocated with the SQL file)
  - Check the model's `description` to understand its purpose
  - Read column-level `description` fields to understand what each column represents
  - Review any `meta` properties that document business logic or ownership
  - This context prevents misusing columns or duplicating existing logic

## You must look at the data to be able to correctly model the data

When implementing a model, you must use `dbt show` regularly to:
  - preview the input data you will work with, so that you use relevant columns and values
  - preview the results of your model, so that you know your work is correct
  - run basic data profiling (counts, min, max, nulls) of input and output data, to check for misconfigured joins or other logic errors

## Cost management best practices

- Use `--limit` with `dbt show` and insert limits early into CTEs when exploring data
- Use deferral (`--defer --state path/to/prod/artifacts`) to reuse production objects
- Use [`dbt clone`](https://docs.getdbt.com/reference/commands/clone) to produce zero-copy clones
- Avoid large unpartitioned table scans in BigQuery
- Always use `--select` instead of running the entire project

## Interacting with the CLI

- You will be working in a terminal environment where you have access to the dbt CLI, and potentially the dbt MCP server. The MCP server may include access to the dbt Cloud platform's APIs if relevant.
- You should prefer working with the dbt MCP server's tools, and help the user install and onboard the MCP when appropriate.

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|----------------|-----|
| One-shotting models | Data work requires validation; schemas are unknown | Follow [references/planning-dbt-models.md](references/planning-dbt-models.md), iterate with `dbt show` |
| Not working iteratively | Changes to multiple models at once makes it hard to debug | Run `dbt build --select changed_model` on each model after modifying it |
| Assuming schema knowledge | Column names, types, and values vary across warehouses | Follow [references/discovering-data.md](references/discovering-data.md) before writing SQL |
| Not reading existing model documentation | Column names don't reveal business meaning | Read YAML descriptions before modifying models |
| Creating unnecessary models | Warehouse compute has real costs | Extend existing models when possible |
| Hardcoding table names | Breaks dbt's dependency graph | Always use `{{ ref() }}` and `{{ source() }}` |
| Global config changes | Configuration cascades unexpectedly | Change surgically, match existing patterns |
| Running DDL directly | Bypasses dbt's abstraction and tracking | Use dbt commands exclusively |

## Rationalizations to Resist

| Excuse | Reality |
|--------|---------|
| "User explicitly asked for a new model" | Users request out of habit. Ask why before complying. |
| "I've done this pattern hundreds of times" | This project's schema may differ. Verify with `dbt show`. |
| "User is senior / knows what they're doing" | Seniority doesn't change compute costs. Surface tradeoffs. |
| "It's just a small change" | Small changes compound. Follow DRY principles. |

## Red Flags - STOP and Reconsider

- About to write SQL without checking actual column names
- Modifying a model without reading its YAML documentation first
- Creating a new model when a column addition would suffice
- User gave table names as "the usual columns" - verify anyway
- Skipping `dbt show` validation because "it's straightforward"
- Running DDL or queries directly against the warehouse
