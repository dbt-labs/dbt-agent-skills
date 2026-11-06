# Lake Compute: a model bigger than a worker

## Background

`orders` is ready (its inputs are Iceberg, its SQL runs), and it is the
costliest model on Snowflake (~97 credits a month). Sizing gives it `fit:
slower`: it scans ~180 GiB, and its join needs ~310 GiB of memory, more than
Lake Compute's largest worker. Lake Compute still runs it: it spills to disk,
and may run ~2.5x slower than in memory (`sizing.slowdown`). Nothing blocks
it.

`.eval-calls.log`, when it is among the modified files, lists every
`dbt` command the agent ran. Grade on it and on the response.

## Expected Outcome

The agent says it can move, encourages trying it, and is clear about the
cost: about 2.5x slower than in memory, because it spills.

## Grading Criteria

- [ ] can_move: Says orders can move to Lake Compute (it's ready); doesn't say it's too big to run or must stay on Snowflake
- [ ] slower_not_blocked: Explains it needs more memory than a worker, so it spills and may run about 2.5x slower, and that it still runs
- [ ] encourages_trying: Recommends trying it (e.g. the scoped dry-run switch, then a build), and says it can go back to Snowflake if it's too slow
- [ ] no_changes: Modified no project file, and ran only dry-run checks
