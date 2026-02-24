Create `docs/investigations/job-failure-<date>.md`:

```markdown
# Job Failure Investigation: <Job Name>

**Date:** YYYY-MM-DD
**Job ID:** <id>
**Status:** Unresolved

## Summary
Brief description of the failure and symptoms.

## What Was Checked

### Tools Used
- [ ] list_jobs_runs - findings
- [ ] get_job_run_error - findings
- [ ] git history - findings
- [ ] Data investigation - findings

### Hypotheses Tested
| Hypothesis | Evidence | Result |
|------------|----------|--------|
| Recent code change | No changes to affected models in 7 days | Ruled out |

## Patterns Observed
- Failures occur between 2-4 AM (peak load time?)
- Always fails on model X

## Suggested Next Steps
1. [ ] Check the data ingestion process to see if new data was added
2. [ ] Check if a new version of dbt or of the dbt adapter was released

## Related Resources
- Link to job run logs
- Link to relevant documentation
```
