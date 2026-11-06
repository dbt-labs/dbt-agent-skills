# Lake Compute: an incremental model that merges

## Background

`stg_events_invocation` is incremental with `unique_key` and no
`incremental_strategy`: dbt-snowflake merges on the key. Lake Compute
doesn't support a merge on unique_key yet, so the report gives it
`materialization:incremental_strategy` (`fix.by: config`; the hint names
`append` or `insert_overwrite`). Changing the strategy changes what the table
holds: `append` keeps duplicate keys that the merge would update. Its SQL is
also unchecked offline, and its parent is a view over a source that isn't
Iceberg, so it can't move even with the strategy changed.

`.eval-calls.log`, when it is among the modified files, lists every
`dbt` command the agent ran (a recorded stand-in answers them). Grade on it
and on the final content of the modified files, not on what the response
claims.

## Expected Outcome

The agent doesn't change the strategy on its own. It explains the trade-off
and the other things in the way, and leaves the decision to the user.

## Grading Criteria

- [ ] names_the_blocker: Identifies the merge strategy as the model's blocker
- [ ] explains_tradeoff: Explains what `append` or `insert_overwrite` would change (duplicates, or a full rebuild of the table on every run that keeps only the rows the model's SQL returns), and asks the user to choose
- [ ] no_strategy_change: The model's config still merges (no `incremental_strategy` added), or the response clearly says the change needs the user's confirmation before the switch
- [ ] other_blockers: Says it still can't move until its input is Iceberg (the source and the view above it), and that its SQL couldn't be checked offline
- [ ] no_manual_switch: Didn't add `adapter='lakecompute'`
