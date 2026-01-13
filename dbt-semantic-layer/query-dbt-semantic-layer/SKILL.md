---
name: query-dbt-semantic-layer
description: Use when answering business questions that could be answered by querying data, when dbt MCP tools are available
---

# dbt Semantic Layer Queries

## Overview

Answer business questions using dbt Semantic Layer MCP tools. If the question cannot be answered with current configuration, say so clearly and suggest semantic layer changes if in a dbt project.

## Workflow

```dot
digraph dbt_sl {
    "Business question received" [shape=box];
    "List metrics (list_metrics)" [shape=box];
    "Relevant metric exists?" [shape=diamond];
    "Get dimensions (get_dimensions)" [shape=box];
    "Required dimensions exist?" [shape=diamond];
    "Query metrics (query_metrics)" [shape=box];
    "Return answer" [shape=box];
    "Say: metric not available" [shape=box];
    "Say: dimension not available" [shape=box];
    "In dbt project?" [shape=diamond];
    "Suggest semantic layer changes" [shape=box];
    "Done" [shape=doublecircle];

    "Business question received" -> "List metrics (list_metrics)";
    "List metrics (list_metrics)" -> "Relevant metric exists?";
    "Relevant metric exists?" -> "Get dimensions (get_dimensions)" [label="yes"];
    "Relevant metric exists?" -> "Say: metric not available" [label="no"];
    "Get dimensions (get_dimensions)" -> "Required dimensions exist?";
    "Required dimensions exist?" -> "Query metrics (query_metrics)" [label="yes"];
    "Required dimensions exist?" -> "Say: dimension not available" [label="no"];
    "Query metrics (query_metrics)" -> "Return answer";
    "Return answer" -> "Done";
    "Say: metric not available" -> "In dbt project?";
    "Say: dimension not available" -> "In dbt project?";
    "In dbt project?" -> "Suggest semantic layer changes" [label="yes"];
    "In dbt project?" -> "Done" [label="no"];
    "Suggest semantic layer changes" -> "Done";
}
```

## Quick Reference

| Step | Tool | Purpose |
|------|------|---------|
| 1 | `list_metrics` | Find relevant metrics |
| 2 | `get_dimensions` | Check available dimensions for those metrics |
| 3 | `get_entities` | Check available entities if grouping by business objects |
| 4 | `query_metrics` | Execute the query |

## When You Cannot Answer

**Be upfront.** Start with the limitation, then explain:

> "This question cannot be answered with the current semantic layer configuration. The `total_premium` metric exists, but there is no `state` dimension available."

This includes when:
- A metric doesn't exist
- A required dimension doesn't exist
- A dimension exists but query returns null/empty values (treat as "cannot answer")

**Do NOT:**
- Bury the finding in paragraphs of exploration details
- Suggest database/ETL fixes ("populate this field", "data engineering team should...")
- Discuss underlying table structures

**Stay at the semantic layer level.** The semantic layer abstracts the database—your suggestions should too.

## Suggesting Changes (dbt Projects Only)

**First, detect if in a dbt project:**
- Look for `dbt_project.yml` in the workspace
- If not found, do NOT suggest changes—just report the limitation

**If in a dbt project, suggest semantic layer changes:**

| Missing | Suggestion |
|---------|------------|
| Metric | "Add a new metric definition to a semantic model" |
| Dimension | "Add the dimension to the semantic model's dimensions list" |
| Entity | "Add an entity relationship to connect the required data" |

**Example suggestion:**
> "To answer 'total premium by state', you would need to add a `state` dimension to the semantic model that defines `total_premium`. This typically involves adding the dimension to the `dimensions:` section of the semantic model YAML."

Do NOT specify exact file paths or write the YAML—that's a separate task.

## Not a Data Question?

If the question is about dbt configuration, documentation, or concepts (not querying data), do NOT use semantic layer tools. Answer from general knowledge or suggest documentation resources.
