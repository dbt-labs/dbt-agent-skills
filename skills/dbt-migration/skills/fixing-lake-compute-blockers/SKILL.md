---
name: fixing-lake-compute-blockers
description: Use when `dbt init lakecompute` reports issues on models that are to move to Lake Compute, such as Snowflake-only functions, semi-structured access, date parts, incremental strategies or hooks, and the model's SQL or config has to change before it can switch.
user-invocable: false
allowed-tools: "Bash(dbt init lakecompute --json --quiet --dry-run*), Bash(DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true dbt init lakecompute --json --quiet --dry-run*), Bash(dbtf init lakecompute --json --quiet --dry-run*), Read, Edit, Grep, Glob"
metadata:
  author: dbt-labs
---

# Fixing Lake Compute Blockers

Use this skill from
[migrating-dbt-project-to-lake-compute](../migrating-dbt-project-to-lake-compute/SKILL.md),
step 4. Each issue in the JSON report has `key`, `message` and `fix`
(`fix.by`, `fix.hint`).

**The loop**: one model at a time.
1. Read everything in its way, in the report of
   `dbt init lakecompute --json --quiet --dry-run --select <model>`
   (`models[]`): its `issues`, its `changes` (inputs that must change first,
   such as a source to land in Iceberg), and `sql.state` (`unchecked`: the
   check couldn't see its SQL). Tell the user all of them, even the ones you
   don't fix: else fixing one looks like enough.
2. Make the smallest edit that removes the first issue. If that edit changes
   what the table holds or does (an incremental strategy, a hook, a grant),
   don't make it: explain the trade-off, and ask the user.
3. Check again: `dbt init lakecompute --json --quiet --dry-run --select <model>`,
   as one command on its own (no `cd`, pipe or `&&`: only that form is
   pre-approved). Make the edit with Edit, not a shell command.
4. The issue must be gone, with no new one. Else undo the edit and try
   another fix, or tell the user.

**The rule that keeps the project working**: until the model switches, it
still builds on Snowflake. So:

1. **Leave to the switch what it rewrites.** The tool translates what it can
   deterministically: the calls and colon paths in the model's
   `rewrite.fragments`. `--switch` applies them. Don't edit those by hand.
2. **Use a form both engines accept** for the rest, wherever one exists. The
   references list them, checked on both engines. For example:
   - date parts get quotes: `datediff('day', a, b)`;
   - intervals get quotes: `ts - interval '1 day'`.
3. **Where no shared form exists, write the Lake Compute form yourself**
   (`lateral flatten`, `object_construct`, `listagg ... within group`, array
   indexes). It must land together with the switch, in the same change: until
   then the model builds on Snowflake, which rejects it. Tell the user each
   one you wrote, and why it can't land earlier.
4. **Never say "fixed" before the check says so.** Run
   `dbt init lakecompute --json --quiet --dry-run --select <model>` (it's
   read-only, and pre-approved). If you can't run it, give the user that
   command, and say the fix is unconfirmed.

## By `fix.by`

| `fix.by` | Use |
|---|---|
| `sql` | The references below, by key family |
| `config` | [Config and materialization](references/config.md) |
| `data` | [Inputs](references/inputs.md): tell the user what has to land in Iceberg |
| `switch` | Nothing: `--switch --convert-views` does it |
| `unsupported` | Nothing: it stays on Snowflake. Drop it from the scope |

## By key family (`fix.by: sql`)

| Key | Reference |
|---|---|
| `syntax:semi_structured` | [Semi-structured access](references/semi-structured.md) |
| `syntax:date_part_name`, `type:date_trunc_date`, `function:dateadd`, `function:to_date`, other date functions | [Dates and times](references/dates.md) |
| other `function:*`, `type:*`, `syntax:*` | [Functions and syntax](references/functions.md) |

## Don't Do These Things

- Don't change an incremental model's strategy (`merge` to `append`) without
  the user. It changes what the table holds.
- Don't remove a hook without the user. It may grant access or audit.
- Don't edit a model the user didn't put in scope.
- Don't call a model fixed until the check says so.
- Don't rewrite calls or colon paths the switch already rewrites
  (`rewrite.fragments` in the report): the switch does it, and keeps it
  reviewable.
