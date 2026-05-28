# Job Config Extraction

## Overview

Before configuring SAO, understand the current job landscape. Use dbt MCP tools (Admin API) to pull job definitions, schedules, and model selections.

## MCP Tools for Job Discovery

### List All Jobs

Use `list_jobs` to see all jobs in the project:

```
Tool: list_jobs
```

**Key fields to extract:**
- Job ID and name
- Job type (deploy, CI, merge) — SAO only works on deploy jobs
- Schedule (cron expression or trigger type)
- Whether Fusion cost optimization is already enabled

### Get Job Details

Use `get_job_details` with a specific job ID:

```
Tool: get_job_details
Input: job_id: <id>
```

**Key fields to extract:**
- `execute_steps` — the dbt commands run (e.g., `dbt build`, `dbt run --select +my_model+`)
- `triggers` — schedule type (cron, webhook, job completion)
- `settings` — whether Fusion/SAO features are enabled

### Resolve Job Selectors to Model Lineage

The `execute_steps` from a job contain dbt selectors (e.g., `dbt build -s +my_model+`, `dbt run --select tag:daily`). These selectors define which models are in scope for that job — and therefore which models need SAO configs tied to that job's schedule.

**After extracting `execute_steps`, use `get_lineage` to resolve the selector into actual models:**

```
Tool: get_lineage
Input: model_name: my_model
```

This expands a selector like `+my_model+` into the full ancestor and descendant graph. You can then map every model in that lineage to the job's schedule when recommending `build_after` intervals.

**Example workflow:**
1. `list_jobs` → find deploy job "Nightly Marts Refresh" (runs daily at 6am)
2. `get_job_details` → extract `execute_steps: ["dbt build -s +fct_orders+"]`
3. `get_lineage` for `fct_orders` → returns: `stg_orders`, `stg_customers`, `int_order_enriched`, `fct_orders`, `report_daily_sales`
4. Now you know all 5 models run on a daily schedule → recommend `build_after: {count: 1, period: day}` as the baseline for this group

**Why this matters:** Without resolving selectors to lineage, you might recommend a 4-hour `build_after` for a model that only runs in a daily job — wasting the config. Matching `build_after` to the actual job cadence maximizes skip rates.

For jobs with multiple selectors or commands in `execute_steps`, resolve each one separately and note which models overlap across jobs (they may need the tightest `build_after` from any job that runs them).

### List Job Runs

Use `list_jobs_runs` to see recent execution history:

```
Tool: list_jobs_runs
Input: job_id: <id>
```

This shows run durations and statuses, helping identify which jobs benefit most from SAO (long-running, frequently triggered jobs save the most).

## MCP Tools for Model Discovery

### List All Models

Use `get_all_models` to get the full model inventory:

```
Tool: get_all_models
```

**Key fields:** model name, materialization, schema/database, tags, access level, group.

### Get Model Details

Use `get_model_details` for specific model info:

```
Tool: get_model_details
Input: model_name: <name>
```

**Key fields:** full SQL, config block, contract info, freshness settings if any.

### Get Lineage

Use `get_lineage` to understand the dependency graph:

```
Tool: get_lineage
Input: model_name: <name>
```

Also use `get_model_parents` and `get_model_children` for direct dependencies.

### Get All Sources

Use `get_all_sources` to list source definitions:

```
Tool: get_all_sources
```

Check for existing `loaded_at_field`, `loaded_at_query`, and freshness configs.

## What to Build from Job Data

After extracting job configs, build this picture:

| Data Point | Source | Why It Matters |
|-----------|--------|----------------|
| Job schedule frequency | `get_job_details` triggers | `build_after` intervals should align with schedule |
| Models selected per job | `get_job_details` execute_steps + `get_all_models` | Know which models need SAO config |
| Job run duration | `list_jobs_runs` | Longer jobs benefit more from SAO |
| Source refresh frequency | Ask user or check source configs | `build_after` should match actual data arrival |
| Existing freshness configs | `get_all_sources` + grep project files | Don't overwrite existing valid configs |

## Mapping Job Schedules to `build_after`

| Job Schedule | Suggested Starting `build_after` | Reasoning |
|-------------|----------------------------------|-----------|
| Every hour | `{count: 4, period: hour}` | Skip 3 out of 4 runs if data hasn't changed |
| Every 6 hours | `{count: 12, period: hour}` | Skip one full cycle if data is stale |
| Daily | `{count: 1, period: day}` | Only rebuild if data changed since yesterday |
| On source refresh (webhook) | `{count: 1, period: hour}` | Small buffer to avoid race conditions |

These are starting points — adjust based on actual source refresh patterns and business SLAs. Always confirm with the user.
