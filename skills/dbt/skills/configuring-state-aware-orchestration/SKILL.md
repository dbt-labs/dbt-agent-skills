---
name: configuring-state-aware-orchestration
description: Use when configuring state-aware orchestration in dbt Cloud jobs, including selecting state comparison strategy, defining defer behavior, and validating deployment safety.
user-invocable: false
metadata:
  author: dbt-labs
---

# Configuring State-Aware Orchestration

## Overview

Use this skill inside the dbt IDE to change dbt project code and configs for maximum SAO savings. Focus on `dbt_project.yml`, model and source YAML, and model-level SQL config so unchanged nodes are skipped safely while freshness SLOs are still met. Start from SAO's default behavior and add custom config only where the project needs more control.

## When to Use

- Adding or tuning SAO-related config in project code
- Setting project defaults for `build_after`, `updates_on`, and freshness
- Creating model-level exceptions for different SLO tiers
- Refactoring configs to reduce unnecessary rebuilds

## When Not to Use

- Editing dbt Cloud job schedules, environment flags, or account settings
- Enabling Fusion/SAO feature flags
- Making org-level rollout or governance decisions not represented in code

## Prerequisites

- A dbt project open in the IDE
- Access to edit project files (`dbt_project.yml`, YAML config files, model SQL)
- SAO is being used for SQL models; Python models are out of scope
- Agreement on where defaults live (project-level vs model-level overrides)

Recommended, but not required:

- Source freshness is configured and actively running for important sources so teams have visibility into source timeliness while tuning SAO behavior.

## Questions to Ask First

1. Which models/domains need the strongest freshness guarantees?
2. What project-level defaults should apply to most models?
3. Which models require explicit overrides due to tighter SLOs?
4. Is `updates_on` standardized (`any` vs `all`) for this domain?
5. Do any incremental models use lookback windows or receive late-arriving data?
6. What config change can be safely rolled back if skips are wrong?

## Recommended Workflow

1. Identify current config surface in code and separate default SAO behavior from explicit overrides.
2. Add or refine project-level defaults first to maximize broad savings with minimal complexity.
3. Add model-level overrides only for exceptions where business SLOs require it.
4. Use `loaded_at_field` or `loaded_at_query` only when warehouse metadata is not the right freshness signal.
5. Validate expected behavior with parse/build/list commands in development.
6. Record rationale in code comments or PR notes for future maintainers.

See [Rollout Playbook](references/rollout-playbook.md) for code-first rollout sequencing.

## Configuration Defaults and Guardrails

1. Start from SAO defaults and avoid advanced settings until baseline behavior is understood.
2. Recommend source freshness on important sources even though SAO does not require it to function.
3. Use project-level defaults first, then add model-level exceptions.
4. Keep model override count low to avoid policy drift.

### Where to Configure SAO Behavior

- `dbt_project.yml` for project-level or folder-level defaults
- model or source property YAML for grouped resource config
- model SQL config blocks for narrow model-specific exceptions

Prefer the highest level that safely expresses the policy.

### Source Freshness Baseline

```yaml
sources:
  dbt_project_name:
    +freshness:
      warn_after:
        count: 12
        period: hour
```

Tune thresholds based on source arrival patterns and business SLOs.

Where practical, make sure source freshness checks are actually scheduled or otherwise running so the project gets operational value from the configuration.

### Core SAO Config Levers in Project Code

- `build_after`: controls rebuild cadence and is the main savings lever.
- `updates_on`: controls what upstream change signals should trigger a rebuild. Default to `any`, but use `all` if a downstream model should only rebuild when all upstream dependencies have changed.
- `loaded_at_field` / `loaded_at_query`: use only for sources needing custom freshness logic.

Only define one of `loaded_at_field` or `loaded_at_query` for a given source.

### Choosing `updates_on` for Facts and Dimensions

- Fact-like models often fit `updates_on: any` when the goal is to process new upstream data as soon as any contributing feed lands.
- Dimension-like models often fit `updates_on: all` when they combine multiple upstream dependencies and should rebuild only after the full set of required updates has arrived.
- These are starting heuristics, not hard rules: a single-source dimension may still fit `any`, and a fact model with tightly synchronized batch dependencies may fit `all`.
- Pick the setting that matches the business requirement for partial versus fully synchronized refreshes.

### Warehouse-Specific Freshness Semantics

- Validate how your warehouse updates object metadata before relying on default change detection.
- When warehouse metadata does not reflect underlying data arrival, define `loaded_at_field` or `loaded_at_query` explicitly.
- Keep warehouse-specific exceptions documented in a reference file rather than embedding them into the main workflow.

See [Snowflake-specific considerations](references/snowflake.md) for known behavior around shared objects and dynamic tables.

### Temporary Fusion Unblocker (Use Sparingly)

If Fusion compile blockers prevent SAO rollout, a temporary fallback is:

```yaml
models:
  +static_analysis: baseline
```

This reduces Fusion capabilities and should be narrowed to problematic models as soon as possible.

## Common Failure Modes

| Symptom | Likely Cause | Validation | Fix |
|---------|--------------|------------|-----|
| SAO skips too much or too little | Misaligned freshness/SLO config | Compare expected critical models vs actual run graph | Adjust `build_after` and source freshness thresholds |
| Runtime savings do not materialize | Overuse of model-level overrides negates defaults | Audit config inheritance in project files | Move common policy back to project-level defaults |
| Freshness SLA misses | Freshness config not aligned to source cadence | Compare source arrival timings vs thresholds | Tighten freshness thresholds for critical sources/models |
| Late-arriving data is missed | `loaded_at_*` logic does not match the incremental model lookback window | Compare the incremental filter window to the freshness query or field being used | Use `loaded_at_query` that aligns with the same lookback logic |
| Warehouse metadata does not track data arrival correctly | Default freshness signal reflects object changes or refresh timing instead of real upstream data changes | Compare object metadata timestamps to actual source arrival timing | Add `loaded_at_field` or `loaded_at_query` for the affected source |
| Fusion compile cannot pass | Static analysis limitation on dynamic SQL | Reproduce compile errors in pilot scope | Apply temporary scoped `static_analysis: baseline`, then remediate |

## Verification Steps

1. Run `dbt parse` to confirm config validity.
2. Run targeted `dbt build --select ...` to verify changed vs unchanged behavior.
3. Confirm model-level exceptions are intentional and documented.
4. Confirm freshness thresholds are defined where the project needs SLA monitoring.
5. Confirm any custom `loaded_at_*` logic matches the actual data arrival pattern.

For platform-side checks and job configuration updates, keep a separate handoff note; this skill focuses on project code changes in the IDE.

## References

- [Implementation Notes](references/implementation-notes.md)
- [Rollout Playbook](references/rollout-playbook.md)
- [Snowflake-specific Considerations](references/snowflake.md)
- https://docs.getdbt.com/docs/deploy/state-aware-setup?version=1.12
- https://docs.getdbt.com/docs/deploy/state-aware-about?version=1.12