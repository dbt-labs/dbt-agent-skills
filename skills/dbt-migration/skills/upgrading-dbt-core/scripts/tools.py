#!/usr/bin/env python3
"""Deterministic helpers for the upgrading-dbt-core skill.

The agent should NOT hand-roll issue selection, filtering, ordering, results
bookkeeping, or report rendering — those are mechanical and must be identical on
every run. This CLI does them. The agent only performs the genuinely agentic
work (detection, fixing, HITL confirmation).

Run with PyYAML available, e.g.:

    uv run --with pyyaml python tools.py collect --from-version 1.7 --adapter snowflake
    uv run --with pyyaml python tools.py preflight --project-dir .
    uv run --with pyyaml python tools.py init-results --from-version 1.7 --adapter snowflake --project-dir .
    uv run --with pyyaml python tools.py set-status --project-dir . --issue-id 1_7_003 \
        --status fixed --files models/marts/customers.sql --note "renamed + rewrote ref"
    uv run --with pyyaml python tools.py report --project-dir .

Commands:
  collect        Ordered list of issues for (from_version, adapter) as JSON. The
                 single source of truth for "which issues, in what order".
  init-results   Write target/dbt_migration_results.json seeded from `collect`,
                 every issue status = "pending" (idempotent: keeps existing statuses).
  set-status     Update one issue's status/files/notes in the results artifact.
  report         Render target/dbt_migration_results.json -> migration_report.md.
  preflight      Git safety gate: not on main/master, working tree clean.
  autofix        Run dbt-autofix in the project; return the files it changed (JSON).
  parse          Run `dbt parse` on a throwaway target-version dbt-core; return {ok, output}.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML required: run via `uv run --with pyyaml python tools.py ...`") from exc

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
ISSUES_DIR = SKILL_ROOT / "references"
RESULTS_REL = Path("target") / "dbt_migration_results.json"
REPORT_REL = Path("migration_report.md")
# Coarse, human-facing progress for whoever is watching the run (the VS Code
# extension renders it as a stepper). Distinct from RESULTS_REL, which is
# per-issue bookkeeping: this is one row per phase of the procedure, and it is
# the ONLY file written for display. Rewritten atomically on every update so a
# reader never sees a half-written file.
STATUS_REL = Path("target") / "dbt_migration_status.json"
STATUS_VERSION = 1

# The phases of the mandatory execution order in SKILL.md, in order. Fixed and
# closed: a watcher renders these rows before the agent has reported anything,
# so the list cannot depend on what the run discovers.
MIGRATION_STEPS: list[tuple[str, str]] = [
    ("preflight", "Git preflight"),
    ("collect", "Collect applicable issues"),
    ("read-project", "Read the project"),
    ("detect", "Detection sweep"),
    ("autofix", "Run dbt-autofix"),
    ("agentic-fixes", "Apply agentic fixes"),
    ("human-fixes", "Confirm human-in-the-loop fixes"),
    ("parse", "Validate with dbt parse"),
    ("re-detect", "Re-run detection"),
    ("report", "Write the report"),
]
# `waiting_input` is distinct from `in_progress`: the agent has stopped and cannot
# continue until the customer answers in the chat. Rendered with its own icon, because
# a spinner would tell them to keep waiting when they are the ones being waited on.
STATUS_VALUES = {"pending", "in_progress", "waiting_input", "complete", "failed"}

AUTOFIX_SPEC = "git+https://github.com/dbt-labs/dbt-autofix.git"

# The core version every project is migrated to. Projects are no longer taken one
# minor bump at a time — they go all the way to this version, so the parse gate
# runs this version too.
TARGET_VERSION = os.environ.get("DBT_TARGET_VERSION", "1.12")

_DBT_VENV = Path(os.environ.get(
    "DBT_TARGET_VENV",
    Path.home() / ".cache" / "dbt_migration" / ("dbt" + TARGET_VERSION.replace(".", "")),
))
# Adapter packages are deliberately UNPINNED: post-1.8 the adapters were split
# out of core's release train and no longer share its minor version, so
# `dbt-snowflake~=1.12.0` may not exist. Pin core, let the resolver pick a
# compatible adapter.
_ADAPTER_PKG = {
    "snowflake": "dbt-snowflake",
    "redshift": "dbt-redshift",
    "bigquery": "dbt-bigquery",
    "databricks": "dbt-databricks",
    "spark": "dbt-spark",
}

VALID_STATUSES = {
    "pending", "detected", "handled-by-autofix", "fixed", "applied",
    "manual-required", "advisory", "skipped-not-present", "failed",
    "flag-set",
}
# `pending` = not yet looked at; `detected` = confirmed present in the project but
# not yet resolved. Neither is an outcome — a run that ends with either is
# incomplete, and the report says so.
TERMINAL_STATUSES = VALID_STATUSES - {"pending", "detected"}


def _vkey(v: str) -> tuple[int, int]:
    a, b = v.split(".")
    return (int(a), int(b))


def load_collected(from_version: str, adapter: str | None) -> list[dict]:
    """core/* + <adapter>/*, filtered to from_version >= start, sorted by sort_order."""
    dirs = [ISSUES_DIR / "core"]
    if adapter and adapter not in ("none", "core"):
        dirs.append(ISSUES_DIR / adapter)
    start = _vkey(from_version)
    issues: list[dict] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.yaml"):
            if f.name.startswith("_"):
                continue
            data = yaml.safe_load(f.read_text())
            if _vkey(str(data["from_version"])) >= start:
                data["_path"] = str(f.relative_to(SKILL_ROOT))
                issues.append(data)
    issues.sort(key=lambda d: d["sort_order"])
    return issues


def _results_path(project_dir: Path) -> Path:
    return project_dir / RESULTS_REL


def _load_results(project_dir: Path) -> dict:
    p = _results_path(project_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def _write_results(project_dir: Path, data: dict) -> None:
    p = _results_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")


def _status_path(project_dir: Path) -> Path:
    return project_dir / STATUS_REL


def _write_status(project_dir: Path, data: dict) -> None:
    """Atomic write: a watcher polls this file, so it must never observe a partial one."""
    p = _status_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, p)


def _load_status(project_dir: Path) -> dict:
    p = _status_path(project_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def cmd_status_init(args) -> int:
    project = Path(args.project_dir).resolve()
    prior = {s["id"]: s for s in _load_status(project).get("steps", [])}
    steps = []
    for sid, label in MIGRATION_STEPS:
        # Preserve anything already reported so a resumed run doesn't rewind the
        # display to all-pending.
        old = prior.get(sid, {})
        steps.append({
            "id": sid,
            "label": label,
            "status": old.get("status", "pending"),
            "note": old.get("note", ""),
        })
    _write_status(project, {"version": STATUS_VERSION, "steps": steps})
    print(f"initialized {len(steps)} steps -> {_status_path(project)}")
    return 0


def cmd_status_set(args) -> int:
    project = Path(args.project_dir).resolve()
    if args.status not in STATUS_VALUES:
        print(f"invalid status {args.status!r}; valid: {sorted(STATUS_VALUES)}", file=sys.stderr)
        return 2
    data = _load_status(project)
    if not data.get("steps"):
        print(f"no status artifact yet; run `status-init` first", file=sys.stderr)
        return 2
    for step in data["steps"]:
        if step["id"] == args.step:
            step["status"] = args.status
            if args.note is not None:
                step["note"] = args.note
            _write_status(project, data)
            print(f"{args.step} -> {args.status}")
            return 0
    print(f"unknown step {args.step!r}; valid: {[s for s, _ in MIGRATION_STEPS]}", file=sys.stderr)
    return 2


def cmd_collect(args) -> int:
    issues = load_collected(args.from_version, args.adapter)
    if args.ids_only:
        for i in issues:
            print(i["issue_id"])
    else:
        print(json.dumps(issues, indent=2))
    return 0


def cmd_init_results(args) -> int:
    project = Path(args.project_dir).resolve()
    issues = load_collected(args.from_version, args.adapter)
    existing = _load_results(project)
    out = {}
    for i in issues:
        iid = i["issue_id"]
        if iid in existing:
            out[iid] = existing[iid]  # preserve prior status (resume/idempotent)
        else:
            out[iid] = {
                "automation_type": i["automation_type"],
                "out_of_repo_risk": i["out_of_repo_risk"],
                "environment_change": i["environment_change"],
                "status": "pending",
                "files_changed": [],
                "notes": "",
            }
    _write_results(project, out)
    print(f"seeded {len(out)} issues -> {_results_path(project)}")
    return 0


def cmd_set_status(args) -> int:
    project = Path(args.project_dir).resolve()
    if args.status not in VALID_STATUSES:
        print(f"invalid status {args.status!r}; valid: {sorted(VALID_STATUSES)}", file=sys.stderr)
        return 2
    data = _load_results(project)
    rec = data.get(args.issue_id)
    if rec is None:
        print(f"issue_id {args.issue_id} not in results (run init-results first)", file=sys.stderr)
        return 2
    rec["status"] = args.status
    if args.files:
        rec["files_changed"] = [f for f in args.files.split(",") if f]
    if args.note is not None:
        rec["notes"] = args.note
    _write_results(project, data)
    print(f"{args.issue_id} -> {args.status}")
    return 0


def cmd_list_issues(args) -> int:
    """Issue ids from the results artifact, optionally filtered by status and/or
    automation_type. Lets each phase of the run drive off the artifact instead of
    the agent hand-tracking which issues are still outstanding."""
    project = Path(args.project_dir).resolve()
    data = _load_results(project)
    if not data:
        print("no results artifact found (run init-results first)", file=sys.stderr)
        return 2
    meta = _load_issue_metadata()
    wanted_status = set(args.status.split(",")) if args.status else None
    wanted_auto = set(args.automation_type.split(",")) if args.automation_type else None

    rows = []
    for iid, rec in data.items():
        auto = rec.get("automation_type") or (meta.get(iid, {}) or {}).get("automation_type")
        if wanted_status and rec.get("status", "pending") not in wanted_status:
            continue
        if wanted_auto and auto not in wanted_auto:
            continue
        rows.append((meta.get(iid, {}).get("sort_order", 0), iid, rec.get("status"), auto))
    rows.sort()

    if args.ids_only:
        for _, iid, _, _ in rows:
            print(iid)
    else:
        print(json.dumps(
            [{"issue_id": i, "status": s, "automation_type": a} for _, i, s, a in rows],
            indent=2))
    return 0


def _load_issue_metadata() -> dict[str, dict]:
    """issue_id -> full issue dict, scanned once across every issues/* dir."""
    out: dict[str, dict] = {}
    for f in ISSUES_DIR.glob("*/*.yaml"):
        if f.name.startswith("_"):
            continue
        data = yaml.safe_load(f.read_text())
        out[data["issue_id"]] = data
    return out


def cmd_report(args) -> int:
    project = Path(args.project_dir).resolve()
    data = _load_results(project)
    if not data:
        print("no results artifact found", file=sys.stderr)
        return 2
    meta = _load_issue_metadata()

    # Bucket into plain-English, user-facing sections rather than internal
    # status/issue-id jargon.
    changed: list[str] = []       # fixed / applied / handled-by-autofix
    pinned: list[str] = []        # flag-set (behavior preserved, not fixed)
    needs_review: list[str] = []  # manual-required / advisory / failed
    not_applicable = 0            # skipped-not-present / pending

    for iid, rec in sorted(data.items()):
        status = rec.get("status", "pending")
        info = meta.get(iid, {})
        change = info.get("change", iid)
        impact = info.get("impact", "")
        files = rec.get("files_changed", [])
        note = rec.get("notes", "")

        if status in ("fixed", "applied", "handled-by-autofix"):
            filepart = f" (updated {', '.join(files)})" if files else ""
            changed.append(f"- {change}{filepart}")
        elif status == "flag-set":
            flag = ((info.get("behavior_flag") or {}).get("name")) or "flag"
            pinned.append(f"- {change} — pinned `{flag}` in dbt_project.yml")
        elif status in ("manual-required", "advisory", "failed"):
            detail = note or impact
            suffix = f" — {detail}" if detail else ""
            needs_review.append(f"- {change}{suffix}")
        elif status == "detected":
            # Present in the project and never resolved — surface it loudly
            # rather than letting it hide in the "did not apply" tail.
            detail = note or impact
            suffix = f" — {detail}" if detail else ""
            needs_review.append(f"- NOT RESOLVED: {change}{suffix}")
        else:  # skipped-not-present, pending
            not_applicable += 1

    lines = ["# Migration summary", ""]
    lines.append(
        f"This project was migrated to dbt {TARGET_VERSION}. Below is a summary of what changed "
        "and what still needs your attention."
    )
    lines.append("")

    lines.append("## Changes made")
    lines.append("")
    if changed:
        lines.extend(changed)
    else:
        lines.append("- No changes were required.")
    lines.append("")

    if pinned:
        lines.append("## Behavior preserved via flags")
        lines.append("")
        lines.append(
            f"dbt {TARGET_VERSION} changes these behaviors by default. Rather than rewriting your "
            "project, the gating flags were set explicitly so your project keeps its current "
            "behavior. Remove a flag when you're ready to adopt the new behavior:"
        )
        lines.append("")
        lines.extend(pinned)
        lines.append("")

    lines.append("## Needs your review")
    lines.append("")
    if needs_review:
        lines.extend(needs_review)
    else:
        lines.append("- Nothing outstanding.")
    lines.append("")

    if not_applicable:
        lines.append(
            f"_{not_applicable} other version-upgrade check(s) were reviewed and did not apply to this project._"
        )
        lines.append("")

    report = project / REPORT_REL
    report.write_text("\n".join(lines))
    print(f"wrote {report}")
    return 0


def cmd_autofix(args) -> int:
    """Run dbt-autofix in the project and report the files it changed.

    dbt-autofix intentionally mutates the repo; the agent maps the returned
    changed files onto the `deterministic` issues. Requires network + uvx.
    """
    project = Path(args.project_dir).resolve()

    def git(*a):
        return subprocess.run(["git", "-C", str(project), *a], capture_output=True, text=True)

    before = git("status", "--porcelain").stdout
    # Pin the interpreter: dbt-autofix's mashumaro dependency crashes on import
    # under Python 3.14 (UnserializableField on Optional[bool]); 3.11 is known-good.
    cmd = ["uvx", "--python", "3.11", "--from", AUTOFIX_SPEC, "dbt-autofix", "deprecations"]
    proc = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True)
    after_names = git("diff", "--name-only").stdout.split()
    untracked = [l[3:] for l in git("status", "--porcelain").stdout.splitlines()
                 if l.startswith("?? ")]
    changed = sorted(set(after_names) | set(untracked))
    out = {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "changed_files": changed,
        "output": (proc.stdout + proc.stderr)[-4000:],
    }
    if before.strip():
        out["warning"] = "working tree was not clean before autofix; changed_files may include pre-existing edits"
    print(json.dumps(out, indent=2))
    return 0 if proc.returncode == 0 else 1


def _resolve_dbt(adapter: str | None, build: bool) -> str | None:
    explicit = os.environ.get("DBT_TARGET_BIN")
    if explicit and Path(explicit).exists():
        return explicit
    dbt = _DBT_VENV / "bin" / "dbt"
    if dbt.exists():
        return str(dbt)
    if not build or shutil.which("uv") is None:
        return None
    _DBT_VENV.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["uv", "venv", str(_DBT_VENV)],
                   check=True, capture_output=True, text=True)
    pkg = _ADAPTER_PKG.get(adapter or "", "dbt-postgres")
    subprocess.run(["uv", "pip", "install", "--python", str(_DBT_VENV / "bin" / "python"),
                    f"dbt-core~={TARGET_VERSION}.0", pkg],
                   check=True, capture_output=True, text=True)
    return str(dbt) if dbt.exists() else None


def _ensure_profiles_dir(project: Path, stack) -> str:
    """Return a --profiles-dir. Prefer an env/project profiles.yml; otherwise
    synthesize a dummy profile matching the project's `profile:` name (parse
    does not connect, so dummy postgres creds are fine)."""
    env_dir = os.environ.get("DBT_PROFILES_DIR")
    if env_dir and (Path(env_dir) / "profiles.yml").exists():
        return env_dir
    if (project / "profiles.yml").exists():
        return str(project)
    profile_name = "default"
    dbt_project = project / "dbt_project.yml"
    if dbt_project.exists():
        cfg = yaml.safe_load(dbt_project.read_text()) or {}
        profile_name = cfg.get("profile", "default")
    tmp = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="dbtmig_prof_")))
    (tmp / "profiles.yml").write_text(
        f"{profile_name}:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: postgres\n"
        "      host: localhost\n"
        "      port: 5432\n"
        "      user: dbt\n"
        "      password: dbt\n"
        "      dbname: dbt\n"
        "      schema: public\n"
        "      threads: 1\n"
    )
    return str(tmp)


def cmd_parse(args) -> int:
    import contextlib
    project = Path(args.project_dir).resolve()
    dbt_bin = _resolve_dbt(args.adapter if args.adapter != "none" else None, build=not args.no_build)
    if not dbt_bin:
        print(json.dumps({"ok": None, "reason": f"no dbt-core {TARGET_VERSION} available (set DBT_TARGET_VENV or install uv)"}))
        return 2
    with contextlib.ExitStack() as stack:
        profiles_dir = _ensure_profiles_dir(project, stack)
        cmd = [dbt_bin, "parse", "--profiles-dir", profiles_dir, "--no-version-check"]
        if args.warn_error:
            cmd.append("--warn-error")
        proc = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True)
    ok = proc.returncode == 0
    print(json.dumps({
        "ok": ok,
        "returncode": proc.returncode,
        "warn_error": bool(args.warn_error),
        "output": (proc.stdout + proc.stderr)[-4000:],
    }, indent=2))
    return 0 if ok else 1


def cmd_preflight(args) -> int:
    project = Path(args.project_dir).resolve()

    def git(*a):
        return subprocess.run(["git", "-C", str(project), *a],
                              capture_output=True, text=True)

    head = git("rev-parse", "--abbrev-ref", "HEAD")
    if head.returncode != 0:
        print(json.dumps({"ok": False, "reason": "not a git repository"}))
        return 2
    branch = head.stdout.strip()
    dirty = bool(git("status", "--porcelain").stdout.strip())
    is_main = branch in ("main", "master")
    ok = not is_main and not dirty
    reason = ""
    if is_main:
        reason = f"on protected branch {branch!r}; create/checkout a migration branch first"
    elif dirty:
        reason = "working tree has uncommitted changes; commit or stash first"
    print(json.dumps({"ok": ok, "branch": branch, "is_main": is_main,
                      "clean": not dirty, "reason": reason}))
    return 0 if ok else 1


def _behavior_flag_for_issue(issue_id: str) -> tuple[str, bool] | None:
    """(flag_name, set_to) for one behavior_flag issue, or None if not one.

    Post-1.8, dbt ships backwards-incompatible changes gated behind a behavior
    flag that defaults to the legacy value for existing projects and flips later.
    We don't fix the underlying behavior — we pin the gate so the project keeps
    its current semantics on the target core.

    Flags are pinned ONLY for issues whose gated behavior the project actually
    exhibits (detected per-issue in the skill's application loop). Pinning every
    flag unconditionally would bury a real signal in a wall of irrelevant config
    in the user's dbt_project.yml.
    """
    meta = _load_issue_metadata().get(issue_id)
    if not meta or meta.get("automation_type") != "behavior_flag":
        return None
    bf = meta.get("behavior_flag") or {}
    name = bf.get("name")
    if not name:
        return None
    return name, bool(bf.get("set_to", False))


def _collect_behavior_flags(from_version: str, adapter) -> list[tuple[str, str, bool]]:
    """(issue_id, flag_name, set_to) for every in-scope behavior_flag issue.
    Used for reporting/inspection only — NOT for blanket pinning."""
    out = []
    for i in load_collected(from_version, adapter):
        if i.get("automation_type") != "behavior_flag":
            continue
        bf = i.get("behavior_flag") or {}
        name = bf.get("name")
        if name:
            out.append((i["issue_id"], name, bool(bf.get("set_to", False))))
    return out


def _yaml_bool(v: bool) -> str:
    return "true" if v else "false"


def _set_flags_in_text(text: str, wanted: dict[str, bool]) -> tuple[str, dict[str, str]]:
    """Insert/update keys under the top-level `flags:` mapping of a
    dbt_project.yml, returning (new_text, {flag: action}).

    Deliberately text-level rather than a yaml.safe_load/dump round-trip: this is
    a user's real project file, and a round-trip would strip every comment and
    reorder every key. We only touch the specific lines we own.
    """
    lines = text.splitlines(keepends=True)
    actions: dict[str, str] = {}

    # Locate a top-level `flags:` block-style key.
    flags_idx = None
    for i, ln in enumerate(lines):
        if re.match(r"^flags:\s*(#.*)?$", ln):
            flags_idx = i
            break

    if flags_idx is None:
        # No flags: block (or an inline `flags: {...}` we won't try to rewrite).
        if re.search(r"^flags:\s*\{", text, re.M):
            raise ValueError(
                "dbt_project.yml uses inline `flags: {...}`; rewrite it as a block "
                "mapping so flags can be set safely without reformatting the file"
            )
        block = ["\n"] if text and not text.endswith("\n") else []
        block.append("\nflags:\n")
        for k, v in wanted.items():
            block.append(f"  {k}: {_yaml_bool(v)}\n")
            actions[k] = "added (new flags: block)"
        return "".join(lines) + "".join(block), actions

    # Determine the extent of the flags block: subsequent indented / blank lines.
    end = flags_idx + 1
    last_content = flags_idx
    while end < len(lines):
        ln = lines[end]
        if ln.strip() == "":
            end += 1
            continue
        if ln[:1] in (" ", "\t"):
            last_content = end
            end += 1
            continue
        break

    indent = "  "
    for j in range(flags_idx + 1, last_content + 1):
        m = re.match(r"^(\s+)\S", lines[j])
        if m:
            indent = m.group(1)
            break

    for k, v in wanted.items():
        want = f"{indent}{k}: {_yaml_bool(v)}\n"
        found = None
        for j in range(flags_idx + 1, last_content + 1):
            if re.match(rf"^\s+{re.escape(k)}\s*:", lines[j]):
                found = j
                break
        if found is None:
            lines.insert(last_content + 1, want)
            last_content += 1
            actions[k] = "added"
        elif lines[found] != want:
            lines[found] = want
            actions[k] = "updated"
        else:
            actions[k] = "already correct"

    return "".join(lines), actions


def cmd_set_flag(args) -> int:
    """Pin ONE behavior-change flag, for an issue the project actually exhibits.

    Called from the per-issue loop only after `context.detection` confirms the
    project relies on the gated behavior. Flags are never pinned speculatively:
    an unrelated flag in dbt_project.yml is noise that hides the ones that matter.
    """
    project = Path(args.project_dir).resolve()
    proj_yml = project / "dbt_project.yml"
    if not proj_yml.exists():
        print(json.dumps({"ok": False, "reason": f"no dbt_project.yml in {project}"}))
        return 2

    found = _behavior_flag_for_issue(args.issue_id)
    if found is None:
        print(json.dumps({
            "ok": False,
            "reason": f"{args.issue_id} is not a behavior_flag issue (or has no behavior_flag.name)",
        }))
        return 2
    name, set_to = found

    try:
        new_text, actions = _set_flags_in_text(proj_yml.read_text(), {name: set_to})
    except ValueError as e:
        print(json.dumps({"ok": False, "reason": str(e)}))
        return 1
    proj_yml.write_text(new_text)

    data = _load_results(project)
    rec = data.get(args.issue_id)
    if rec is not None:
        rec["status"] = "flag-set"
        rec["files_changed"] = ["dbt_project.yml"]
        rec["notes"] = (args.note or
                        f"set flags.{name}: {_yaml_bool(set_to)} to preserve pre-change "
                        f"behavior on dbt {TARGET_VERSION} ({actions.get(name, 'set')})")
        _write_results(project, data)

    print(json.dumps({
        "ok": True,
        "issue_id": args.issue_id,
        "target_version": TARGET_VERSION,
        "file": "dbt_project.yml",
        "flag": name,
        "set_to": _yaml_bool(set_to),
        "action": actions.get(name, "set"),
    }, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic helpers for the upgrading-dbt-core skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--from-version", required=True)
    c.add_argument("--adapter", default=None)
    c.add_argument("--ids-only", action="store_true")
    c.set_defaults(func=cmd_collect)

    ir = sub.add_parser("init-results")
    ir.add_argument("--from-version", required=True)
    ir.add_argument("--adapter", default=None)
    ir.add_argument("--project-dir", required=True)
    ir.set_defaults(func=cmd_init_results)

    ss = sub.add_parser("set-status")
    ss.add_argument("--project-dir", required=True)
    ss.add_argument("--issue-id", required=True)
    ss.add_argument("--status", required=True)
    ss.add_argument("--files", default=None, help="comma-separated repo-relative paths")
    ss.add_argument("--note", default=None)
    ss.set_defaults(func=cmd_set_status)

    si = sub.add_parser("status-init",
                        help="seed the display artifact with every phase pending")
    si.add_argument("--project-dir", required=True)
    si.set_defaults(func=cmd_status_init)

    st = sub.add_parser("status-set", help="report one phase's progress for display")
    st.add_argument("--project-dir", required=True)
    st.add_argument("--step", required=True, choices=[s for s, _ in MIGRATION_STEPS])
    st.add_argument("--status", required=True, choices=sorted(STATUS_VALUES))
    st.add_argument("--note", default=None, help="short line shown under the step")
    st.set_defaults(func=cmd_status_set)

    li = sub.add_parser("list-issues",
                        help="issue ids by status / automation_type, from the results artifact")
    li.add_argument("--project-dir", required=True)
    li.add_argument("--status", default=None, help="comma-separated statuses to include")
    li.add_argument("--automation-type", default=None,
                    help="comma-separated automation types to include")
    li.add_argument("--ids-only", action="store_true")
    li.set_defaults(func=cmd_list_issues)

    rp = sub.add_parser("report")
    rp.add_argument("--project-dir", required=True)
    rp.set_defaults(func=cmd_report)

    pf = sub.add_parser("preflight")
    pf.add_argument("--project-dir", required=True)
    pf.set_defaults(func=cmd_preflight)

    af = sub.add_parser("autofix")
    af.add_argument("--project-dir", required=True)
    af.set_defaults(func=cmd_autofix)

    pa = sub.add_parser("parse")
    pa.add_argument("--project-dir", required=True)
    pa.add_argument("--adapter", default=None)
    pa.add_argument("--warn-error", action="store_true", help="treat deprecation warnings as errors")
    pa.add_argument("--no-build", action="store_true",
                    help=f"do not build a dbt {TARGET_VERSION} venv if missing")
    pa.set_defaults(func=cmd_parse)

    sf = sub.add_parser(
        "set-flag",
        help="pin ONE post-1.8 behavior-change flag (only for a detected issue)")
    sf.add_argument("--project-dir", required=True)
    sf.add_argument("--issue-id", required=True)
    sf.add_argument("--note", default=None)
    sf.set_defaults(func=cmd_set_flag)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
