---
name: configuring-state-aware-orchestration
description: Use when configuring state-aware orchestration in dbt Cloud jobs, including selecting state comparison strategy, defining defer behavior, and validating deployment safety.
user-invocable: false
metadata:
  author: dbt-labs
---

# Configuring State-Aware Orchestration

## Overview

Use this skill inside the dbt IDE to change dbt project code and configs for maximum SAO savings. Focus on `dbt_project.yml`, model/source YAML, and model-level config so unchanged nodes are skipped safely while freshness SLOs are still met.

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
- Known data freshness SLOs for critical domains
- Agreement on where defaults live (project-level vs model-level overrides)

See [Prerequisites and Eligibility](references/prerequisites-and-eligibility.md) for code-scope readiness and [Platform and Job Adjustments (Out of Scope)](references/platform-and-job-adjustments.md) for non-code setup dependencies.

## Questions to Ask First

1. Which models/domains need the strongest freshness guarantees?
2. What project-level defaults should apply to most models?
3. Which models require explicit overrides due to tighter SLOs?
4. Is `updates_on` standardized (`any` vs `all`) for this domain?
5. What config change can be safely rolled back if skips are wrong?

## Recommended Workflow

1. Identify current config surface in code (project defaults, model overrides, source freshness).
2. Add or refine project-level defaults first to maximize broad savings with minimal complexity.
3. Add model-level overrides only for exceptions where business SLOs require it.
4. Validate expected behavior with parse/build/list commands in development.
5. Record rationale in code comments or PR notes for future maintainers.

See [Rollout Playbook](references/rollout-playbook.md) for code-first rollout sequencing.

## Configuration Defaults and Guardrails

1. Start simple and avoid advanced settings until baseline SAO behavior is stable.
2. Add source freshness monitoring before tuning model-level policies.
3. Use project-level defaults first, then add model-level exceptions.
4. Keep model override count low to avoid policy drift.

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

### Core SAO Config Levers in Project Code

- `build_after`: controls rebuild cadence and is the main savings lever.
- `updates_on`: controls what upstream change signals should trigger a rebuild.
- `loaded_at_field` / `loaded_at_query`: use only for sources needing custom freshness logic.

### Temporary Fusion Unblocker (Use Sparingly)

If Fusion compile blockers prevent SAO rollout, a temporary fallback is:

```yaml
models:
  +static_analysis: off
```

This reduces Fusion capabilities and should be narrowed to problematic models as soon as possible.

## Common Failure Modes

| Symptom | Likely Cause | Validation | Fix |
|---------|--------------|------------|-----|
| SAO skips too much or too little | Misaligned freshness/SLO config | Compare expected critical models vs actual run graph | Adjust `build_after` and source freshness thresholds |
| Runtime savings do not materialize | Overuse of model-level overrides negates defaults | Audit config inheritance in project files | Move common policy back to project-level defaults |
| Freshness SLA misses | Freshness config not aligned to source cadence | Compare source arrival timings vs thresholds | Tighten freshness thresholds for critical sources/models |
| Fusion compile cannot pass | Static analysis limitation on dynamic SQL | Reproduce compile errors in pilot scope | Apply temporary scoped `static_analysis: off`, then remediate |

## Verification Steps

1. Run `dbt parse` to confirm config validity.
2. Run targeted `dbt build --select ...` to verify changed vs unchanged behavior.
3. Confirm model-level exceptions are intentional and documented.
4. Confirm freshness thresholds are defined for critical sources.

For platform-side checks and job configuration updates, use [Platform and Job Adjustments (Out of Scope)](references/platform-and-job-adjustments.md).

## References

- [Implementation Notes](references/implementation-notes.md)
- [Prerequisites and Eligibility](references/prerequisites-and-eligibility.md)
- [Platform and Job Adjustments (Out of Scope)](references/platform-and-job-adjustments.md)
- [Rollout Playbook](references/rollout-playbook.md)
- [Success Metrics and Definition of Done](references/success-metrics.md)
- [Resource Links](references/resource-links.md)
- https://docs.getdbt.com/
