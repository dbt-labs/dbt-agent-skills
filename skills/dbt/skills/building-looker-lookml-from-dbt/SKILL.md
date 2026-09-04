---
name: building-looker-lookml-from-dbt
description: Generates LookML views and explores in a Looker project from a dbt fact or dim model, suggesting dimensions, measures, business-relevant derived metrics, and joins. Use when a user asks to create a new Looker view/model for a fact or dim table they've just built or are pointing to. Does not build or modify dbt models.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(dbt *)
user-invocable: false
metadata:
  author: mustafaa7med
---

# Building Looker LookML from dbt

**Core principle:** LookML is generated from an existing fact or dim model, into a separate LookML project that the user points you to. This skill never touches dbt models — it's a one-way, downstream step from dbt to Looker.

## When to Use

- The user asks to create a new Looker view (or explore) for a fact and/or dim model they've built or named
- The user wants LookML regenerated/updated for an existing fact/dim model whose columns changed

**Do NOT use for:**

- Building, modifying, or refactoring dbt models — this skill only reads finished fact/dim models and writes LookML. If no fact or dim model exists yet, say so and stop; don't create one.
- Staging or intermediate models — LookML views are for BI-facing mart models only. If the user points you at a staging/intermediate model, flag that it's not typically exposed in Looker and confirm before proceeding.

## Step 0: Find Out Where the LookML Lives

LookML views are files (`.view.lkml`, `.model.lkml`) in a Looker project, which is almost always a **separate Git repo** from the dbt project. Unless the user has a Looker MCP active.

**Always ask the user where this project lives** if it isn't already established in this conversation (e.g. a cloned Looker repo path on disk). Do not assume a location or create one unless the user asks for it. Once given a path:

- Look at the existing folder structure and naming of `.view.lkml` files there to learn the team's convention — one view per mart model, views grouped by subject area, a specific `views/` subfolder, etc. — before writing anything new.
- If you can't find any existing views to infer a convention from, ask rather than guessing.

## Step 1: Understand the Business Context via dbt Exposures

Before generating dimensions or, especially, suggesting metrics, look for a dbt **exposure** that documents the dashboard/use case this model feeds:

```yaml
exposures:
  - name: sales_pipeline_dashboard
    type: dashboard
    depends_on:
      - ref('fct__salesforce_activity')
    description: >
      Tracks opportunity stage progression and conversion rates for the sales team.
```

- If an exposure references this model, use its `description` and `depends_on` to understand what the model is for — this is what grounds good metric suggestions (see Step 3).
- **If no exposure exists, do not guess the business context.** Ask the user a short clarifying question instead — e.g. "What does this fact table represent, and what should I know about how it's used?" Proceeding without this context risks suggesting metrics that don't match how the business actually thinks about the data.

## Step 2: Check for an Existing View File

Before writing anything:

1. Determine the expected filename from the model name (see naming convention below) and check whether it already exists in the target directory.
2. **If it exists, stop and ask the user** what they want to do — update it, leave it alone, or replace it. Never silently overwrite or create a duplicate file with a modified name.
3. If it doesn't exist, proceed to generation.

## Naming Convention

The view name mirrors the dbt model name exactly, and the file is `<model_name>.view.lkml`:

| dbt model | LookML view file |
| --- | --- |
| `fct__salesforce_activity` | `fct__salesforce_activity.view.lkml` |
| `dim__salesforce_opportunities` | `dim__salesforce_opportunities.view.lkml` |

Don't shorten, reformat, or reorder the name — the view name should make it obvious which dbt model it came from.

## Step 3: Generate the View

Read the model's YAML (columns, `data_type`, `description`, `data_tests`, `meta.looker` overrides) and its actual compiled SQL/schema to confirm current columns and types — see [references/mapping-dbt-types-to-lookml.md](references/mapping-dbt-types-to-lookml.md) for the type mapping and dimension-group rules.

Applies to both fact and dim models:

- **One view per dbt model**, unless the existing convention in the target repo says otherwise (checked in Step 0).
- **`sql_table_name`**: reference the model's actual warehouse location (schema.table), read from the model's `config` (schema/alias/database) — never hardcode a name that could drift from how dbt actually materializes it.
- **Primary key**: a column with a `unique` + `not_null` test (or a single-column `unique_key` in an incremental config) becomes `primary_key: yes` on its dimension.
- **Dates/timestamps**: never emit a raw timestamp as a plain `string`/`number` dimension. Always use a `dimension_group` with `type: time` and a sensible `timeframes` list.
- **`meta.looker` overrides win** over anything inferred from type/name.

### If it's a fact model (`fct__...`)

- Generate dimensions for all columns as above.
- Generate measures based on what the table actually contains (e.g. a `count` on the primary key; sums on genuinely additive numeric columns).
- **Suggest possible derived business metrics**, using the exposure's business context from Step 1. This is the most valuable and most error-prone part of the skill — see [references/suggesting-fact-metrics.md](references/suggesting-fact-metrics.md) for how to do this responsibly (e.g. a table with per-stage timestamp columns on a sales opportunity table suggests a stage-to-stage conversion-rate metric — but only surface it as a *suggestion* for the user to confirm, never add it to the view unprompted).

### If it's a dim model (`dim__...`)

- **Dimensions only** — do not generate measures or suggest metrics for dim models. A dim model describes entities, not events; metrics belong on the fact side.

## Step 4: Create or Update the Explore

After the view is written, check whether an explore is needed for this model:

- If the model is a fact table, it's very likely the base of a new (or existing) explore.
- Look at the fact model's columns for foreign keys (e.g. `opportunity_id` on `fct__salesforce_activity`) and check whether a corresponding dim model exists (`dim__salesforce_opportunities`) that would add useful descriptive fields.
- **Suggest the join, don't assume it's wanted.** Present it as a recommendation — "`fct__salesforce_activity` has an `opportunity_id` FK; joining `dim__salesforce_opportunities` would add opportunity name, owner, and amount fields — want me to add this join?" — and confirm before adding it to the explore.
- Follow [references/generating-explores-and-joins.md](references/generating-explores-and-joins.md) for how to derive join keys, join type, and `relationship:` correctly (via `relationships` tests where they exist, or the FK-naming heuristic above when they don't — always flagged as a suggestion either way).
- Dim models generally don't need their own explore unless the user asks for one to browse the dimension standalone.

## Reference Guides

| Guide | Use When |
| --- | --- |
| [references/mapping-dbt-types-to-lookml.md](references/mapping-dbt-types-to-lookml.md) | Translating column data types (including Redshift-specific types) into LookML dimension/dimension_group types |
| [references/suggesting-fact-metrics.md](references/suggesting-fact-metrics.md) | Turning a fact table's actual columns and business context into responsible, confirmed-before-adding metric suggestions |
| [references/generating-explores-and-joins.md](references/generating-explores-and-joins.md) | Deriving join keys and relationship types from FK columns, `relationships` tests, and dim model lookups |

## Common Mistakes and Red Flags

| Mistake | Fix |
| --- | --- |
| Assuming where the LookML project lives | Always ask in Step 0 if not already given |
| Guessing business context without an exposure | Ask a clarifying question instead — never invent the use case |
| Overwriting an existing `.view.lkml` silently | Stop and ask the user what to do before touching an existing file |
| Adding measures/metrics to a dim model | Dim models get dimensions only — no measures, no metric suggestions |
| Adding a suggested metric or join directly without confirming | Suggestions are proposals — confirm before writing them into the file |
| Emitting `type: string` for a timestamp column | Always use a `type: time` dimension group |
| Building or editing the dbt model itself | Out of scope — this skill only reads finished fact/dim models |

**STOP if you're about to:** write to a LookML path the user hasn't confirmed, overwrite an existing view file without asking, invent a business metric without exposure context or user confirmation, or add measures to a dim model.
