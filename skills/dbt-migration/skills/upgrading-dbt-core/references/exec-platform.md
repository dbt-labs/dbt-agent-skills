# Execution profile — dbt platform (Studio)

Mechanics for running `upgrading-dbt-core` inside a Studio develop session. The
rules, the phase order, and when to do each of these live in SKILL.md; this file
only says *how*. If you have a shell, you want `exec-local.md` instead.

## What is different here

**There is no shell.** The skill's `scripts/tools.py` cannot run, and neither can
anything else you might be tempted to shell out to. Every step the script does
locally is done with a Studio tool below.

Three consequences worth stating plainly:

- **`dbt_command` accepts exactly two binaries: `dbt` and `dbt-autofix`.** Nothing
  else is on the allowlist.
- **You write the artifacts yourself** with `edit_file`. No script validates them,
  so the schemas in SKILL.md are the contract — never invent a field, a status
  value, or a phase id.
- **There is no `write_file`.** `edit_file` creates the file when the path does
  not exist, so it is also how you create an artifact for the first time.

Never install anything, and treat `environment_change` issues as advisory edits
only — same rule as local, but here there is not even a mechanism to break it.

## State layout — one file, yours to maintain

All migration state lives in **a single file**, `target/dbt_migration.json`:

```json
{
  "version": 1,
  "updated_at": "2026-08-13T09:15:00+00:00",
  "steps": [
    { "id": "preflight", "label": "Git preflight",
      "status": "complete", "note": "On branch upgrade/dbt-1.12, clean tree" },
    { "id": "detect", "label": "Detection sweep",
      "status": "in_progress", "note": "12 of 41 issues checked" }
  ],
  "issues": {
    "1_7_003": {
      "automation_type": "agentic",
      "out_of_repo_risk": false,
      "environment_change": false,
      "status": "fixed",
      "files_changed": ["models/marts/customers.sql"],
      "notes": "renamed + rewrote ref"
    }
  }
}
```

`steps` and `issues` carry exactly the records SKILL.md's **Migration state**
section defines — same phase ids, same status values, same fields. Only the
packaging differs: locally these are two script-written files, here they are two
keys in one file you write with `edit_file`.

One file, because you are writing it by hand and nothing checks your work.
Two files can disagree — a phase marked `complete` while its issues still read
`pending` — and reconciling them costs edits you would rather spend on the
migration. This file is also what you read at the end to write the report, so
keeping it whole and current is what makes Step 9 possible.

Refresh `updated_at` on every write. Never rewrite the document wholesale from
memory: read it, change the one record you mean to change, write it back.

## Tools you have

| Tool | Use |
|---|---|
| `load_skill_resource_file` | Read this skill's own files — the issue bundle, this profile |
| `read_file`, `list_directory`, `find_files`, `grep` | Read the project; run detection |
| `edit_file` | Every file change, including creating the artifacts |
| `delete_file` | Remove a file a fix retires |
| `git` (`status`, `branches`, `diff`, `checkout`, `commit`, `push`, `pull`, `revert`, `merge`) | Preflight, diffs for approval, undo. **No `stash`** |
| `dbt_command`, `dbt_command_status`, `dbt_command_cancel` | The whole verification gate — `dbt parse`, then `dbt build` / `dbt test` — and the `dbt-autofix` run |
| `request_user_input` | Every question you put to the user |
| `get_job_details` | Read one job by id — its `execute_steps` and pinned `dbt_version`. This is how you build `migration_jobs.json` (`jobs-file`) |
| `list_jobs` | Use with care: it returns every job in the **account**, not this project. Work from the legacy job ids you were given |

**You do not trigger jobs.** `trigger_job_run` is not part of this skill. A job
run executes on the deployment environment's own credentials and its own target
schema, which is very often production — the migration has no business writing
there, and a `schema_override` is a flag you can forget. Verification stays in
this session, on this session's development credentials. See
[`verify-commands`](#verify-commands--the-command-rungs).

`$PROJECT` = the project's root. `$ADAPTER` = the adapter type. `$FROM` = the
starting version. `<id>` = an `issue_id` from the bundle.

The **adapter needs no lookup** — it is already in your system prompt as
`dialect`.

## Operations

### `status-init`
`edit_file` on `target/dbt_migration.json`, creating it with all ten phases
present and `pending`, in execution order, and an empty `issues` map. Use the
exact phase ids and status values from SKILL.md's **Migration state** section.

### `status-set`
`edit_file` the same file, changing that one phase's `status` and `note`, and
refreshing `updated_at`. Change one row at a time — do not rewrite the whole
document from memory, or you will drop state you have already recorded.

### `preflight`
`git status` and `git branches`. If the session is on `main`/`master` or the tree
is dirty, `request_user_input` before going further. Create the migration branch
with `git checkout` and `create_if_missing`.

Studio also refuses commits to protected branches, so this is guarded twice —
but do the check anyway; the point is to tell the user before doing work, not to
be caught later.

### `load-bundle`
```
load_skill_resource_file → references/kb_<FROM>_<ADAPTER>.json
```
e.g. `references/kb_1_5_snowflake.json`. Versions are dotless (`1.5` → `1_5`) and
the adapter is `core` when there is none.

This is the whole corpus for this migration — self-contained, with every issue's
`action`, `automation_type`, and `context.detection` / `context.fixing`. The
`kb/` YAML corpus these are compiled from **does not ship in the package**; do
not try to read it.

### `init-results`
`edit_file` the **same** `target/dbt_migration.json`, filling its `issues` map
with one record per issue in the bundle at `status: "pending"`, copying
`automation_type`, `out_of_repo_risk` and `environment_change` straight from the
bundle.

If records are already there, keep the statuses they carry — that is what makes
a run resumable.

### `set-status`
`edit_file` that same file, updating one issue's `status`, `files_changed`, and
`notes` under `issues`. One record at a time, for the same reason as
`status-set`.

### `list-issues`
`read_file` on `target/dbt_migration.json` and filter the `issues` map yourself.
There is no query tool; the file is small enough to read whole.

### `autofix`
`dbt_command` with:

```
dbt-autofix migrate-1x --from <FROM> --to 1.8
```

then `git diff` to see which files it touched.

The subcommand matters. `migrate-1x` is the 1.x → 1.x pass; `deprecations` is
the Fusion/v1.10 pass and is **not** this migration. `--from` must be the
project's real starting version, not the tool's 1.3 default, so autofix replays
exactly the hops the bundle covers — an out-of-range rule would change files
that map onto no collected issue. `--to` stays at 1.8 because everything after
it is behavior-flag gated and pinned by `set-flag`, never rewritten.

This is the one step that works the same way it does locally, because
`dbt-autofix` is on the `dbt_command` allowlist.

### `set-flag`
`edit_file` on `dbt_project.yml`, adding the flag named in that issue's
`behavior_flag.name` under `flags:` set to `false`.

Add the key if `flags:` already exists rather than replacing the block, and pin
only flags for behaviors detection actually found.

### `parse`
`dbt_command` with `dbt parse`. Poll with `dbt_command_status`.

**This session already runs on the target release track.** The platform moves your
develop session onto it before handing off to you, and verifies that it took effect
rather than assuming it — so this is a real gate against the target, not against the
version you are migrating away from. You do not need to check the running version,
and you must not try to change it.

What the gate is: the *cheap* rung. Run it before `verify-commands`, because it
catches the small mistakes — a bad `ref`, malformed YAML, a config that moved — in
seconds instead of in a `dbt build` that spends warehouse compute to tell you the
same thing. It proves the project **parses**. It cannot prove behaviour; that is
`verify-commands`.

### `jobs-file`

**You create this file here.** No extension ran before you, so unlike the local
profile there is nothing on disk to read — you build it from the legacy job ids you
were given, then record your verdicts in it.

1. For each legacy job id, `get_job_details` → its `execute_steps`.
2. `edit_file` on `migration_jobs.json` at the **project root** (not under
   `target/`), creating it with one entry per job and one step entry per command,
   every step `status: "pending"` and `updated: null`.
3. Then `edit_file` the same file as you work through the issues, setting each step
   to `ok` / `needs_change` / `manual`.

Set `"source": "platform"`. Use the legacy job ids you were given — **not**
`list_jobs`, which is account-wide and would pull in jobs from projects that are
none of this migration's business.

The schema is **fixed and shared with the VS Code extension**, which writes the
same file deterministically on the local path: see
[Job commands](../SKILL.md#job-commands--migration_jobsjson) and match it exactly.
Nothing validates it for you here, so that section is the contract — do not add
fields, rename them, or invent status values.

Write it in **Step 2**, before detection, not when the first job-command issue
turns up. `verify-commands` reads its commands from this file, so it has to exist
whether or not any out-of-repo issue was found.

Writing this file is not permission to change the jobs. `verify-commands` re-runs
their *commands* in this session; nothing in this skill edits a job, and nothing
in this skill runs one.

### `revert`
`git` `revert` with a `files` list. That undoes those uncommitted changes, which
is what `git restore` does locally. There is no `stash`.

### `report`
`read_file` on `target/dbt_migration.json` and `edit_file` to write
`migration_report.md` from its `issues` map, grouped by outcome, then show it in
chat. Locally a script renders this; here you render it yourself, which is the
reason the state file has to have been kept accurate all the way through.

Cover what changed, which behavior flags were pinned and why, anything left
`manual-required` or `failed`, and — for this environment specifically — **every
environment and job the user still has to flip**, listed together. A partial flip
leaves the project split across release tracks.

For job **commands**, give the count and link `migration_jobs.json` rather than
restating them; that file is the actionable list and a prose copy will drift from
it. Flipping a job's version and fixing its commands are two different jobs of
work — say both.

### `ask`
`request_user_input`. Always `status-set` the current phase to `waiting_input`
**before** asking, with a note saying what you asked, and set it back to
`in_progress` the moment they answer.

### `verify-commands` — the command rungs

Platform only. These are the rungs above `parse` in SKILL.md's Step 7: re-run the
customer's **own job commands** here in the session, on the target version, and
see whether they actually work. `dbt parse` cannot catch behavior-only changes —
connector swaps, quoting, timeout defaults, a changed materialization default —
and those are exactly what breaks after a version bump.

Same tool as the parse rung: `dbt_command`, polled with `dbt_command_status`.
There is nothing new to learn here; what changes is *which* commands and *whose*
they are.

**Where it runs — this is the whole safety argument, so do not skip it.** A
develop session is connected to the warehouse through **the signed-in user's own
development credential**, which is per user, per project. The platform never
gives a develop session the deployment environment's credential. That is why this
skill runs the commands here instead of triggering the jobs: a job run executes on
the *deployment* environment's credential and target schema, which is frequently
production.

**But "development credential" does not guarantee "harmless schema."** Nothing
validates what the user put in it — a credential whose schema is `analytics` will
write to `analytics`. A `schema:` in the development environment's extended
attributes overrides it for everyone on the project, and a project whose
`generate_schema_name` macro hardcodes a schema ignores the target entirely.

So **establish the target schema before the first build, and put it in the
question you ask.** `dbt debug` reports it and writes nothing. If it is not
obviously a development schema, or if `generate_schema_name` overrides it, say
exactly what it is and **stop** — do not build, let the parse gate stand alone.
"Your development credential points at `analytics`; I am not going to build into
that" is the correct outcome, not a failure.

Never pass `--target`, `--profile`, or `--profiles-dir` (the tool refuses the
last one anyway), and never a `--vars` override that feeds `generate_schema_name`.
Those are the ways to leave the session's own schema on purpose.

**The loop.** Once, up front: `dbt debug` to establish the target schema, then
`ask` for approval naming that schema and the number of commands. `dbt deps` too,
if the project needs its packages — that is setup, not verification, and it is the
one non-build command you may run.

Then read `migration_jobs.json`. For each job, in file order, for each step:

1. **Skip and note** — do not run — any step that is not a build or a test:
   `dbt deps`, `dbt source freshness`, `dbt docs generate`, `dbt run-operation`,
   `dbt clean`. Also skip any step already marked `needs_change` or `manual`:
   that command is being replaced, so a red result tells you nothing you did not
   already record.
2. `dbt_command` with the step's `original` args, verbatim.
3. Poll with `dbt_command_status`. Green → record it, next step.
4. Red → read the node-level errors in the status output, attribute the failure
   to an issue, go back to Step 5 or 6, then re-run Step 7 **from the parse
   rung**. Record what you changed in the issue's notes.

When every runnable step is green, go on to Step 8.

**Guardrails:**

- **Ask before the first command run**, with `request_user_input`, and set the
  phase to `waiting_input` while you wait. Say what it will cost: how many
  commands, and that `dbt build` materializes the whole project into the named
  schema — name it. Studio will also raise its own approval prompt for
  `dbt_command`, but its "allow for this session" then covers every later
  `dbt build`, so that prompt is not a substitute for describing the whole run
  before the first one.
- **One command at a time.** Do not fan out; `dbt_command` is per-command anyway
  and concurrent builds into one schema will collide.
- **Max 3 trips round the loop**, then stop. Unlike a job trigger there is no
  per-run approval bounding this, so the cap is what bounds it. Say you hit the
  cap rather than quietly stopping.
- **Never on `main`/`master`** — always the migration branch, same as everything
  else in this skill.

**If you cannot run it** — the user declines, the session has no warehouse
connection, the project's schema generation is not safe to build into — that is a
normal outcome. Say so plainly, let the parse gate stand as the verification, and
make sure the report names **every command left unverified** so the user knows
exactly what was and was not proven.
