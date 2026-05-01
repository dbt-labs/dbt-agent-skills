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

# Subgraph + node styling (cycle for 3+ projects). Matches Mermaid Live-friendly palette.
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
    """Remove characters that break quoted labels in Mermaid / mermaid.live."""
    if not s:
        return s
    s = s.replace('"', "").replace("'", "").replace("`", "")
    s = s.replace("#", "").replace("[", "(").replace("]", ")")
    s = re.sub(r"[<>*&]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def job_display_order(
    pid: int,
    all_jobs: dict[int, dict],
    edges: list[tuple[int, int, int, int]],
) -> list[int]:
    """Incident jobs first: cross-project sources, internal completion chain (topo), other incident; then rest by id."""
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

    # Internal edges whose upstream is not already listed as a cross-project source
    # (avoids duplicating nodes like 83771 that both span projects and trigger in-project jobs).
    internal_edges = [
        (f, t)
        for f, t, fp, tp in edges
        if fp == tp == pid
        and f in jids
        and t in jids
        and f not in cross_src_set
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-id",
        type=int,
        action="append",
        dest="project_ids",
        required=True,
        help="Repeat for each dbt Cloud project id to include.",
    )
    ap.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to write .mmd (UTF-8).",
    )
    ap.add_argument(
        "--renderer",
        choices=("dagre", "elk"),
        default="elk",
        help="flowchart defaultRenderer in %%{init}%%.",
    )
    ap.add_argument(
        "--cross-project-label",
        default=DEFAULT_CROSS_LABEL,
        help="Text on dashed edges between projects (Mermaid edge label).",
    )
    args = ap.parse_args()
    dbtp = os.environ.get("DBTP_PATH", "dbtp")

    projects: dict[int, str] = {}
    jobs_by_proj: dict[int, list] = {}
    edges: list[tuple[int, int, int, int]] = []

    for pid in args.project_ids:
        p = run_json(f"{dbtp} projects get --id {pid} -o json")
        projects[pid] = p["data"]["name"]
        jobs_by_proj[pid] = []
        offset, limit = 0, 100
        while True:
            page = run_json(
                f"{dbtp} jobs list --project-id {pid} -o json --limit {limit} --offset {offset}"
            )
            jobs_by_proj[pid].extend(page["data"])
            c = page["extra"]["pagination"]["count"]
            t = page["extra"]["pagination"]["total_count"]
            offset += c
            if c == 0 or offset >= t:
                break

    all_jobs: dict[int, dict] = {}
    for pid, rows in jobs_by_proj.items():
        for r in rows:
            jid = r["id"]
            all_jobs[jid] = {"name": r["name"], "project_id": r["project_id"]}

    for jid in sorted(all_jobs.keys()):
        j = run_json(f"{dbtp} jobs get --id {jid} -o json")["data"]
        cond = (j.get("job_completion_trigger_condition") or {}).get("condition")
        if cond:
            fj, fp = cond["job_id"], cond["project_id"]
            edges.append((fj, jid, fp, j["project_id"]))

    proj_edges: set[tuple[int, int]] = set()
    for fj, tj, fp, tp in edges:
        if fp != tp:
            proj_edges.add((fp, tp))

    adj: dict[int, set[int]] = defaultdict(set)
    indeg: dict[int, int] = defaultdict(int)
    for a, b in proj_edges:
        adj[a].add(b)
        indeg[b] += 1
    projs = list(projects.keys())
    for p in projs:
        indeg.setdefault(p, 0)

    ready = sorted([p for p in projs if indeg[p] == 0])
    order: list[int] = []
    while ready:
        u = ready.pop(0)
        order.append(u)
        for v in sorted(adj[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort()
    order.extend(sorted(set(projs) - set(order)))

    lines: list[str] = []
    lines.append("%% Job completion DAG — paste into https://mermaid.live %%")
    lines.append(
        f'%%{{init: {{"flowchart": {{"defaultRenderer": "{args.renderer}", '
        f'"htmlLabels": true, "nodeSpacing": 40, "rankSpacing": 25, '
        f'"padding": 12, "useMaxWidth": false}}}}}}%%'
    )
    lines.append("flowchart LR")
    lines.append("  %% Color classes %%")
    for i in range(len(order)):
        name, stroke, fill = STYLE_CLASSES[i % len(STYLE_CLASSES)]
        lines.append(f"  classDef {name} stroke:{stroke},fill:{fill}")

    proj_class: dict[int, str] = {}
    for i, pid in enumerate(order):
        proj_class[pid] = STYLE_CLASSES[i % len(STYLE_CLASSES)][0]

    lines.append("")
    for pid in order:
        title = sanitize_label(f"{projects[pid]} | {pid}")
        cls = proj_class[pid]
        lines.append(f"  %% Project: {title} ({cls}) %%")
        lines.append(f'  subgraph proj_{pid}["{title}"]')
        lines.append("    direction TB")
        for jid in job_display_order(pid, all_jobs, edges):
            info = all_jobs[jid]
            lab = sanitize_label(f'{info["name"]} | {jid}')
            lines.append(f'    job_{jid}["{lab}"]')
        lines.append("  end")
        lines.append("")

    lines.append("  %% Completion-trigger dependencies %%")
    cross_lbl = sanitize_label(args.cross_project_label).replace('"', "")
    for fj, tj, fp, tp in edges:
        if fp == tp:
            lines.append(f"  job_{fj} --> job_{tj}")
        else:
            lines.append(
                f'  job_{fj} -. "{cross_lbl}" .-> job_{tj}'
            )

    lines.append("")
    lines.append("  %% Apply styles %%")
    for pid in order:
        cls = proj_class[pid]
        chain = job_display_order(pid, all_jobs, edges)
        ids_list = [f"proj_{pid}"] + [f"job_{j}" for j in chain]
        ids = ",".join(dict.fromkeys(ids_list))
        lines.append(f"  class {ids} {cls}")

    out = "\n".join(lines) + "\n"
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)
    print(args.output, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
