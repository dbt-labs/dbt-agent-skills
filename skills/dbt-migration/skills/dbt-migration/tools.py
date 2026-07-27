#!/usr/bin/env python3
"""Deterministic helpers for the dbt-migration skill.

The agent should NOT hand-roll issue selection, filtering, ordering, results
bookkeeping, or report rendering — those are mechanical and must be identical on
every run. This CLI does them. The agent only performs the genuinely agentic
work (detection, fixing, HITL confirmation).

Run with PyYAML available, e.g.:

    uv run --with pyyaml python tools.py collect --from-version 1.7 --adapter snowflake
    uv run --with pyyaml python tools.py preflight --project-dir .
    uv run --with pyyaml python tools.py init-results --from-version 1.7 --adapter snowflake --project-dir .
    uv run --with pyyaml python tools.py set-status --project-dir . --issue-id from_1.7_to_1.8_003 \
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
  parse          Run `dbt parse` on a throwaway dbt-core 1.8; return {ok, output}.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML required: run via `uv run --with pyyaml python tools.py ...`") from exc

HERE = Path(__file__).resolve().parent
ISSUES_DIR = HERE / "issues"
RESULTS_REL = Path("target") / "dbt_migration_results.json"
REPORT_REL = Path("migration_report.md")

AUTOFIX_SPEC = "git+https://github.com/dbt-labs/dbt-autofix.git"
_DBT18_VENV = Path(os.environ.get("DBT18_VENV", Path.home() / ".cache" / "dbt_migration" / "dbt18"))
_ADAPTER_PKG = {
    "snowflake": "dbt-snowflake~=1.8.0",
    "redshift": "dbt-redshift~=1.8.0",
    "bigquery": "dbt-bigquery~=1.8.0",
    "databricks": "dbt-databricks~=1.8.0",
    "spark": "dbt-spark~=1.8.0",
}

VALID_STATUSES = {
    "pending", "handled-by-autofix", "fixed", "applied",
    "manual-required", "advisory", "skipped-not-present", "failed",
}
TERMINAL_STATUSES = VALID_STATUSES - {"pending"}


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
                data["_path"] = str(f.relative_to(HERE))
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
        elif status in ("manual-required", "advisory", "failed"):
            detail = note or impact
            suffix = f" — {detail}" if detail else ""
            needs_review.append(f"- {change}{suffix}")
        else:  # skipped-not-present, pending
            not_applicable += 1

    lines = ["# Migration summary", ""]
    lines.append(
        "This project was migrated to dbt 1.8. Below is a summary of what changed "
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
    cmd = ["uvx", "--from", AUTOFIX_SPEC, "dbt-autofix", "deprecations"]
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


def _resolve_dbt18(adapter: str | None, build: bool) -> str | None:
    explicit = os.environ.get("DBT18_BIN")
    if explicit and Path(explicit).exists():
        return explicit
    dbt = _DBT18_VENV / "bin" / "dbt"
    if dbt.exists():
        return str(dbt)
    if not build or shutil.which("uv") is None:
        return None
    _DBT18_VENV.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["uv", "venv", "--python", "3.11", str(_DBT18_VENV)],
                   check=True, capture_output=True, text=True)
    pkg = _ADAPTER_PKG.get(adapter or "", "dbt-postgres~=1.8.0")
    subprocess.run(["uv", "pip", "install", "--python", str(_DBT18_VENV / "bin" / "python"),
                    "dbt-core~=1.8.0", pkg], check=True, capture_output=True, text=True)
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
    dbt_bin = _resolve_dbt18(args.adapter if args.adapter != "none" else None, build=not args.no_build)
    if not dbt_bin:
        print(json.dumps({"ok": None, "reason": "no dbt-core 1.8 available (set DBT18_BIN or install uv)"}))
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


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic helpers for the dbt-migration skill")
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
    pa.add_argument("--no-build", action="store_true", help="do not build a dbt 1.8 venv if missing")
    pa.set_defaults(func=cmd_parse)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
