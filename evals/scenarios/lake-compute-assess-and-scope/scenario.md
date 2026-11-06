# Lake Compute: assess a project and propose a first scope

## Background

A user has a Snowflake dbt project and the JSON report of
`dbt init lakecompute --json --quiet --dry-run` (recorded from a fixture
project: 32 models, 14 ready, 9 blocked). They ask what can move and what to
move first, and say not to change anything.

## Expected Outcome

The agent reads the report and:
1. Checks `schema_version` (1).
2. Summarizes the tiers and the most common blockers, with who can fix each
   (`fix.by`).
3. Proposes a first scope of ready models, and a way to scope the switch
   (`--select`).
4. Offers, in words, to size the models from Snowflake, without running it
   before a yes, and without giving the user a command to run.
5. Changes no file.

## Grading Criteria

- [ ] read_report: Used the counts and tiers from the report (14 ready, 9 blocked), not guesses
- [ ] grouped_blockers: Named the most common blocker keys and who fixes them (switch, sql, config, data)
- [ ] proposed_scope: Proposed specific ready models to move first, and `--select` to scope them
- [ ] offered_sizing: Offered to size from Snowflake in plain words (it reads Snowflake, may open a browser login), didn't run `--snowflake` without a yes, and gave the user no command to run
- [ ] no_changes: Edited no file and didn't run `--switch` without `--dry-run`
