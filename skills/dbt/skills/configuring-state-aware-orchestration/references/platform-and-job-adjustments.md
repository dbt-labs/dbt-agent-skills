# Platform and Job Adjustments (Out of Scope)

Use this reference when the next step is not a code change in the dbt Cloud IDE.

## What Stays Out of This Skill

Do not try to perform or simulate these actions from project code:

- enabling Fusion on the environment
- enabling state-aware orchestration in dbt Cloud job settings
- enabling Efficient testing in job settings
- creating or editing deploy job schedules and triggers
- changing account entitlements, seat access, or other platform permissions
- selecting compare-against behavior in the dbt Cloud UI

## Preconditions to Confirm with the User

- the project is running in a Fusion-enabled deployment environment
- the relevant job is a deploy job
- the job has state-aware orchestration enabled if it was not created with defaults that already enable it
- the user has permission to view, create, edit, and run jobs
- the relevant workload is SQL, not Python

## What the Agent Can Do Instead

- prepare the project-side SAO configuration in `dbt_project.yml`, YAML properties, and SQL config blocks
- identify which non-code settings the user must verify in dbt Cloud
- summarize any platform dependencies or blockers in a handoff note

## Handoff Checklist

Ask the user or deployment owner to confirm:

1. Fusion is enabled for the target deployment environment.
2. The job is a deploy job, not CI or merge.
3. State-aware orchestration is enabled in job settings where required.
4. Efficient testing is enabled only if the project is ready for it.
5. Compare-against behavior and trigger settings match the intended rollout plan.