# Implementation Notes

Use these notes to maximize SAO savings through code and config changes in the dbt project.

## Start with Defaults

- SAO already works without custom configuration when code changes or new source data is detected.
- An activation phase with zero or near-zero tuning can still deliver meaningful savings, so confirm the baseline before adding complexity.
- Add custom configuration only when the project needs tighter control over rebuild cadence, freshness semantics, or SLA monitoring.
- Source freshness is still recommended on important sources because it improves observability and makes SAO tuning easier to reason about.
- Keep platform setup, deploy-job configuration, and environment changes out of the code change itself.

## Recommended Configuration Sequence

1. Confirm which behavior already comes from SAO defaults versus explicit config.
2. Validate the activation-phase baseline before tuning.
3. Establish project-level defaults first (`build_after`, `updates_on`, source freshness).
4. Add model-level overrides only for explicit SLO exceptions.
5. Consolidate duplicated override patterns back into project defaults.
6. Re-test changed domains and document rationale for each remaining exception.

## Business-Led Simplification

- Prefer a small number of freshness tiers driven by business needs over a large matrix of technical policies.
- A simple project-wide default with a few narrow overrides is usually easier to operate than encoding many schedules into many folders.
- If the project needs hourly, daily, and weekly behavior, start with one broad default and only add targeted exceptions for intra-day or long-range late-arriving cases.

## Valid Configuration Surfaces

- `dbt_project.yml` for project-level or folder-level defaults
- model and source YAML for resource-level configuration
- model SQL config blocks for narrow exceptions

Prefer the highest-level config surface that safely represents the intended policy.

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

Recommendation:

- Configure source freshness for important sources even when SAO would technically work without it.
- Make sure those freshness checks are actually running so the configuration provides real operational signal.

## Advanced Configuration Guidance

- `build_after`: Use to set expected refresh cadence and avoid unnecessary rebuilds.
- `updates_on`: `any` is the default behavior; `all` can reduce unnecessary builds when a downstream model should wait for all upstream dependencies.
- `loaded_at_field` / `loaded_at_query`: Use only where metadata-based freshness is insufficient.

If you need different runtime behaviors across jobs, a useful pattern is:

- set a stable project default in code
- use narrow model-level overrides for true exceptions
- coordinate any job-level `--vars` overrides with deployment owners rather than encoding job-specific assumptions everywhere in model config

## Choosing `updates_on` by Model Type

- Fact-like models commonly fit `updates_on: any` because they often should rebuild as soon as any upstream source delivers new rows.
- Dimension-like models commonly fit `updates_on: all` when they depend on multiple upstream datasets and partial refreshes would produce incomplete or misleading attributes.
- Use `any` for dimensions when a model depends on one source or when partial freshness is acceptable.
- Use `all` for facts when business logic depends on coordinated batch completeness across multiple upstream inputs.
- Make the choice based on whether the model should react to the first upstream change or wait for a complete synchronized set of changes.
- Be cautious applying `all` broadly on frequent jobs. If upstream datasets refresh at different cadences, `all` can lengthen runtimes and create queueing.

For `loaded_at_*` configuration:

- define `loaded_at_field` or `loaded_at_query`, but not both
- use YAML block syntax for multi-line `loaded_at_query`
- prefer `loaded_at_query` when freshness needs to reflect thresholds, lookback windows, or partial ingestion behavior

Use warehouse specific information and supersede these implementation notes where necessary.

## Late-Arriving Data Guidance

- If an incremental model uses a lookback window, make sure freshness logic aligns with that same window.
- A `loaded_at_field` based on event time can miss late-arriving records when the event timestamp is old but the ingest happened now.
- In these cases, prefer `loaded_at_query` that mirrors the incremental model's lookback logic.

Longer-range late-arriving workflows may justify a separate daily or weekly treatment, but keep that policy simple and explicit.

## First-Run and New-Model Guidance

- Newly introduced models may need explicit validation on their first deploy because SAO may not yet have the expected freshness history for the rollout path.
- Do not assume first-run behavior will look identical to steady-state reuse behavior.
- Add a handoff note when a rollout includes brand-new models or dependencies that have not yet established their freshness pattern.

## High-Savings Patterns

- Prefer project-level defaults for shared behavior across a domain.
- Keep overrides near only the models with stricter freshness needs.
- Avoid per-model customization unless the business impact is clear.
- Periodically remove stale overrides that no longer differ from defaults.

## Temporary Compile Unblocker

If Fusion compile issues block SAO adoption, use this temporary fallback:

```yaml
models:
  +static_analysis: baseline
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
- `updates_on` choices are consistent with whether a model can tolerate partial upstream freshness
- Source freshness is configured where the project needs SLA visibility or custom freshness semantics
- Any `loaded_at_*` logic is aligned with real data arrival behavior
- Late-arriving data paths are handled explicitly where relevant
- Config changes are grouped in reviewable commits
- Out-of-scope platform/job dependencies are captured in handoff notes
