# Fusion Migration Triage — GitHub Issue Search Behavior

## Background

A user is migrating their dbt project from dbt-core to Fusion. They ran `dbt compile` and are seeing `dbt1501: Failed to render SQL too many arguments` on a model that uses the Jinja `truncate()` filter. This works in dbt-core but fails in Fusion because MiniJinja doesn't support the same `truncate()` arguments as Jinja2.

This is tracked in a real GitHub issue (dbt-labs/dbt-fusion#1318). The key behavior being tested is: **when the agent encounters an error it can't immediately explain from the skill's pattern catalog, does it search GitHub issues to find known Fusion limitations?**

## Expected Outcome

The agent should:
1. Recognize this error is not a standard user-fixable pattern
2. Search GitHub issues (dbt-labs/dbt-fusion) to check if this is a known limitation
3. Reference the GitHub issue or explain this is a Fusion engine gap
4. Provide context to the user about whether this is tracked/being worked on

Whether the agent also suggests a workaround is secondary — the primary signal is whether it reaches out to GitHub.

## Grading Criteria

- [ ] searched_github: Attempted to search or reference GitHub issues for dbt-labs/dbt-fusion (via WebFetch, Bash with gh/curl, or by referencing a known issue URL)
- [ ] identified_fusion_limitation: Recognized this as a Fusion/MiniJinja engine difference, not a user code error
- [ ] referenced_issue: Referenced a specific GitHub issue number or URL related to this limitation
- [ ] provided_context: Gave the user actionable context — is this tracked? is there a workaround? should they wait for a fix?
