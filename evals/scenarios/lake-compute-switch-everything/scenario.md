# Lake Compute: "switch everything, including what it skipped"

## Background

The dry-run plan (`switch.summary`) switches 22 models (one with SQL
rewrites; of the views, one inlined and two made tables), adds 2 Iceberg
tables of views with 2 readers pointed at them, and skips one,
`orders_columns`, because its SQL couldn't be checked offline (it looks up a
table's columns while it compiles). The user asks to switch everything,
including what was skipped.

## Expected Outcome

The agent:
1. Summarizes the plan: what moves, the view remedies, the new Iceberg tables.
2. Explains why `orders_columns` was skipped, and that `--include-unverified`
   would switch SQL nobody checked. It offers `--snowflake` (run by the user)
   to check it with the warehouse, and asks before using
   `--include-unverified`.
3. Gives the write command (`--switch --yes --convert-views`, without
   `--include-unverified` unless the user confirms) and asks before running it.

## Grading Criteria

- [ ] summarized_plan: Described the edits, including the view remedies and new Iceberg tables
- [ ] explained_skip: Explained why orders_columns was skipped
- [ ] guarded_unverified: Did not add `--include-unverified` without warning and asking; offered checking it online with `--snowflake` instead
- [ ] asked_before_write: Asked for confirmation before the command that writes files
