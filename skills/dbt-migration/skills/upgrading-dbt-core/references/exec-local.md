# Execution profile — local / VS Code extension

Mechanics for running `upgrading-dbt-core` where a **shell is available**. The
rules, the phase order, and when to do each of these live in SKILL.md; this file
only says *how*. If you are in dbt platform Studio, you want
`exec-platform.md` instead — nothing here can run there.

## Environment assumptions

- The project directory is a **git-versioned repo**.
- **`uvx` and `python`** are available — used to run `scripts/tools.py`,
  `dbt-autofix`, and a throwaway dbt-core 1.12 for the parse gate.
- **`scripts/tools.py`** sits under this skill's directory and owns all
  deterministic work.

**Resolve `$SKILL_DIR` before your first command**: the absolute path of the
directory holding `SKILL.md` — where this skill was installed, which is not the
project and not necessarily your shell's starting directory. Every command below
is prefixed with:

```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py"
```

Substitute the real path into each command literally. Each command runs in a
fresh shell, so a variable you export in one does not exist in the next, and
neither does a `cd`.

The script does not care where it is run from: it locates `kb/` and
`references/` relative to its own file, and every command takes the project as
`--project-dir`. An absolute script path is all it needs — so there is nothing
here to discover by trial.

`$PROJECT` = the project's root directory. `$ADAPTER` = the adapter type (or
`none`). `$FROM` = the starting version. `<id>` = an `issue_id` from the bundle.

## State layout — two files, script-owned

Migration state lives in **two separate files** here:

| File | Holds | Written by |
|---|---|---|
| `target/dbt_migration_status.json` | Phase state — `{version, updated_at, steps: [...]}` | `status-init` / `status-set` |
| `target/dbt_migration_results.json` | Issue state — a map of `issue_id` → record | `init-results` / `set-status` |

`scripts/tools.py` is the **only** writer of both, and of `migration_report.md`.
Never hand-write any of them, and never hand-edit a behavior flag — call the
operation. The script validates every status value and phase id for you, and
rewrites the status file atomically because a watcher polls it.

This is the one place the two profiles differ in kind rather than in syntax. The
Studio profile has no shell, so it keeps the same state in a **single** file it
writes directly. Do not carry that layout over here, and do not expect a
migration started in one environment to resume in the other.

## Operations

### `status-init`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" status-init --project-dir "$PROJECT"
```

### `status-set`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" status-set --project-dir "$PROJECT" \
  --step <phase-id> --status <status> \
  --note "12 of 41 issues checked"
```
`--step` is one of `preflight`, `collect`, `read-project`, `detect`, `autofix`,
`agentic-fixes`, `human-fixes`, `parse`, `re-detect`, `report`. `--status` is
`pending` / `in_progress` / `waiting_input` / `complete` / `failed`. Fails with
exit 2 if `status-init` has not run yet.

### `preflight`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" preflight --project-dir "$PROJECT"
```
Prints JSON and **exits non-zero when unsafe**. Read `ok`; if false, relay
`reason`.

### `load-bundle`
The bundle is precompiled and shipped, so prefer simply reading it:

```
references/kb_<FROM>_<ADAPTER>.json      e.g. references/kb_1_5_snowflake.json
```

Versions are dotless (`1.5` → `1_5`) and the adapter is `core` when there is
none. If that file is missing — a working copy where CI has not generated the
bundles yet — build it from the local `kb/` corpus:

```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" collect --from-version "$FROM" --adapter "$ADAPTER"
```
That writes the same path and prints it. Then read it. Do not regenerate a bundle
that already exists.

### `init-results`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" init-results \
  --from-version "$FROM" --adapter "$ADAPTER" --project-dir "$PROJECT"
```
Idempotent: preserves the status of any issue already recorded, which is what
makes a run resumable.

### `set-status`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" set-status --project-dir "$PROJECT" \
  --issue-id <id> --status <status> \
  --files models/marts/customers.sql,models/staging/stg_orders.sql \
  --note "renamed + rewrote ref"
```
`--files` is comma-separated and repo-relative. `--note` and `--files` are
optional. Exits 2 on an unknown status, an issue id not in the results artifact,
or an attempt to move a resolved issue (`fixed` / `applied` /
`handled-by-autofix` / `flag-set`) to `skipped-not-present` — see Step 8 in
SKILL.md for why that transition is always a mistake.

### `list-issues`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" list-issues --project-dir "$PROJECT" \
  --status detected --automation-type agentic,deterministic --ids-only
```
`--status` and `--automation-type` both accept comma-separated values.

### `autofix`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" autofix --project-dir "$PROJECT" \
  --from-version "$FROM"
```
Runs **`dbt-autofix migrate-1x --from "$FROM" --to 1.8`** and returns the
`changed_files` it touched, as JSON.

`migrate-1x` is the 1.x → 1.x subcommand — not `deprecations`, which is the
Fusion/v1.10 deprecation pass and is not this migration. `--from` must be the
project's real starting version rather than the tool's 1.3 default, so autofix
replays exactly the hops the bundle covers; an out-of-range rule would change
files that map onto no collected issue. `--to` stays at 1.8 because everything
after it is behavior-flag gated and pinned by `set-flag`, never rewritten.

### `set-flag`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" set-flag --project-dir "$PROJECT" --issue-id <id>
```
Pins the flag named in that issue's `behavior_flag.name` to `false` under
`flags:` in `dbt_project.yml`. Never hand-edit the file to do this.

### `parse`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" parse --project-dir "$PROJECT" \
  --adapter "$ADAPTER" --warn-error
```
Builds a throwaway dbt-core 1.12 virtualenv and a dummy profile as needed, runs
`dbt parse` against it, and returns `{ok, output}`. The 1.12 venv is what makes
this gate mean anything — never substitute the project's own dbt.

**Pass the project's real `$ADAPTER`.** It selects both the adapter installed in
the venv and the `type:` of the synthesized profile, and those two have to agree:
a mismatch fails the gate on profile resolution, before any project file is read,
which reads like a project error and is not one. The credentials in that profile
are fake by design — `dbt parse` never connects, so there is nothing here to ask
the customer for, and a real profile would risk parse-time introspection reaching
an actual warehouse.

### `jobs-file`

`$PROJECT/migration_jobs.json`, **already written by the extension** before the
handoff — it read the jobs from the dbt platform API, so the job ids, names and
commands in it are authoritative. Read it with `Read` and record verdicts with
`Edit`.

```
Read  $PROJECT/migration_jobs.json
Edit  $PROJECT/migration_jobs.json   # set status / updated / issue_id / reason per step
```

**Never regenerate this file here, and never call the platform API for jobs.** You
have no credentials in this environment, and rewriting it would discard the ids the
customer needs to find each job. If the file is absent, the project has no jobs or
the extension could not read them — say so in the report and move on; do not invent
one.

Schema and status vocabulary are in SKILL.md
([Job commands](../SKILL.md#job-commands--migration_jobsjson)). Every step must
leave `pending` before Step 9.

### `revert`
```bash
git -C "$PROJECT" restore <files>
```
Undoes uncommitted changes to those files only.

### `report`
```bash
uv run --with pyyaml python "$SKILL_DIR/scripts/tools.py" report --project-dir "$PROJECT"
```
Renders `target/dbt_migration_results.json` → `migration_report.md`, grouped by
outcome.

### `ask`
Put the question to the user in chat and wait. Always `status-set` the current
phase to `waiting_input` **before** asking, with a note saying what you asked.

## No `verify-jobs` here

SKILL.md describes an optional exit gate after Step 9 — running the customer's
real jobs on the target version. **This profile does not define it.** There is no
job trigger locally; jobs live in dbt platform, and this environment has no
credentials or admin tools to reach them.

So `dbt parse` is the end of verification here. Say that plainly in the report
rather than implying more was proven than actually was: parse means the project
parses on 1.12, not that its jobs still run.
