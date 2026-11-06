---
name: validating-lake-compute-migration
description: Use whenever reading `dbt init lakecompute --validate` (or `--baseline`) output, or answering whether a Lake Compute migration is done - checking that switched models build the same tables they built on Snowflake, and finding why a table differs.
user-invocable: false
allowed-tools: "Bash(dbt init lakecompute --json --quiet --dry-run*), Bash(dbtf init lakecompute --json --quiet --dry-run*), Bash(git diff*), Bash(git log*), Bash(git show*), Read, Grep, Glob"
metadata:
  author: dbt-labs
---

# Validating a Lake Compute Migration

`dbt init lakecompute` checks a switched model's table in two passes, both
read-only on Snowflake:

1. Before the switch, `--baseline` takes a fingerprint of each table: its
   rows; per column, its non-null values, their sum (numbers) or distinct
   count, and a hash of the values.
2. After the switched models are built on Lake Compute (which writes the
   tables back to Snowflake), `--validate` takes the fingerprints again and
   compares them.

Both passes read the warehouse and may open a browser login: say so, and on
a yes, run them yourself
(`dbt init lakecompute --json --quiet --select <selector> --validate --yes`),
then read the result, or `target/lakecompute/` for the details.

## Answering "Is It Done?"

Answer in this order:

1. **Done or not**: the migration is done only when every table `matches`.
2. **Each table** that doesn't, with what to do (the table below).
3. **For each table that differs**: the expression behind each differing
   column (read the model's SQL), and its likely cause (see
   [finding why](#finding-why-a-table-differs)).
4. **The fallback**: if a difference can't be fixed now, revert that model
   (`git checkout -- <its file>`), and its readers that moved with it.

## Reading the result

`--validate` exits with 1 when a table differs or can't be read (`--baseline`: when a fingerprint fails). `validation.validated[]`
gives each table's `status`:

| `status` | Meaning | Next |
|---|---|---|
| `matches` | Same rows, same values in every column | Done |
| `not_rebuilt` | The table hasn't changed since the baseline | Build the switched model on Lake Compute, then validate again |
| `missing` | The table can't be read (`why`) | Check the build, and that the model's relation exists |
| `differs` | `differences` lists what changed | Find the cause (below) |

## Finding why a table differs

Work through these in order. Stop at the first that explains every
difference, and tell the user.

1. **The inputs changed.** The fingerprints compare tables as built. If a
   source got new rows between the Snowflake build and the Lake Compute
   build, `rows` and sums differ for that reason alone. Ask the user whether
   the sources load continuously. If they do, take a new baseline with the
   sources paused, or right before the Lake Compute build.
2. **A rewrite or an edit.** Find the columns that differ in the model's SQL:
   `git diff` the model's file since the switch. The switch's `rewrite`
   fragments and your own edits from
   [fixing-lake-compute-blockers](../fixing-lake-compute-blockers/SKILL.md)
   are the likely cause when only those columns differ.
3. **A known engine difference** in that column's expression:
   - Rounding and decimal scale (`its values differ` but sums are close).
   - Time zones: date functions over zoned timestamps (Lake Compute's zone
     is UTC).
   - Division: Snowflake's `/` returns a decimal; check integer division.
   - String comparison, collation and case.
   - The order of rows where a window function has ties in its `order by`.
4. **Types.** A `type ... before, ... now` difference: the switched model
   builds a column of another type. Cast it to the type Snowflake built, so
   readers that stay on Snowflake don't change.

## When it can't be fixed now

Revert the one model's switch, and tell the user why:

```bash
git checkout -- <the model's file>
```

It goes back to Snowflake. Its readers that moved with it must be reverted
too, or they will read a table that isn't built on Lake Compute anymore. Run
`dbt init lakecompute --json --quiet --dry-run --select <them>` to see what the
check says now.

## Don't Do These Things

- Don't take a new baseline after the switch to make a difference go away.
- Don't call a migration validated on `not_rebuilt`: nothing was compared.
- Don't edit the baseline file.
