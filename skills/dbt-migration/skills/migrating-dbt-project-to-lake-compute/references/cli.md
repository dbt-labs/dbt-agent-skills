# `dbt init lakecompute`: Flags and Exit Codes

## Flags

| Flag | What it does | Reads Snowflake | Writes files |
|---|---|---|---|
| `--json` | Prints the report as JSON. With `--quiet`, stdout is the report alone | | |
| `--summary` | With `--json`: grouped blockers and inputs, the ready models, no per-model entries and no diffs. | | |
| `--select`, `--exclude`, `--selector` | dbt's selection: reports on, sizes and switches only these models (the whole project is still compiled). Graph operators work as in dbt. The parents and views they need come along | | |
| `--all` | Lists every model in the text report | | |
| `--dry-run` | Writes nothing and runs no warehouse query, whatever else is passed: `--switch` prints its plan, `--snowflake` prints its queries, `--baseline` lists its tables | | |
| `--snowflake` | Sizes models and prices their builds from Snowflake: query history, EXPLAIN plans, table sizes | yes | |
| `--history-days <n>` | With `--snowflake`: the days of query history to read | | |
| `--switch` | Switches the models that can move, after showing the diff | | yes |
| `--convert-views` | With `--switch`: also handles the views that keep models from moving | | yes |
| `--include-unverified` | With `--switch`: also switches models whose SQL couldn't be checked | | yes |
| `--no-rewrite` | Doesn't rewrite SQL that Lake Compute's DuckDB rejects | | |
| `--baseline` | Fingerprints each model's table on Snowflake, into `target/lakecompute/baseline.json` | yes | yes |
| `--validate` | Fingerprints them again and compares with the baseline | yes | |
| `--yes` | Goes ahead without asking. `--json` with `--switch`, `--snowflake`, `--baseline` or `--validate` needs it (or `--dry-run`) | | |
| `--run-results <path>` | Build times from this run_results.json | | |
| `--warehouse-size <size>` | The warehouse size to price build times at | | |

Every Snowflake statement is appended to `target/lakecompute/warehouse_queries.sql`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The report was printed. Blocked models are not a failure. |
| `1` | The project didn't compile (the error says why), a file couldn't be written, `--validate` found a table that differs or can't be read, or a `--baseline` fingerprint failed |
| `2` | A usage error: for example `--json --switch` without `--yes` or `--dry-run` |

## On a terminal

Without flags that act, on a terminal, `dbt init lakecompute` opens an
interactive guide. An agent's shell isn't a terminal, so it gets the report
instead. Prefer `--json --quiet` all the same.
