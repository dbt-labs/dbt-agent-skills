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
| `dbt_command`, `dbt_command_status`, `dbt_command_cancel` | The `dbt parse` gate and the `dbt-autofix` run |
| `request_user_input` | Every question you put to the user |
| `get_job_details` | Read one job by id — its `execute_steps` and pinned `dbt_version`. Also how you build `migration_jobs.json` (`jobs-file`) |
| `list_jobs` | Use with care: it returns every job in the **account**, not this project. Work from the legacy job ids you were given |
| `trigger_job_run`, `get_job_run_details`, `get_job_run_error`, `list_job_run_artifacts` | The optional `verify-jobs` exit gate |

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

The gate is only meaningful against **dbt-core 1.12** — the target version. Treat
the session as running 1.12 for the purposes of this skill.

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

Writing this file is not permission to change the jobs. `verify-jobs` may *run*
them; nothing in this skill edits them.

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

### `verify-jobs` — the optional exit gate

Platform only. This is the `verify-jobs` operation SKILL.md describes after
Step 9: run the customer's **own existing jobs** on the target version and see
whether they actually work. `dbt parse` cannot catch behavior-only changes —
connector swaps, quoting, timeout defaults — and those are exactly what breaks
after a version bump.

Admin tools, all bound to the signed-in user:

| Tool | Use |
|---|---|
| `get_job_details` | Read each legacy job by id — its `execute_steps` and pinned `dbt_version`. Pick targets from the legacy job ids you were given, not from `list_jobs`, which is account-wide |
| `trigger_job_run` | Start one run, with `dbt_version_override` plus `git_branch` and `schema_override` |
| `get_job_run_details` | Poll that run to completion |
| `get_job_run_error` | Read the failure when it fails |
| `list_job_run_artifacts` | Pull artifacts from the run if you need more than the error |

**The loop.** For each job whose effective version is legacy — every one of them,
not a sample:

1. `trigger_job_run` with `dbt_version_override` set to the target version,
   `git_branch` set to the migration branch, and `schema_override` set to a
   **scratch schema**. Never the job's real target schema.
2. Poll with `get_job_run_details`.
3. Green → record it and move to the next job.
4. Red → `get_job_run_error`, attribute the failure to an issue, go back to
   Step 5 or 6, re-run Step 7's parse gate, and only then retry. Record what you
   changed in the issue's notes.

When every legacy job is green, re-issue the report.

**Guardrails — these are the operation, not decoration:**

- **Ask before *every* triggered run**, not just the first, with
  `request_user_input`, and set the phase to `waiting_input` while you wait. Each
  run spends real warehouse compute on the customer's account. Studio's in-session
  approval for `dbt_command` does **not** cover `trigger_job_run` — it is a
  server-side action with no equivalent gate — so this instruction is the only
  thing standing between the user and an unrequested bill.

  Per-run approval is also what bounds the loop: there is no attempt cap here
  precisely because you cannot start another run without being told to. Never
  batch several runs behind one approval.
- **Always a scratch schema**, via `schema_override`. Never write to the schema a
  real job targets.
- **One job at a time.** Do not fan out.
- **Never trigger anything on `main`/`master`** — always the migration branch.

**If you cannot run it** — `dbt_version_override` unavailable on `trigger_job_run`,
or the user lacks run permission, or they decline — that is a normal outcome.
Say so plainly, let the parse gate stand as the verification, and make sure the
report names **every job left unverified** so the user knows exactly what was
and was not proven.
