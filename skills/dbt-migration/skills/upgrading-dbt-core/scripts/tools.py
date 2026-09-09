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
  collect        Ordered list of issues for (from_version, adapter), written to
                 references/kb_<from_version>_<warehouse>.json. The single source
                 of truth for "which issues, in what order".
  collect-all    Regenerate every bundle (committed; CI diffs them after editing kb/).
  init-results   Write target/dbt_migration_results.json seeded from `collect`,
                 every issue status = "pending" (idempotent: keeps existing statuses).
  set-status     Update one issue's status/files/notes in the results artifact.
  report         Render target/dbt_migration_results.json -> migration_report.md.
  preflight      Git safety gate: not on main/master, working tree clean.
  autofix        Run `dbt-autofix migrate-1x` in the project; return the files it
                 changed (JSON).
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
ISSUES_DIR = SKILL_ROOT / "kb"
# Where `collect` writes its output: one JSON file per (from_version, adapter),
# so the agent reads a single stable artifact instead of a giant stdout blob.
COLLECT_DIR = SKILL_ROOT / "references"
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

# Upper bound for `dbt-autofix migrate-1x`. Deterministic rewriting stops at 1.8:
# every backwards-incompatible change after it is gated behind a behavior-change
# flag, which this skill pins via set-flag rather than rewriting.
AUTOFIX_TO_VERSION = "1.8"

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

# Throwaway profile bodies for the parse gate, one per adapter we install. Values
# are fake; the field *names* are not — dbt validates a profile's required keys
# before it parses anything, so a stub missing one fails the gate for a reason
# that has nothing to do with the project. Keep in step with _ADAPTER_PKG.
_DUMMY_OUTPUTS: dict[str, dict[str, object]] = {
    "postgres": {
        "type": "postgres",
        "host": "localhost",
        "port": 5432,
        "user": "dbt",
        "password": "dbt",
        "dbname": "dbt",
        "schema": "public",
        "threads": 1,
    },
    "snowflake": {
        "type": "snowflake",
        "account": "dummy",
        "user": "dbt",
        "password": "dbt",
        "role": "accountadmin",
        "database": "dbt",
        "warehouse": "dbt",
        "schema": "public",
        "threads": 1,
    },
    "redshift": {
        "type": "redshift",
        "host": "localhost",
        "port": 5439,
        "user": "dbt",
        "password": "dbt",
        "dbname": "dbt",
        "schema": "public",
        "threads": 1,
    },
    "bigquery": {
        # `oauth` rather than service-account: it needs no keyfile on disk, which
        # a synthetic profile has no way to produce.
        "type": "bigquery",
        "method": "oauth",
        "project": "dbt",
        "dataset": "dbt",
        "threads": 1,
    },
    "databricks": {
        "type": "databricks",
        "host": "localhost",
        "http_path": "/sql/1.0/warehouses/dummy",
        "token": "dbt",
        "schema": "default",
        "threads": 1,
    },
    "spark": {
        "type": "spark",
        "method": "thrift",
        "host": "localhost",
        "port": 10000,
        "schema": "default",
        "threads": 1,
    },
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

# Statuses meaning "this issue was present and something was done about it". These
# are the ones re-detection must never overwrite with `skipped-not-present`; see
# cmd_set_status.
RESOLVED_STATUSES = {"fixed", "applied", "handled-by-autofix", "flag-set"}


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


def _warehouse_slug(adapter: str | None) -> str:
    wh = (adapter or "").strip().lower()
    return "core" if wh in ("", "none", "core") else wh


def collect_path(from_version: str, adapter: str | None) -> Path:
    """references/kb_<from_version>_<warehouse>.json, versions dotless to match
    the kb file naming (1.7 -> 1_7)."""
    return COLLECT_DIR / f"kb_{from_version.replace('.', '_')}_{_warehouse_slug(adapter)}.json"


def _write_collected(from_version: str, adapter: str | None) -> tuple[Path, int]:
    """Write one bundle. Deliberately contains no timestamp: these files are
    committed, and CI regenerates them and diffs, so the output must depend only
    on the kb corpus — not on when it ran."""
    issues = load_collected(from_version, adapter)
    out = collect_path(from_version, adapter)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "from_version": from_version,
        "warehouse": _warehouse_slug(adapter),
        "target_version": TARGET_VERSION,
        "count": len(issues),
        "issues": issues,
    }, indent=2) + "\n")
    return out, len(issues)


def cmd_collect(args) -> int:
    out, n = _write_collected(args.from_version, args.adapter)
    if args.ids_only:
        for i in load_collected(args.from_version, args.adapter):
            print(i["issue_id"])
    print(f"collected {n} issues -> {out}")
    return 0


def kb_from_versions() -> list[str]:
    """Every from_version the corpus actually uses, oldest first."""
    seen = {str(yaml.safe_load(f.read_text())["from_version"])
            for f in ISSUES_DIR.glob("*/*.yaml") if not f.name.startswith("_")}
    return sorted(seen, key=_vkey)


def kb_warehouses() -> list[str]:
    """core + every adapter directory in the corpus."""
    return ["core"] + sorted(d.name for d in ISSUES_DIR.iterdir()
                             if d.is_dir() and d.name != "core")


def cmd_collect_all(args) -> int:
    """Regenerate every (from_version, warehouse) bundle. Run this after editing
    the kb; CI reruns it and fails if the committed bundles drift."""
    written = []
    for v in kb_from_versions():
        for wh in kb_warehouses():
            out, n = _write_collected(v, wh)
            written.append((out, n))
    if args.prune:
        keep = {p for p, _ in written}
        for stale in sorted(COLLECT_DIR.glob("kb_*.json")):
            if stale not in keep:
                stale.unlink()
                print(f"removed stale {stale.name}")
    for out, n in written:
        print(f"{out.name}: {n} issues")
    print(f"wrote {len(written)} bundles -> {COLLECT_DIR}")
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
    # A resolved issue cannot become "not present". Re-detection (Step 8) exists
    # to confirm that fixes hold, and a fix that worked is *supposed* to stop
    # detecting — so re-applying Step 3's "not present -> skipped-not-present"
    # mapping there silently erases the work: the record loses its files, and the
    # report goes on to say "No changes were required" over a real edit.
    # Refused here rather than left to the agent to notice, because by the time
    # it is visible the evidence of the fix is already gone.
    current = rec.get("status", "pending")
    if args.status == "skipped-not-present" and current in RESOLVED_STATUSES:
        print(
            f"refusing {args.issue_id}: {current} -> skipped-not-present. A resolved issue no "
            "longer detecting is the fix being confirmed, not the issue being absent. Leave the "
            f"status at {current}; if the fix genuinely did not hold, set 'detected' or 'failed'.",
            file=sys.stderr,
        )
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
    #
    # `migrate-1x`, not `deprecations`: this skill replays 1.x -> 1.x version
    # boundaries, which is exactly that subcommand's job ("no Fusion/v1.10
    # deprecation fixes"). --from is the project's actual starting version, not
    # the tool's 1.3 default, so autofix applies the same hops the bundle covers
    # -- an out-of-range rule would change files that map onto no collected
    # issue. --to stays at 1.8 because everything after it is behavior-flag
    # gated and pinned by set-flag, never rewritten.
    # --project-dir explicitly: migrate-1x's default is the cwd captured when its
    # module is imported, which happens to be right here only because cwd=project
    # below. Say it outright rather than depend on that.
    cmd = ["uvx", "--python", "3.11", "--from", AUTOFIX_SPEC, "dbt-autofix",
           "migrate-1x", "--project-dir", str(project),
           "--from", str(args.from_version), "--to", AUTOFIX_TO_VERSION]
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


def _dummy_profile(profile_name: str, adapter: str | None) -> str:
    """A throwaway profile for the parse gate, typed to match `adapter`.

    `dbt parse` never opens a connection, so the credentials are deliberately
    fake. The **`type`** is not: dbt resolves it against the adapter installed in
    the venv, and `_resolve_dbt` installs `dbt-<adapter>`. A postgres stub in a
    Snowflake project therefore fails before a single project file is read, which
    reads like a project problem and is not one.

    Fake beats real here. Asking the customer for credentials to run a command
    that never connects buys nothing, and a real profile risks parse-time
    introspection reaching an actual warehouse.
    """
    key = (adapter or "").strip().lower()
    if key in ("", "none", "core"):
        key = "postgres"
    output = _DUMMY_OUTPUTS.get(key)
    if output is None:
        # An adapter we have no stub for. `type` still has to name it, because
        # that is what must match the installed adapter — falling back to
        # postgres would be guaranteed wrong rather than possibly incomplete.
        # Any missing required field surfaces as a profile error naming it.
        output = {"type": key, "schema": "public", "threads": 1}
    return yaml.safe_dump(
        {profile_name: {"target": "dev", "outputs": {"dev": dict(output)}}},
        sort_keys=False,
    )


def _ensure_profiles_dir(project: Path, stack, adapter: str | None = None) -> str:
    """Return a --profiles-dir. Prefer an env/project profiles.yml; otherwise
    synthesize a dummy profile matching the project's `profile:` name and the
    adapter its venv was built for (see {@link _dummy_profile})."""
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
    (tmp / "profiles.yml").write_text(_dummy_profile(profile_name, adapter))
    return str(tmp)


def cmd_parse(args) -> int:
    import contextlib
    project = Path(args.project_dir).resolve()
    dbt_bin = _resolve_dbt(args.adapter if args.adapter != "none" else None, build=not args.no_build)
    if not dbt_bin:
        print(json.dumps({"ok": None, "reason": f"no dbt-core {TARGET_VERSION} available (set DBT_TARGET_VENV or install uv)"}))
        return 2
    with contextlib.ExitStack() as stack:
        # Same adapter the venv was built with, above: the stub's `type` has to
        # match the adapter that is actually installed.
        profiles_dir = _ensure_profiles_dir(
            project, stack, args.adapter if args.adapter != "none" else None
        )
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

    c = sub.add_parser(
        "collect",
        help="write references/kb_<from_version>_<warehouse>.json for the applicable issues")
    c.add_argument("--from-version", required=True)
    c.add_argument("--adapter", default=None,
                   help="warehouse/adapter (snowflake, redshift, ...); omit or 'none' for core-only")
    c.add_argument("--ids-only", action="store_true",
                   help="also print the collected issue ids to stdout")
    c.set_defaults(func=cmd_collect)

    ca = sub.add_parser(
        "collect-all",
        help="regenerate every references/kb_<version>_<warehouse>.json bundle")
    ca.add_argument("--prune", action="store_true",
                    help="delete kb_*.json bundles no longer produced by the corpus")
    ca.set_defaults(func=cmd_collect_all)

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

    af = sub.add_parser("autofix",
                        help="run `dbt-autofix migrate-1x` over the project; report the files it changed")
    af.add_argument("--project-dir", required=True)
    af.add_argument("--from-version", required=True,
                    help="the project's starting minor (1.3-1.7); passed to migrate-1x --from so "
                         "autofix replays the same hops the issue bundle covers")
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
