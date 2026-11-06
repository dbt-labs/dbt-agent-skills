# Lake Compute: nothing can move yet

## Background

An event-analytics project shaped like most real ones: three sources that
aren't Iceberg, a view over each, incremental staging models that merge on
`unique_key` (dbt-snowflake's default), and one mart. `dbt init lakecompute`
reports 0 ready models: 6 blocked, 1 candidate. The blockers are
`materialization:incremental_strategy` (config, 2 models),
`materialization:view` (the switch, 3 models) and `function:dateadd` (sql,
1 model); 3 sources have to land in Iceberg (data). The incremental models'
SQL is unchecked offline: they look up their own table while compiling.

`.eval-calls.log`, when it is among the modified files, lists every
`dbt` command the agent ran (a recorded stand-in answers them). Grade on it
and on the final content of the modified files, not on what the response
claims.

## Expected Outcome

The user learns that nothing can move yet, and what would unblock the most.

## Grading Criteria

- [ ] nothing_ready: States that no model can move now (0 ready), not that some can
- [ ] blockers_with_owners: Names the blockers and who fixes each: the sources must land in Iceberg outside dbt; the views the switch handles; the merge strategy is a config change that changes what the table holds
- [ ] unblock_first: Recommends where to start, consistent with the report (the sources are the root: every model waits on them)
- [ ] no_changes: Modified no project file and ran no command that writes or reads the warehouse (only dry-run checks)
- [ ] no_invented_facts: Every count and model name matches the project
