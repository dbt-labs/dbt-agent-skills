## Rollout Playbook

This playbook is for a user working inside the dbt Cloud IDE with the dbt developer agent. Use it to guide the agent through a step-by-step SAO implementation in project code.

## Operating Principle

Have the agent work in small, verifiable steps:

- inspect current config first
- propose the smallest broad default that improves SAO behavior
- implement project-level defaults before model-level exceptions
- validate after each config change
- summarize what changed, what was validated, and what still needs human confirmation

## Step 1: Inventory the Current State

Goal: Map the current config surface before it edits anything.

You should:

- inspect `dbt_project.yml` for existing project-level defaults
- inspect model and source YAML files for `build_after`, `updates_on`, freshness, and `loaded_at_*` settings
- inspect model SQL for inline config overrides
- identify whether defaults already exist and where override sprawl has accumulated
- call out warehouse-specific freshness cases that may need explicit handling

Expected agent output:

- a short inventory of current SAO-related config
- a list of files likely to change
- a recommendation for the safest first default to add or refine

## Step 2: Set the Broadest Safe Project-Level Defaults First

Goal: Maximize savings with minimal config complexity.

Implement project-level defaults before any exceptions:

- add or refine source freshness where missing for critical sources
- define a default `build_after` policy that fits the dominant data arrival pattern
- standardize `updates_on` behavior for the domain unless there is a clear reason not to
- keep the first pass conservative and easy to reason about

Agent constraints:

- do not introduce many one-off overrides in the first pass
- do not mix platform changes with code changes
- do not rely on warehouse metadata semantics unless they are known to be valid

Validation after this step:

- run `dbt parse`
- run targeted `dbt build --select ...` or other narrow validation commands appropriate for the changed scope
- confirm the resulting behavior is understandable enough to explain in a short summary

## Step 3: Add Targeted Exceptions Only Where Defaults Fail SLOs

Goal: Protect critical models without undermining the value of the defaults.

Add model-level exceptions only after the default pass is validated:

- identify high-priority models or domains with tighter freshness needs
- add overrides only for those exceptions
- prefer grouped exceptions by layer or domain over scattered one-off rules
- document the reason for each override in the change summary or nearby docs

Validation after this step:

- re-run `dbt parse`
- run targeted builds for the affected critical paths
- verify that the exception count remains small and intentional
- check that the new exceptions do not cause broad rebuild expansion

## Step 4: Handle Warehouse-Specific Freshness Edge Cases Explicitly

Goal: Make the agent avoid false assumptions about warehouse object metadata.

Tell the agent to:

- check whether object metadata reflects real upstream data arrival or only object-level changes
- add `loaded_at_field` or `loaded_at_query` when default metadata signals are unreliable
- use warehouse-specific reference guidance when needed rather than hard-coding warehouse assumptions into the general workflow

For Snowflake-specific behavior, see [snowflake.md](snowflake.md).

Validation after this step:

- compare metadata timestamps to actual source arrival expectations
- confirm that freshness logic is tied to data recency rather than object-alter timing when required

## Step 5: Clean Up Config Drift Before Stopping

Goal: Leave the project in a simpler, more governable state than before.

You should:

- remove stale overrides that now duplicate project defaults
- keep the final config surface as small as possible
- note any remaining exceptions or follow-up work for humans
- summarize what was changed, what was validated, and what remains out of scope

Exit criteria:

- project defaults are clear
- exception count is controlled
- validation commands passed for the intended scope
- remaining risks or assumptions are explicitly called out

## Step 6: Escalate Non-Code Work Instead of Mixing It Into the Change

Goal: Keep the dbt developer agent focused on code and config changes inside the IDE.

Stop and hand off when the next step requires:

- dbt Cloud job schedule changes
- environment flag changes
- account-level feature enablement
- orchestration ownership decisions outside project code
