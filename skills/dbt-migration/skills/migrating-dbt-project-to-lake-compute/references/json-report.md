# The JSON Report (`schema_version` 1)

`dbt init lakecompute --json --quiet` prints one JSON object on stdout. With
`--quiet`, stdout is the report alone.

With `--summary`, the report has no `models` and no `switch.edits[].diff`,
`inputs` lists the 20 most read, and `ready` lists up to 20 ready models.
`autofix` and `switch` still list each view and edit: scope them with
`--select`. Read the summary first.

`schema_version` goes up when a field changes meaning or goes away. New fields
don't raise it. If it isn't `1`, tell the user this skill may be out of date,
and read the report with care.

## Top level

| Field | What it is |
|---|---|
| `schema_version` | `1` |
| `selected` | With `--select`/`--exclude`/`--selector`: the selected models' unique ids |
| `counts` | Models per tier: `ready`, `candidate`, `harder`, `blocked` |
| `already_lakecompute` | Models already on lakecompute (not counted) |
| `answers` | `fit`, `slower`, `may_not_run`, `not_sized`, `ready`, and `costliest` (`unique_id`, `name`, `cost`) |
| `blockers` | Issues grouped by `key`, most common first: `models` (a count), `examples`, `fix` |
| `inputs` | Inputs to change, most read first: `upstream`, `kind`, `readers`, `examples`, `message`, `fix` |
| `inputs_by_kind` | The inputs counted by `kind`: `inputs`, `readers`, `fix` |
| `autofix` | `views` (by unique id) and `moved`: what `--switch --convert-views` handles |
| `models` | One entry per model (see below); not with `--summary` |
| `ready` | With `--summary`: the ready models' labels, costliest first |
| `snowflake` | With `--snowflake`: `queries`, `executed`, `errors`, `unavailable` |
| `switch` | With `--switch`: `edits` and `skipped` |
| `validation` | With `--baseline` or `--validate` (see below) |

## Tiers

| Tier | Meaning |
|---|---|
| `ready` | Its inputs are Iceberg, and its SQL runs on Lake Compute. It can move now. |
| `candidate` | It can move once its input tables land in Iceberg. |
| `harder` | It can move once an upstream model is an Iceberg table. |
| `blocked` | Its own SQL, materialization or config needs a change first. |

## A model

| Field | What it is |
|---|---|
| `unique_id`, `name`, `label`, `path` | Which model. `label` includes the version (`orders.v2`) |
| `materialized` | `table`, `incremental`, `view`, ... |
| `tier` | See above |
| `already_lakecompute` | It runs on lakecompute already |
| `iceberg_of` | It is an Iceberg table that `--switch` added for a view (it builds on Snowflake) |
| `sql` | `state` (`compatible`, `incompatible`, `inconclusive`, `unchecked`), `key`, `error` |
| `rewrite` | SQL `--switch` rewrites for Lake Compute: `fragments` (`function`: the Snowflake function, or `colon path`; `before`, `after`), and `applies_to_source` |
| `issues` | What blocks it: `key`, `message`, `fix` |
| `changes` | What its inputs need: `kind`, `upstream`, `message`, `tables`, `fix` |
| `fit` | `good`, `slower`, `may_not_run`, `unknown` (from sizing; see below) |
| `sizing`, `cost` | With `--snowflake` (or a run_results.json): bytes, memory, credits |

`sql.state` `unchecked` means the check couldn't see the model's real SQL: for
example, offline, a macro that looks up a table's columns. `--snowflake`
compiles it with the warehouse.

## Fixes

Every issue and change has `fix`: `by` says who can fix it, `hint` says how.

| `fix.by` | Who |
|---|---|
| `switch` | `dbt init lakecompute --switch` (with the flag the hint names) |
| `sql` | An edit to the model's SQL; check again after |
| `config` | An edit to the model's (or its input's) config |
| `data` | Landing the input in Iceberg, outside the project |
| `unsupported` | Nothing in the project: it stays on Snowflake |

Issue keys come in families (`function:iff`, `syntax:semi_structured`,
`materialization:view`, `config:post_hook`, `type:date_trunc_date`,
`undeclared:<DATABASE>`). `blockers` groups them by key.

## Fit (from sizing)

A model that needs more memory than a worker has still runs on Lake
Compute: it spills to disk, and runs slower. Only a model whose measured
size is more than a worker may hold in memory and on disk together may not
run. That limit is rough: such a model is worth trying too.

| `fit` | Meaning |
|---|---|
| `good` | A worker has the memory for it, or its plan streams |
| `slower` | It needs more memory than the largest worker: it runs, slower. `sizing.slowdown` is about how many times slower (1.5 to 4), and `sizing.warnings` says why |
| `may_not_run` | Its measured bytes (query history, table sizes) are past a rough limit of what a worker holds, spilled too. `sizing.may_not_run` says why. Say it may fail; it can still be tried, and goes back to Snowflake if it fails |
| `unknown` | Not sized: run `--snowflake` to size it. Expect it to fit |

When a model is `slower`, encourage trying it: say it runs, and offer the
scoped dry-run switch, then a build. `slowdown` compares Lake Compute
spilling with Lake Compute holding it in memory, not with Snowflake: don't
say "slower than Snowflake". If the build is too slow, the model goes back
to Snowflake with `git checkout` of its file.

## View remedies (`autofix.views`)

| `remedy` | What `--switch --convert-views` does |
|---|---|
| `inline` | Makes the view ephemeral, on lakecompute: inlined into its one reader |
| `table` | Makes it a table on lakecompute: built once, read by each reader |
| `intermediate` | Leaves the view, adds `table` (`<view>_iceberg`), an Iceberg table of it built on Snowflake, and points the moving readers at it |

Each has `why` (the reason) and `readers` (the models that move with it).

## Switch plan (`switch`)

- `summary`: the edits counted: `switched` (models set to lakecompute),
  `rewritten`, `tables` and `inlined` (views), `added` (new Iceberg tables of
  views), `repointed` (readers pointed at them), `skipped`. Quote these
  numbers rather than counting the edits.
- `edits[]`: `model`, `path`, `how`, `diff`, `converted`, `created` (a new
  file), `repointed` (now reads an Iceberg table of a view), `remedy` (for a
  view: `table`, `inline`, or `intermediate` on the added table),
  `rewritten_calls`.
- `skipped[]`: `model`, `reason`.

## Validation (`validation`)

- `--baseline`: `baseline` (the file), `taken`, `failed`.
- `--validate`: `validated[]` with `unique_id`, `relation` and `status`:
  `matches`; `differs` (with `differences`); `not_rebuilt` (unchanged since
  the baseline); `missing` (with `why`).
- `--dry-run`: `would_read`, the tables it would read.
