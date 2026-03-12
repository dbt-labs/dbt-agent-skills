## Rollout Playbook

This playbook converts SAO strategy into code-first execution inside the dbt IDE.

### 1. Baseline the Current Config Surface

Goal: Understand existing defaults and override sprawl.

Checklist:

- Inventory project-level defaults in `dbt_project.yml`
- Inventory model-level overrides in YAML/SQL configs
- Capture baseline metrics for runtime, cost, models-per-run

### 2. Establish Project-Level Defaults

Goal: Maximize broad savings with minimal config complexity.

Implementation:

- Add or refine project-level source freshness
- Define default `build_after` by domain behavior
- Standardize `updates_on` policy (`any` or `all`) per domain
- Keep policy simple before adding exceptions

Exit criteria:

- Defaults compile cleanly and are understandable
- Early validation shows expected skip/rebuild behavior

### 3. Add Targeted Model-Level Exceptions

Goal: Protect high-priority SLOs without undermining global savings.

Implementation:

- Add model-level overrides only where defaults are insufficient
- Document each override with the business reason
- Prefer grouped exceptions by layer/domain over one-off rules
- Re-test selected critical paths

Exit criteria:

- Override count is controlled and justified
- No unexplained rebuild expansion

### 4. Clean Up and Govern Config Quality

Goal: Prevent configuration drift over time.

Implementation:

- Remove stale overrides that duplicate defaults
- Keep a domain config matrix in repo docs
- Add PR review checklist for SAO config changes
- Review savings and SLA fit at regular intervals

Exit criteria:

- Configuration remains minimal and explainable
- New model onboarding follows default-first policy

### 5. Coordinate Out-of-Scope Platform Changes

Goal: Handoff non-code adjustments when needed.

- Share required job/platform changes with deployment owners
- Track dependencies that can affect measured savings

See [Platform and Job Adjustments (Out of Scope)](platform-and-job-adjustments.md).
