## Platform and Job Adjustments (Out of Scope)

This skill focuses on project code and config changes in the dbt IDE.
Use this reference to track non-code dependencies that may be required for full SAO savings.

### Typical Out-of-Scope Items

- Enabling Fusion and SAO feature flags at account/platform level
- Editing job schedules and execution cadence
- Updating environment-level settings
- Managing account permissions and operational ownership
- Organization-wide rollout governance outside repository code

### Handoff Checklist

- Confirm platform prerequisites are met (Fusion + SAO availability)
- Confirm source freshness jobs are scheduled where required
- Confirm job ownership and overlap plan across deployment jobs
- Confirm baseline and post-change metrics collection ownership

### Coordination Template

Use this handoff summary in PRs or implementation docs:

1. What code/config changed in the project
2. Why the change should improve SAO savings
3. Which platform/job changes are required to realize full impact
4. Who owns each out-of-scope change and expected completion date

### Notes

Keep this file as a handoff artifact. Do not place platform operation steps into the main skill workflow unless they can be executed directly from project code.