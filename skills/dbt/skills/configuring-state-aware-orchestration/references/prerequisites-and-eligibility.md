## Prerequisites and Eligibility

Use this checklist before implementing SAO through project code changes in the dbt IDE.

### In-Scope Requirements (Code and Config)

- dbt project is available in the IDE
- Ability to edit `dbt_project.yml`, source YAML, and model configs
- Defined domain/model freshness SLOs
- Clear ownership for reviewing and merging config changes

### Operational Readiness

- Baseline metrics available for 14 to 30 days:
  - Runtime
  - Cost
  - Models-per-run
- Named owners for rollout and rollback decisions
- Agreed domain/model SLO expectations

### Out-of-Scope but Required Dependencies

- SAO requires Fusion and account-level enablement
- Fusion and SAO controls may be enabled separately
- Job schedule and environment tuning may be needed for full savings realization

See [Platform and Job Adjustments (Out of Scope)](platform-and-job-adjustments.md).

### Important Caveat

Fusion capabilities continue to evolve. If compile blockers appear during rollout, use targeted mitigation and avoid broad permanent disablement of Fusion static analysis.

### Resident Architect Enablement (Internal)

- Fusion GTM enablement program completion
- Primary Fusion documentation review
- SAO implementation playbooks reviewed (Activate, Accelerate, Architect)
