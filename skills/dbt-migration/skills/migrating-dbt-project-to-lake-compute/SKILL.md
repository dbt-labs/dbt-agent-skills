---
name: migrating-dbt-project-to-lake-compute
description: Use when moving a Snowflake dbt project's models to Lake Compute - assessing which models can run there, what they cost and what blocks the rest - and before running any `dbt init lakecompute` command that writes files (`--switch`), including when asked to switch everything, to include skipped or unverified models, or to read a dry-run switch plan. Drives `dbt init lakecompute` in its JSON mode.
allowed-tools: "Bash(dbt init lakecompute --json --quiet --dry-run*), Bash(DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true dbt init lakecompute --json --quiet --dry-run*), Bash(dbtf init lakecompute --json --quiet --dry-run*), Bash(dbt init lakecompute --help), Bash(dbtf init lakecompute --help), Bash(dbt --version), Read, Grep, Glob"
metadata:
  author: dbt-labs
---

# Migrating a dbt Project to Lake Compute

`dbt init lakecompute` checks a Snowflake dbt project for Lake Compute: which
models can move now, what blocks the others, and what each one costs on
Snowflake. It can also switch the models that can move, and check afterwards
that Lake Compute built the same tables.

**The core rule**: the tool decides what is safe to move. Never set
`adapter='lakecompute'` on a model yourself. Switch models only with
`dbt init lakecompute --switch`, which shows the diff first and edits only
models whose SQL it verified. When the tool reports a blocker it can't fix,
change the model (see
[fixing-lake-compute-blockers](../fixing-lake-compute-blockers/SKILL.md)) and
run the check again.

**The user only talks to you, in plain English.** Run every command
yourself, and never give the user a command to run (no `!` commands). Before a
command that reads Snowflake or writes files, say in one sentence what it does
and get a yes in words; the tool's permission prompt then approves the command
itself. Ask as few questions as you can: batch them, and propose a default the
user can accept with "yes".

**Run the check as one command, on its own**, from the project's directory:
`dbt init lakecompute --json --quiet --dry-run ...`, with no `cd`, pipe, `;`
or `&&`. Only that form is pre-approved. It prints one JSON object, small
with `--summary` or `--select`: read it as it is.

**Never offer `--include-unverified`** in a command until the user has
confirmed it, naming the models, after you explained why each one couldn't
be checked and offered `--snowflake` to check them. A request to "switch
everything" or to include the skipped models doesn't count as that
confirmation.

**Success criteria**:
1. The models the user chose are switched, and the report shows them as on lakecompute.
2. They build on Lake Compute.
3. `--validate` says their tables match the baseline taken before the switch.

## Answering "What Can Move?" (Changing Nothing)

When the user asks what can move, or to assess the project, answer in this
order, from the summary (run
`dbt init lakecompute --json --quiet --dry-run --summary` if you have none):

1. **Version**: "Report schema_version 1." If it isn't 1, say this skill may
   be out of date.
2. **Tiers**: the `counts`, and what each tier means.
3. **Blockers**: a table of `blockers` (already grouped by key, most common
   first), each with its `models` count and its `fix.by` (who fixes it: the
   switch, an SQL edit, a config edit, landing data, or nothing).
4. **Inputs**: `inputs_by_kind`, for example how many sources have to land
   in Iceberg, and the most read of them from `inputs`.
5. **First scope**: the `ready` models to move first (the summary lists them
   costliest first), and the exact command that scopes them:
   `dbt init lakecompute --json --quiet --dry-run --select <models> --switch --convert-views`
   (a dry run: it shows the diff and writes nothing). When nothing is
   ready, say so, and name the work that unblocks the most models: the top
   `blockers` and `inputs_by_kind`.
6. **Sizing**: offer to size the models from Snowflake. It reads Snowflake,
   and the login may open a browser. On a yes, run
   `dbt init lakecompute --snowflake --json --quiet --yes`.

Change no file. Until the user agrees to sizing, run nothing but the dry-run
check.

## Contents

- [Answering "What Can Move?"](#answering-what-can-move-changing-nothing)
- [Additional Resources](#additional-resources)
- [Migration Workflow](#migration-workflow)
- [Don't Do These Things](#dont-do-these-things)
- [Known Limitations](#known-limitations)

## Additional Resources

- [The JSON report](references/json-report.md): its fields, issue keys and fixes
- [Flags and exit codes](references/cli.md): every flag the workflow uses
- [Setting up the profile](references/profile-setup.md): the lakecompute output and the build gates

## Migration Workflow

### Progress Checklist

Copy this checklist to track the migration:

```
Lake Compute migration:
- [ ] Step 1: Preflight: dbt has `init lakecompute`; the project compiles
- [ ] Step 2: Assess the project (check, then optionally size from Snowflake)
- [ ] Step 3: Agree on the scope with the user
- [ ] Step 4: Fix the blockers in scope that the tool can't fix
- [ ] Step 5: Take a baseline of the tables in scope
- [ ] Step 6: Switch (dry run, review, then write)
- [ ] Step 7: Build on Lake Compute
- [ ] Step 8: Validate against the baseline
```

### Step 1: Preflight

Find the dbt v2 command: `dbtf` if it exists, else `dbt` when
`dbt --version` names the Fusion engine. Then confirm the subcommand:

```bash
dbt init lakecompute --help
```

If it isn't there, the user's dbt predates `dbt init lakecompute`. Tell them
to update it (`dbt system update`, or their package manager), then check
again. If the newest dbt still lacks it, the command hasn't shipped to them
yet: say so, and stop.

What a migration needs, and when it's first needed:

- The project compiles on Snowflake (`dbt compile`): from Step 2.
- Inputs in Iceberg: sources with `catalog_name`, in a `catalogs.yml`. Without
  them, the report shows the inputs to change; that's an answer, not a
  failure.
- A Lake Compute account, its token in `DBT_LAKE_COMPUTE_TOKEN`, and a
  `lakecompute` output in the profile (see
  [profile setup](references/profile-setup.md)): from Step 7.
- An external volume or catalog integration on Snowflake, only when a view
  gets an Iceberg table built on Snowflake (see Known Limitations).
- The catalogs linked, when a model staying on Snowflake reads a switched
  one, and for Step 8: a Snowflake catalog integration for Lake Compute's
  catalog, granted to the role dbt runs as. Lake Compute then propagates each
  table it builds to Snowflake, where readers `ref` it as before. See
  [catalog linking](references/profile-setup.md#linking-the-catalogs): from
  Step 7.

Name the ones that are missing up front, so the user isn't surprised at
Step 7.

### Step 2: Assess

Run the check. With `--dry-run` it is offline and read-only: it needs no
warehouse login, and writes nothing whatever else is passed.

```bash
dbt init lakecompute --json --quiet --dry-run --summary
```

`--summary` keeps the report small: grouped blockers and inputs, no
per-model entries. Read it first (see
[the JSON report](references/json-report.md)); read the full report only
with `--select`, for the models in scope. Check `schema_version` first; this
skill reads version 1. Summarize for the user:

- `counts`: models per tier (`ready`, `candidate`, `harder`, `blocked`).
- `answers`: what fits, what moves with no work, the costliest models.
- `autofix.views`: views the switch can handle, each with its remedy and why.
- `blockers` and `inputs_by_kind`: the most common blockers and inputs to
  change, each with its `fix.by` (who can fix it).

Sizing and cost need Snowflake. `--snowflake` first compiles the project on
Snowflake, as `dbt compile` does: SQL the project's Jinja runs while compiling
(`run_query`, `statement` blocks) runs too, and can write; hooks don't. Then it
runs read-only queries (query history, EXPLAIN plans, table sizes). Ask the
user first, and say their login may open a browser. On a yes, run it:

```bash
dbt init lakecompute --snowflake --json --quiet --yes
```

On a large account, 30 days of query history can take many minutes to scan.
If the project has run only for a few days, add `--history-days <n>`.

### Step 3: Agree on the scope

Propose a first scope: models with `tier: ready`, costliest first. Sizing
doesn't rule a model out: a `slower` one runs (about `sizing.slowdown` times
slower); say so, and include it. Let the user choose. Use `--select <selector>` from then on, with the
same selector each time. The tool brings along the parents a selected model
needs moved with it, and the views it needs handled; it never touches models
outside that.

Name each model outside the scope that reads one in it (its `ref`s): it stays
on Snowflake and reads the Lake Compute table through the linked catalogs.
Ask whether they are linked; if not, offer the
[setup](references/profile-setup.md#linking-the-catalogs), or a scope without
those parents.

### Step 4: Fix what the tool can't

For each model in scope with issues, read `issue.fix.by`:

| `fix.by` | What to do |
|---|---|
| `switch` | Nothing now: step 6 does it (views need `--convert-views`) |
| `sql` | Edit the model's SQL as `fix.hint` says, then run the check again |
| `config` | Change the model's config as `fix.hint` says, then run the check again |
| `data` | Tell the user: the input has to land in Iceberg first, outside dbt |
| `unsupported` | It stays on Snowflake; drop it from the scope |

Use [fixing-lake-compute-blockers](../fixing-lake-compute-blockers/SKILL.md)
for the edits. After each edit, run
`dbt init lakecompute --json --quiet --dry-run --select <selector>` again. The model must
come back without that issue before you go on.

### Step 5: Take a baseline

Before switching, after the fixes of Step 4, fingerprint the tables in
scope on Snowflake. It reads Snowflake: say so, and on a yes, run it:

```bash
dbt init lakecompute --json --quiet --select <selector> --baseline --yes
```

It fingerprints only the models that can move at the time, so take it after
the hand fixes.

It keeps the fingerprints in `target/lakecompute/baseline.json`. The tables
must be current: build them on Snowflake first if they are stale.

### Step 6: Switch

Show the plan without writing:

```bash
dbt init lakecompute --json --quiet --dry-run --select <selector> --switch --convert-views
```

Present the plan in this order, with the numbers from `switch.summary` (don't
count the edits yourself):

1. **Models switched**: `summary.switched`, and the ones with SQL rewrites
   (`summary.rewritten`; the edits with `rewritten_calls`).
2. **View remedies**: views inlined (`summary.inlined`), views made tables
   (`summary.tables`), and new Iceberg tables of views (`summary.added`, the
   edits with `created`) with the readers pointed at them
   (`summary.repointed`).
3. **Skipped**: each `switch.skipped` model and its `reason`.
4. **The write command**, without `--include-unverified`, and a question:
   may I run it?

The diffs are in `switch.edits[].diff` (not with `--summary`): show the
ones with rewrites or view remedies. The
[migration reviewer](../../agents/lake-compute-migration-reviewer.md) can check
the plan first. When the user agrees, write it. This is the only step that
edits files, so it isn't pre-approved: only commands that start
`--json --quiet --dry-run` are. With `--json`, `--yes` is required:

```bash
dbt init lakecompute --json --quiet --select <selector> --switch --yes --convert-views
```

Without `--convert-views`, views are left alone and their readers stay.

**Skipped models** (`switch.skipped`): tell the user each one's `reason`.
For one whose SQL couldn't be checked, `--include-unverified` would switch SQL
nobody checked. **A request to switch everything, or to include the skipped
models, is not the confirmation.** First:

1. Say, for each such model, why its SQL couldn't be checked.
2. Offer to check it with the warehouse instead: a model that looks up columns
   or tables while it compiles can be checked by
   `dbt init lakecompute --snowflake --json --quiet --yes --select <it>`,
   which you run on a yes.
3. Add `--include-unverified` only after the user confirms, naming those
   models. Until then, the command you offer doesn't have it.

### Step 7: Build on Lake Compute

The switch prints the build command with the environment variables this dbt
needs, for example:

```bash
DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true dbt build --select <the switched models>
```

Run what it prints, with the user's approval. From here on, put
`DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true` in front of every dbt command
that compiles the project (`build`, `run`, `compile`, `show`, `test`): the
switched models need it (see
[build gates](references/profile-setup.md#build-gates)). A build failure is a migration
finding: report it, and don't retry with other flags. To put a failed model
back, revert its file (`git checkout -- <model file>`) and the readers that
moved with it, and delete any model the switch added (`switch.edits[]` with
`created`): `git checkout` doesn't remove new files.

### Step 8: Validate

Compare the rebuilt tables with the baseline. It reads Snowflake: on a yes,
run it:

```bash
dbt init lakecompute --json --quiet --select <selector> --validate --yes
```

Exit code 1 means a table differs or can't be read. `validation.validated[]` gives each table's
`status`: `matches`, `differs` (with `differences`), `not_rebuilt` (Step 7
hasn't written it back yet), or `missing`. Report each table that differs, and
use [validating-lake-compute-migration](../validating-lake-compute-migration/SKILL.md)
to find out why.

## Don't Do These Things

- Don't add `adapter='lakecompute'` or rewrite SQL for Lake Compute by hand
  without the check confirming it afterwards.
- Don't pass `--include-unverified` on your own.
- Don't give the user commands to run, `!` or otherwise. Run them yourself,
  after a yes for those that read Snowflake or write files.
- Don't run `--snowflake`, `--baseline` or `--validate` without a yes. They
  read the warehouse and may open a browser login.
- Don't ask for a token or password in the conversation. Credentials go in
  environment variables the profile reads (see
  [profile setup](references/profile-setup.md)).
- Don't run plain `dbt init`: it asks for credentials interactively.
- Don't edit models outside the agreed scope.

## Known Limitations

- `--select`, `--exclude` and `--selector` scope the report, sizing and switch only: the tool
  still compiles and checks the whole project. Graph operators select as in dbt (`+model` is the
  model and its parents), so prefer listing the models to move.
- `--validate` compares tables as built. If the inputs changed between the two
  builds, a difference may come from the data, not from Lake Compute.
- `--validate` reads the rebuilt tables on Snowflake, through the linked
  catalogs. Without the link, every table "can't be read": see
  [linking the catalogs](references/profile-setup.md#linking-the-catalogs).
- A view with exposures, or one whose SQL can't run on Lake Compute, gets an
  Iceberg table of it built on Snowflake. Snowflake needs an external volume
  or a catalog integration to write it.
- Lake Compute builds incrementals with `append` or `insert_overwrite` only,
  and doesn't apply `on_schema_change`: see
  [config fixes](../fixing-lake-compute-blockers/references/config.md).
