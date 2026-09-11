#!/usr/bin/env python3
"""Emit a Mermaid job-DAG .mmd file from dbtp (requires DBT_* env vars)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

# Skill directory (parent of scripts/)
_SKILL_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_EXPORT_DIR = _SKILL_DIR / "exports"

SNAPSHOT_SCHEMA_VERSION = 1

STYLE_CLASSES = (
    ("projectA", "#2dd4bf", "#f0fdfa"),
    ("projectB", "#a78bfa", "#f5f3ff"),
    ("projectC", "#fb923c", "#fff7ed"),
    ("projectD", "#38bdf8", "#f0f9ff"),
)

DEFAULT_CROSS_LABEL = "triggers downstream project job"


def run_json(cmd: str) -> dict:
    out = subprocess.check_output(cmd, shell=True, text=True)
    return json.loads(out)


def sanitize_label(s: str) -> str:
    if not s:
        return s
    s = s.replace('"', "").replace("'", "").replace("`", "")
    s = s.replace("#", "").replace("[", "(").replace("]", ")")
    s = re.sub(r"[<>*&]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def paginate_jobs_list(dbtp: str, project_id: int | None) -> list[dict]:
    rows: list[dict] = []
    offset, limit = 0, 100
    while True:
        cmd = f"{dbtp} jobs list -o json --limit {limit} --offset {offset}"
        if project_id is not None:
            cmd += f" --project-id {project_id}"
        page = run_json(cmd)
        rows.extend(page["data"])
        c = page["extra"]["pagination"]["count"]
        t = page["extra"]["pagination"]["total_count"]
        offset += c
        if c == 0 or offset >= t:
            break
    return rows


def paginate_projects_list(dbtp: str) -> list[dict]:
    rows: list[dict] = []
    offset, limit = 0, 100
    while True:
        page = run_json(f"{dbtp} projects list -o json --limit {limit} --offset {offset}")
        rows.extend(page["data"])
        c = page["extra"]["pagination"]["count"]
        t = page["extra"]["pagination"]["total_count"]
        offset += c
        if c == 0 or offset >= t:
            break
    return rows


def projects_get_name(dbtp: str, pid: int, cache: dict[int, str]) -> str:
    if pid not in cache:
        p = run_json(f"{dbtp} projects get --id {pid} -o json")
        cache[pid] = p["data"]["name"]
    return cache[pid]


def jobs_get(dbtp: str, jid: int) -> dict:
    return run_json(f"{dbtp} jobs get --id {jid} -o json")["data"]


def extract_edges_from_job_payloads(
    jobs: dict[int, dict],
) -> list[tuple[int, int, int, int]]:
    """Derive completion-trigger edges from full job payloads (no API calls)."""
    edges: list[tuple[int, int, int, int]] = []
    for jid in sorted(jobs.keys()):
        j = jobs[jid]
        cond = (j.get("job_completion_trigger_condition") or {}).get("condition")
        if cond:
            fj, fp = cond["job_id"], cond["project_id"]
            edges.append((fj, jid, fp, j["project_id"]))
    return edges


def assert_snapshot_covers_edges(jobs: dict[int, dict], edges: list[tuple[int, int, int, int]]) -> None:
    jids = set(jobs.keys())
    for f, t, _fp, _tp in edges:
        if f not in jids:
            print(
                f"[job-dag-export] Snapshot is missing full job payload for id={f} "
                "(upstream edge endpoint). Re-run export from the API.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if t not in jids:
            print(
                f"[job-dag-export] Snapshot is missing full job payload for id={t}. Re-run export from the API.",
                file=sys.stderr,
            )
            raise SystemExit(1)


def extract_edges_from_jobs(
    dbtp: str,
    job_ids: list[int],
    log: Callable[[str], None] | None = None,
    progress_every: int = 50,
    job_payloads: dict[int, dict] | None = None,
) -> list[tuple[int, int, int, int]]:
    edges: list[tuple[int, int, int, int]] = []
    n = len(job_ids)
    if log and n:
        log(f"Fetching full job definitions ({n} jobs) to read completion-trigger edges…")
    for i, jid in enumerate(job_ids, 1):
        j = jobs_get(dbtp, jid)
        if job_payloads is not None:
            job_payloads[jid] = j
        cond = (j.get("job_completion_trigger_condition") or {}).get("condition")
        if cond:
            fj, fp = cond["job_id"], cond["project_id"]
            edges.append((fj, jid, fp, j["project_id"]))
        if (
            log
            and n >= progress_every
            and i % progress_every == 0
            and i < n
        ):
            log(f"  … jobs get {i}/{n}")
    if log and n:
        log(
            f"Completed job definition reads ({n}/{n}); "
            f"found {len(edges)} completion-trigger edge(s)."
        )
    return edges


def ensure_endpoints_materialized(
    dbtp: str,
    all_jobs: dict[int, dict],
    edges: list[tuple[int, int, int, int]],
    project_names: dict[int, str],
    log: Callable[[str], None] | None = None,
    job_payloads: dict[int, dict] | None = None,
) -> None:
    """jobs get any edge endpoint missing from all_jobs (e.g. parent outside original scope)."""
    ids = set(all_jobs.keys())
    missing: set[int] = set()
    for f, t, fp, tp in edges:
        if f not in ids:
            missing.add(f)
        if t not in ids:
            missing.add(t)
    if log and missing:
        log(f"Fetching {len(missing)} job(s) referenced on edges but outside the initial scope…")
    for jid in sorted(missing):
        j = jobs_get(dbtp, jid)
        all_jobs[jid] = {"name": j["name"], "project_id": j["project_id"]}
        if job_payloads is not None:
            job_payloads[jid] = j
        projects_get_name(dbtp, j["project_id"], project_names)
    if log and missing:
        log("Resolved outside-scope edge endpoints.")


def expand_downstream_jobs(
    dbtp: str,
    focus_project_ids: set[int],
    all_jobs: dict[int, dict],
    project_names: dict[int, str],
    log: Callable[[str], None] | None = None,
    job_payloads: dict[int, dict] | None = None,
) -> None:
    """Add jobs in other projects that completion-trigger from any reachable job (transitive).

    Fetches each non-focus job at most once, then propagates reachability in memory.
    """
    reachable: set[int] = {
        jid for jid, info in all_jobs.items() if info["project_id"] in focus_project_ids
    }
    all_project_rows = paginate_projects_list(dbtp)
    other_pids = [r["id"] for r in all_project_rows if r["id"] not in focus_project_ids]
    if log:
        log(
            f"Expand downstream: {len(focus_project_ids)} focus project(s); "
            f"{len(other_pids)} other project(s) to scan for triggered jobs."
        )

    foreign_ids: list[int] = []
    for pid in other_pids:
        for row in paginate_jobs_list(dbtp, pid):
            jid = row["id"]
            if jid not in all_jobs:
                foreign_ids.append(jid)

    if log:
        log(f"Listing non-focus projects: {len(foreign_ids)} job id(s) to inspect (jobs get each)…")

    foreign_payloads: dict[int, dict] = {}
    nf = len(foreign_ids)
    for i, jid in enumerate(foreign_ids, 1):
        foreign_payloads[jid] = jobs_get(dbtp, jid)
        if job_payloads is not None:
            job_payloads[jid] = foreign_payloads[jid]
        if log and nf >= 50 and i % 50 == 0 and i < nf:
            log(f"  … non-focus jobs get {i}/{nf}")

    changed = True
    while changed:
        changed = False
        for jid, j in foreign_payloads.items():
            if jid in all_jobs:
                continue
            cond = (j.get("job_completion_trigger_condition") or {}).get("condition")
            if not cond:
                continue
            if cond["job_id"] not in reachable:
                continue
            all_jobs[jid] = {"name": j["name"], "project_id": j["project_id"]}
            projects_get_name(dbtp, j["project_id"], project_names)
            reachable.add(jid)
            changed = True

    if log:
        log(
            f"Expand downstream finished: {len(all_jobs)} job(s) in scope "
            f"({len(reachable)} reachable from focus projects)."
        )


def apply_connected_only(
    all_jobs: dict[int, dict],
    edges: list[tuple[int, int, int, int]],
    log: Callable[[str], None] | None = None,
) -> None:
    n_jobs_before = len(all_jobs)
    n_edges_before = len(edges)
    endpoints: set[int] = set()
    for f, t, fp, tp in edges:
        endpoints.add(f)
        endpoints.add(t)
    drop = [jid for jid in all_jobs if jid not in endpoints]
    for jid in drop:
        del all_jobs[jid]
    edges[:] = [
        (f, t, fp, tp)
        for f, t, fp, tp in edges
        if f in endpoints and t in endpoints
    ]
    if log:
        log(
            f"Connected-only filter: {n_jobs_before} → {len(all_jobs)} job(s), "
            f"{n_edges_before} → {len(edges)} edge(s)."
        )


def job_display_order(
    pid: int,
    all_jobs: dict[int, dict],
    edges: list[tuple[int, int, int, int]],
) -> list[int]:
    jids = {j for j, info in all_jobs.items() if info["project_id"] == pid}
    endpoints: set[int] = set()
    for f, t, fp, tp in edges:
        endpoints.add(f)
        endpoints.add(t)
    incident = jids & endpoints

    cross_src_set = {
        j
        for j in incident
        if any(f == j and fp == pid and tp != pid for f, t, fp, tp in edges)
    }
    cross_src = sorted(cross_src_set)

    internal_edges = [
        (f, t)
        for f, t, fp, tp in edges
        if fp == tp == pid and f in jids and t in jids and f not in cross_src_set
    ]
    internal_vertices: set[int] = set()
    for f, t in internal_edges:
        internal_vertices.add(f)
        internal_vertices.add(t)

    succ: dict[int, list[int]] = defaultdict(list)
    pred: dict[int, int] = defaultdict(int)
    for f, t in internal_edges:
        succ[f].append(t)
        pred[t] += 1
    for v in internal_vertices:
        pred.setdefault(v, 0)

    ready = sorted([v for v in internal_vertices if pred[v] == 0])
    middle_internal: list[int] = []
    while ready:
        v = ready.pop(0)
        middle_internal.append(v)
        for t in sorted(succ[v]):
            pred[t] -= 1
            if pred[t] == 0:
                ready.append(t)
                ready.sort()
    middle_internal.extend(sorted(internal_vertices - set(middle_internal)))

    placed_mid = set(cross_src) | set(middle_internal)
    other_incident = sorted(incident - placed_mid)
    tail = sorted(jids - incident)
    return cross_src + middle_internal + other_incident + tail


def project_subgraph_order(project_ids: list[int], edges: list[tuple[int, int, int, int]]) -> list[int]:
    proj_edges: set[tuple[int, int]] = set()
    for fj, tj, fp, tp in edges:
        if fp != tp:
            proj_edges.add((fp, tp))
    adj: dict[int, set[int]] = defaultdict(set)
    indeg: dict[int, int] = defaultdict(int)
    for a, b in proj_edges:
        adj[a].add(b)
        indeg[b] += 1
    for p in project_ids:
        indeg.setdefault(p, 0)
    ready = sorted([p for p in project_ids if indeg[p] == 0])
    order: list[int] = []
    while ready:
        u = ready.pop(0)
        order.append(u)
        for v in sorted(adj[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort()
    order.extend(sorted(set(project_ids) - set(order)))
    return order


def render_mermaid(
    renderer: str,
    cross_lbl: str,
    order: list[int],
    all_jobs: dict[int, dict],
    edges: list[tuple[int, int, int, int]],
    project_names: dict[int, str],
) -> str:
    lines: list[str] = []
    lines.append("%% Job completion DAG — paste into https://mermaid.live %%")
    lines.append(
        f'%%{{init: {{"flowchart": {{"defaultRenderer": "{renderer}", '
        f'"htmlLabels": true, "nodeSpacing": 40, "rankSpacing": 25, '
        f'"padding": 12, "useMaxWidth": false}}}}}}%%'
    )
    lines.append("flowchart LR")
    lines.append("  %% Color classes %%")
    for i in range(len(order)):
        name, stroke, fill = STYLE_CLASSES[i % len(STYLE_CLASSES)]
        lines.append(f"  classDef {name} stroke:{stroke},fill:{fill}")

    proj_class = {pid: STYLE_CLASSES[i % len(STYLE_CLASSES)][0] for i, pid in enumerate(order)}

    lines.append("")
    for pid in order:
        title = sanitize_label(f"{project_names.get(pid, str(pid))} | {pid}")
        cls = proj_class[pid]
        lines.append(f"  %% Project: {title} ({cls}) %%")
        lines.append(f'  subgraph proj_{pid}["{title}"]')
        lines.append("    direction TB")
        shown = job_display_order(pid, all_jobs, edges)
        if not shown:
            lines.append("    %% (no jobs in scope) %%")
        for jid in shown:
            info = all_jobs[jid]
            lab = sanitize_label(f'{info["name"]} | {jid}')
            lines.append(f'    job_{jid}["{lab}"]')
        lines.append("  end")
        lines.append("")

    lines.append("  %% Completion-trigger dependencies %%")
    lbl = sanitize_label(cross_lbl).replace('"', "")
    for fj, tj, fp, tp in edges:
        if fp == tp:
            lines.append(f"  job_{fj} --> job_{tj}")
        else:
            lines.append(f'  job_{fj} -. "{lbl}" .-> job_{tj}')

    lines.append("")
    lines.append("  %% Apply styles %%")
    for pid in order:
        cls = proj_class[pid]
        chain = job_display_order(pid, all_jobs, edges)
        ids_list = [f"proj_{pid}"] + [f"job_{j}" for j in chain]
        ids = ",".join(dict.fromkeys(ids_list))
        lines.append(f"  class {ids} {cls}")

    return "\n".join(lines) + "\n"


def write_snapshot(
    path: Path,
    *,
    account_id: str | None,
    account: bool,
    project_ids: list[int],
    expand_downstream: bool,
    project_names: dict[int, str],
    job_payloads: dict[int, dict],
    all_job_ids: set[int],
) -> None:
    """Write full job definitions for offline re-rendering (same stem as .mmd, .json)."""
    jobs_out: dict[str, dict] = {}
    for jid in sorted(all_job_ids):
        if jid not in job_payloads:
            raise RuntimeError(f"Internal error: missing job payload for id={jid}")
        jobs_out[str(jid)] = job_payloads[jid]
    doc: dict = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "account_id": account_id,
        "options": {
            "account": account,
            "project_ids": list(project_ids) if not account else None,
            "expand_downstream": expand_downstream,
        },
        "project_names": {str(k): v for k, v in sorted(project_names.items())},
        "jobs": jobs_out,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_snapshot(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ver = data.get("schema_version")
    if ver != SNAPSHOT_SCHEMA_VERSION:
        print(
            f"[job-dag-export] Unsupported snapshot schema_version {ver!r} "
            f"(expected {SNAPSHOT_SCHEMA_VERSION}).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not data.get("jobs"):
        print("[job-dag-export] Snapshot has no jobs.", file=sys.stderr)
        raise SystemExit(1)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export dbt Cloud job completion DAG to Mermaid (.mmd).",
    )
    ap.add_argument(
        "--account",
        action="store_true",
        help="List jobs across the entire account (omit per-project --project-id).",
    )
    ap.add_argument(
        "--project-id",
        type=int,
        action="append",
        dest="project_ids",
        default=None,
        help="Repeat for each project to include (ignored when --account).",
    )
    ap.add_argument(
        "--connected-only",
        action="store_true",
        help="Keep only jobs that participate in at least one completion-trigger edge.",
    )
    ap.add_argument(
        "--expand-downstream",
        action="store_true",
        help=(
            "With --project-id only: include all jobs in those projects, then add jobs in "
            "other projects that completion-trigger from them (transitive). Not valid with --account."
        ),
    )
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output path. Default: exports/job-dag-export-<timestamp>.mmd under this skill. "
            "If path ends in .mmd, write exactly that file. Else treat as directory."
        ),
    )
    ap.add_argument("--renderer", choices=("dagre", "elk"), default="elk")
    ap.add_argument("--cross-project-label", default=DEFAULT_CROSS_LABEL)
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages on stderr (still prints output path at end).",
    )
    ap.add_argument(
        "--from-snapshot",
        metavar="PATH",
        default=None,
        help=(
            "Load full job payloads from a JSON file written by a previous run (no API calls). "
            "Re-apply --connected-only, --renderer, and --cross-project-label as needed."
        ),
    )
    ap.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Do not write a .json snapshot next to the .mmd file (fetch mode only).",
    )
    args = ap.parse_args()

    def log(msg: str) -> None:
        if not args.quiet:
            print(f"[job-dag-export] {msg}", file=sys.stderr)

    if args.from_snapshot and args.no_snapshot:
        ap.error("--no-snapshot applies only to fetch mode, not with --from-snapshot")

    project_ids = args.project_ids or []
    if args.from_snapshot:
        if args.account or project_ids or args.expand_downstream:
            ap.error(
                "--from-snapshot cannot be combined with --account, --project-id, or --expand-downstream"
            )
    else:
        if args.account:
            if project_ids:
                ap.error("Do not combine --account with --project-id")
        elif not project_ids:
            ap.error("Pass --project-id one or more times, or use --account")

        if args.expand_downstream and args.account:
            ap.error("--expand-downstream requires --project-id (focus project(s)), not --account")

    dbtp = os.environ.get("DBTP_PATH", "dbtp")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    stamped_name = f"job-dag-export-{ts}.mmd"
    if args.output is None:
        out_path = _DEFAULT_EXPORT_DIR / stamped_name
    else:
        p = Path(args.output).expanduser()
        out_path = p if p.suffix.lower() == ".mmd" else p / stamped_name

    if args.from_snapshot:
        snap_in = Path(args.from_snapshot).expanduser()
        if not snap_in.is_file():
            print(f"[job-dag-export] File not found: {snap_in}", file=sys.stderr)
            return 1
        data = load_snapshot(snap_in)
        job_payloads: dict[int, dict] = {
            int(k): v for k, v in (data.get("jobs") or {}).items()
        }
        project_names = {int(k): v for k, v in (data.get("project_names") or {}).items()}
        all_jobs: dict[int, dict] = {
            jid: {"name": j["name"], "project_id": j["project_id"]}
            for jid, j in job_payloads.items()
        }
        edges: list[tuple[int, int, int, int]] = extract_edges_from_job_payloads(job_payloads)
        assert_snapshot_covers_edges(job_payloads, edges)
        bits = [f"from snapshot {snap_in.name}"]
        if args.connected_only:
            bits.append("connected-only")
        log(f"Starting export ({'; '.join(bits)}).")
        log("Rebuilding edges from snapshot payloads (no API calls)…")
        if args.connected_only:
            apply_connected_only(all_jobs, edges, log=log)
        for pid in sorted({info["project_id"] for info in all_jobs.values()}):
            project_names.setdefault(pid, str(pid))
    else:
        project_names = {}
        all_jobs = {}
        edges = []
        focus_project_ids: set[int] = set()
        job_payloads = {}

        bits = []
        if args.account:
            bits.append("account-wide")
        else:
            bits.append(f"project(s) {project_ids}")
        if args.connected_only:
            bits.append("connected-only")
        if args.expand_downstream:
            bits.append("expand-downstream")
        log(f"Starting export ({'; '.join(bits)}).")

        if args.account:
            log("Listing jobs for entire account (paginated jobs list)…")
            rows = paginate_jobs_list(dbtp, None)
            seen: set[int] = set()
            for row in rows:
                jid = row["id"]
                if jid in seen:
                    continue
                seen.add(jid)
                all_jobs[jid] = {
                    "name": row["name"],
                    "project_id": row["project_id"],
                }
            log(
                f"Resolving project names for {len({info['project_id'] for info in all_jobs.values()})} "
                "distinct project id(s)…"
            )
            for pid in {info["project_id"] for info in all_jobs.values()}:
                projects_get_name(dbtp, pid, project_names)
        else:
            focus_project_ids = set(project_ids)
            log(f"Listing jobs for {len(project_ids)} project(s)…")
            for pid in project_ids:
                projects_get_name(dbtp, pid, project_names)
                for row in paginate_jobs_list(dbtp, pid):
                    jid = row["id"]
                    all_jobs[jid] = {
                        "name": row["name"],
                        "project_id": row["project_id"],
                    }

        np = len({info["project_id"] for info in all_jobs.values()})
        log(f"Job list complete: {len(all_jobs)} job(s) across {np} project(s).")

        if args.expand_downstream:
            expand_downstream_jobs(
                dbtp, focus_project_ids, all_jobs, project_names, log=log, job_payloads=job_payloads
            )

        edges = extract_edges_from_jobs(
            dbtp, sorted(all_jobs.keys()), log=log, job_payloads=job_payloads
        )

        ensure_endpoints_materialized(
            dbtp, all_jobs, edges, project_names, log=log, job_payloads=job_payloads
        )

        for jid in all_jobs:
            if jid not in job_payloads:
                raise RuntimeError(f"Internal error: missing full job payload for id={jid}")

        if not args.no_snapshot:
            snap_path = out_path.with_suffix(".json")
            write_snapshot(
                snap_path,
                account_id=os.environ.get("DBT_ACCOUNT_ID"),
                account=args.account,
                project_ids=project_ids,
                expand_downstream=args.expand_downstream,
                project_names=dict(project_names),
                job_payloads=job_payloads,
                all_job_ids=set(all_jobs.keys()),
            )
            log(
                f"Wrote snapshot {snap_path} ({len(all_jobs)} job(s)) — "
                "re-render with --from-snapshot without API calls."
            )

        if args.connected_only:
            apply_connected_only(all_jobs, edges, log=log)
            for pid in {info["project_id"] for info in all_jobs.values()}:
                projects_get_name(dbtp, pid, project_names)

        distinct_pids = sorted({info["project_id"] for info in all_jobs.values()})
        for pid in distinct_pids:
            projects_get_name(dbtp, pid, project_names)

    distinct_pids = sorted({info["project_id"] for info in all_jobs.values()})
    log(
        f"Rendering diagram: {len(all_jobs)} job(s), {len(edges)} edge(s), "
        f"{len(distinct_pids)} subgraph(s)."
    )
    order = project_subgraph_order(distinct_pids, edges)
    out = render_mermaid(
        args.renderer,
        args.cross_project_label,
        order,
        all_jobs,
        edges,
        project_names,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(str(out_path), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
