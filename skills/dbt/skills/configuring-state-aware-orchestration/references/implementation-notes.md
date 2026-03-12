# Implementation Notes

Use these notes to maximize SAO savings through code and config changes in the dbt project.

## Recommended Configuration Sequence

1. Establish project-level defaults first (`build_after`, `updates_on`, source freshness).
2. Validate the default behavior on representative model paths.
3. Add model-level overrides only for explicit SLO exceptions.
4. Consolidate duplicated override patterns back into project defaults.
5. Re-test changed domains and document rationale for each remaining exception.

## Project-Level Source Freshness Starter

```yaml
sources:
  dbt_project_name:
    +freshness:
      warn_after:
        count: 12
        period: hour
```

Use threshold values that match business SLOs and source arrival characteristics.

## Advanced Configuration Guidance

- `build_after`: Use to set expected refresh cadence and avoid unnecessary rebuilds.
- `updates_on`: Standardize on one policy (`any` or `all`) per domain to reduce confusion.
- `loaded_at_field` / `loaded_at_query`: Use only where metadata-based freshness is insufficient.

## High-Savings Patterns

- Prefer project-level defaults for shared behavior across a domain.
- Keep overrides near only the models with stricter freshness needs.
- Avoid per-model customization unless the business impact is clear.
- Periodically remove stale overrides that no longer differ from defaults.

## Temporary Compile Unblocker

If Fusion compile issues block SAO adoption, use this temporary fallback:

```yaml
models:
  +static_analysis: off
```

Prefer scoping this to specific models once root causes are known.

## Code-Level Rollback Guidance

1. Keep a small, atomic commit for each config policy change.
2. If skip/rebuild behavior is incorrect, revert the specific config commit.
3. Re-apply with narrower scope and explicit comments.
4. Keep a changelog of config intent by domain.

## Review Checklist

- Project-level defaults are defined and minimal
- Model-level overrides are justified and documented
- Source freshness is configured for critical sources
- Config changes are grouped in reviewable commits
- Out-of-scope platform/job dependencies are captured in handoff notes
