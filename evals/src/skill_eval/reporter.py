"""Report generation for skill evaluation."""

import html as html_lib
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from skill_eval.grader import load_grades


def _compute_skill_set_stats(results: dict) -> dict[str, dict]:
    """Compute aggregate statistics per skill set."""
    # Flatten nested structure into (skill_set_name, data) pairs
    all_entries = (
        (skill_set_name, data)
        for skill_sets in results.values()
        for skill_set_name, data in skill_sets.items()
    )

    # Use defaultdict to auto-initialize
    stats: dict[str, dict] = defaultdict(lambda: {
        "passed": 0,
        "total": 0,
        "scores": [],
        "tool_usage": Counter(),
        "skill_usage": [],
    })

    for skill_set_name, data in all_entries:
        s = stats[skill_set_name]
        s["total"] += 1
        s["passed"] += bool(data.get("success"))
        if (score := data.get("score")) is not None:
            s["scores"].append(score)
        if tool_usage := (data.get("tool_usage") or "").lower():
            s["tool_usage"][tool_usage] += 1
        if skills_available := data.get("skills_available", []):
            s["skill_usage"].append((len(data.get("skills_invoked", [])), len(skills_available)))

    return dict(stats)


def print_rich_report(run_dir: Path, console: Console | None = None) -> None:
    """Print a rich-formatted report to the terminal."""
    if console is None:
        console = Console()

    grades = load_grades(run_dir)
    if not grades or not grades.get("results"):
        console.print("[red]No grades found. Run `skill-eval grade` first.[/red]")
        return

    results = grades["results"]
    run_id = run_dir.name

    # Header
    console.print()
    console.print(f"[bold blue]Eval Report:[/bold blue] [cyan]{run_id}[/cyan]")
    console.print(f"[dim]Graded: {grades.get('graded_at', 'Not yet')} | Grader: {grades.get('grader', 'unknown')}[/dim]")
    console.print()

    # Summary table
    skill_set_stats = _compute_skill_set_stats(results)

    summary_table = Table(title="Summary", title_style="bold", box=None, padding=(0, 2))
    summary_table.add_column("Skill Set", style="cyan", no_wrap=True)
    summary_table.add_column("Passed", justify="right")
    summary_table.add_column("Avg Score", justify="right")
    summary_table.add_column("Tool Usage", justify="center")
    summary_table.add_column("Skill Usage", justify="right")

    for skill_set_name, stats in sorted(skill_set_stats.items()):
        passed = stats["passed"]
        total = stats["total"]
        pct = (passed / total * 100) if total > 0 else 0
        scores = stats["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Color the pass rate
        if pct == 100:
            passed_str = f"[green]{passed}/{total} ({pct:.0f}%)[/green]"
        elif pct >= 50:
            passed_str = f"[yellow]{passed}/{total} ({pct:.0f}%)[/yellow]"
        else:
            passed_str = f"[red]{passed}/{total} ({pct:.0f}%)[/red]"

        # Color the score (scale is 1-5)
        if avg_score >= 4:
            score_str = f"[green]{avg_score:.1f}/5[/green]"
        elif avg_score >= 3:
            score_str = f"[yellow]{avg_score:.1f}/5[/yellow]"
        else:
            score_str = f"[red]{avg_score:.1f}/5[/red]"

        # Tool usage with colors
        tool_stats = stats["tool_usage"]
        tool_str = f"[green]{tool_stats['appropriate']}✓[/green] [yellow]{tool_stats['partial']}~[/yellow] [red]{tool_stats['inappropriate']}✗[/red]"

        # Skill usage
        skill_usage_data = stats["skill_usage"]
        if skill_usage_data:
            total_invoked = sum(x[0] for x in skill_usage_data)
            total_available = sum(x[1] for x in skill_usage_data)
            skill_pct = (total_invoked / total_available * 100) if total_available else 0
            if skill_pct == 100:
                skill_str = f"[green]{skill_pct:.0f}% ({total_invoked}/{total_available})[/green]"
            elif skill_pct >= 50:
                skill_str = f"[yellow]{skill_pct:.0f}% ({total_invoked}/{total_available})[/yellow]"
            else:
                skill_str = f"[red]{skill_pct:.0f}% ({total_invoked}/{total_available})[/red]"
        else:
            skill_str = "[dim]-[/dim]"

        summary_table.add_row(skill_set_name, passed_str, score_str, tool_str, skill_str)

    console.print(summary_table)
    console.print()

    # Detailed results by scenario
    console.print("[bold]By Scenario[/bold]")
    console.print()

    for scenario_name, skill_sets in sorted(results.items()):
        console.print(f"  [bold cyan]{scenario_name}[/bold cyan]")

        for skill_set_name, data in sorted(skill_sets.items()):
            success = data.get("success")
            score = data.get("score")
            tool_usage = data.get("tool_usage", "")
            notes = data.get("notes", "")
            skills_available = data.get("skills_available", [])
            skills_invoked = data.get("skills_invoked", [])

            # Status icon and color
            if success:
                icon = "[green]✓[/green]"
            elif success is False:
                icon = "[red]✗[/red]"
            else:
                icon = "[yellow]?[/yellow]"

            # Score with color (scale is 1-5)
            if score is not None:
                if score >= 4:
                    score_str = f"[green]({score}/5)[/green]"
                elif score >= 3:
                    score_str = f"[yellow]({score}/5)[/yellow]"
                else:
                    score_str = f"[red]({score}/5)[/red]"
            else:
                score_str = ""

            # Tool usage
            tool_str = f" [dim][tools: {tool_usage}][/dim]" if tool_usage else ""

            # Skill usage
            if skills_available:
                skill_pct = (len(skills_invoked) / len(skills_available) * 100)
                skill_str = f" [dim][skills: {skill_pct:.0f}%][/dim]"
            else:
                skill_str = ""

            console.print(f"    {icon} [bold]{skill_set_name}[/bold] {score_str}{tool_str}{skill_str}")

            # Notes (truncated to 500 chars for terminal)
            if notes:
                truncated = notes[:500] + "..." if len(notes) > 500 else notes
                console.print(f"      [dim]{truncated}[/dim]")

            # Skills detail (extra indentation to distinguish from skill set)
            if skills_available:
                for skill in skills_available:
                    if skill in skills_invoked:
                        console.print(f"          [green]✓[/green] [dim]{skill}[/dim]")
                    else:
                        console.print(f"          [red]✗[/red] [dim]{skill} (not invoked)[/dim]")

        console.print()


def generate_report(run_dir: Path) -> str:
    """Generate a markdown report for a run."""
    grades = load_grades(run_dir)
    if not grades or not grades.get("results"):
        return "# No grades found\n\nRun `skill-eval grade` first."

    results = grades["results"]
    run_id = run_dir.name

    lines = [
        f"# Eval Report: {run_id}",
        "",
        f"Graded: {grades.get('graded_at', 'Not yet')}",
        f"Grader: {grades.get('grader', 'unknown')}",
        "",
        "## Summary",
        "",
    ]

    skill_set_stats = _compute_skill_set_stats(results)

    lines.append("| Skill Set | Passed | Avg Score | Tool Usage | Skill Usage |")
    lines.append("|-----------|--------|-----------|------------|-------------|")

    for skill_set_name, stats in sorted(skill_set_stats.items()):
        passed = stats["passed"]
        total = stats["total"]
        pct = (passed / total * 100) if total > 0 else 0
        scores = stats["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0
        tool_stats = stats["tool_usage"]
        tool_str = f"{tool_stats['appropriate']}✓ {tool_stats['partial']}~ {tool_stats['inappropriate']}✗"
        # Compute skill usage summary
        skill_usage_data = stats["skill_usage"]
        if skill_usage_data:
            total_invoked = sum(x[0] for x in skill_usage_data)
            total_available = sum(x[1] for x in skill_usage_data)
            skill_pct = (total_invoked / total_available * 100) if total_available else 0
            skill_str = f"{skill_pct:.0f}% ({total_invoked}/{total_available})"
        else:
            skill_str = "-"
        lines.append(f"| {skill_set_name} | {passed}/{total} ({pct:.0f}%) | {avg_score:.1f}/5 | {tool_str} | {skill_str} |")

    lines.append("")
    lines.append("## By Scenario")
    lines.append("")

    for scenario_name, skill_sets in sorted(results.items()):
        lines.append(f"### {scenario_name}")
        lines.append("")
        for skill_set_name, data in sorted(skill_sets.items()):
            success = data.get("success")
            score = data.get("score")
            tool_usage = data.get("tool_usage", "")
            notes = data.get("notes", "")
            skills_available = data.get("skills_available", [])
            skills_invoked = data.get("skills_invoked", [])

            icon = "✓" if success else "❌" if success is False else "?"
            score_str = f"({score}/5)" if score is not None else ""
            tool_str = f" [tools: {tool_usage}]" if tool_usage else ""

            # Skill usage string
            if skills_available:
                skill_pct = (len(skills_invoked) / len(skills_available) * 100) if skills_available else 0
                skill_str = f" [skills: {skill_pct:.0f}% ({len(skills_invoked)}/{len(skills_available)})]"
            else:
                skill_str = ""

            notes_str = f" - {notes}" if notes else ""

            lines.append(f"- **{skill_set_name}**: {icon} {score_str}{tool_str}{skill_str}{notes_str}")

            # List individual skills with status
            if skills_available:
                for skill in skills_available:
                    if skill in skills_invoked:
                        lines.append(f"  - ✓ {skill}")
                    else:
                        lines.append(f"  - ✗ {skill} (not invoked)")
        lines.append("")

    return "\n".join(lines)


def save_report(run_dir: Path, reports_dir: Path) -> Path:
    """Generate and save report to reports directory."""
    report = generate_report(run_dir)
    report_file = reports_dir / f"{run_dir.name}.md"
    report_file.write_text(report)
    return report_file


def _format_duration(duration_ms: int | float | None) -> str:
    """Format milliseconds as e.g. '1m 05s' or '3.2s'."""
    if duration_ms is None:
        return "-"
    seconds = duration_ms / 1000
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{int(minutes)}m {seconds:02.0f}s"
    return f"{seconds:.1f}s"


def _format_cost(cost: float | None) -> str:
    """Format a USD cost, e.g. '$0.1426'."""
    return "-" if cost is None else f"${cost:.4f}"


def _format_tokens(n: int | None) -> str:
    """Format a token count with thousands separators."""
    return "-" if n is None else f"{n:,}"


def collect_review_rows(run_dir: Path) -> list[dict]:
    """Gather per (scenario, skill_set) run data for the review index page."""
    grades = load_grades(run_dir).get("results", {})

    rows = []
    for scenario_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        scenario_name = scenario_dir.name
        for skill_set_dir in sorted(p for p in scenario_dir.iterdir() if p.is_dir()):
            skill_set_name = skill_set_dir.name

            metadata_file = skill_set_dir / "metadata.yaml"
            metadata: dict = {}
            if metadata_file.exists():
                loaded = yaml.safe_load(metadata_file.read_text())
                metadata = loaded if isinstance(loaded, dict) else {}

            transcript = skill_set_dir / "transcript" / "index.html"
            output_md = skill_set_dir / "output.md"

            rows.append(
                {
                    "scenario": scenario_name,
                    "skill_set": skill_set_name,
                    "metadata": metadata,
                    "transcript_rel": transcript.relative_to(run_dir).as_posix() if transcript.exists() else None,
                    "output_rel": output_md.relative_to(run_dir).as_posix() if output_md.exists() else None,
                    "grade": grades.get(scenario_name, {}).get(skill_set_name),
                }
            )
    return rows


_REVIEW_CSS = """
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 2rem; color: #1c1e21; background: #fff; }
  h1 { font-size: 1.3rem; margin-bottom: 0.2rem; }
  .subtitle { color: #666; margin-top: 0; margin-bottom: 1.2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  th, td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #e3e5e8; text-align: left; white-space: nowrap; }
  th { position: sticky; top: 0; background: #f5f6f8; cursor: pointer; user-select: none; }
  th:hover { background: #ebedf0; }
  th.sorted::after { content: " \\25BE"; }
  tbody tr:hover { background: #f9fafb; }
  td.right, th.right { text-align: right; }
  td.center, th.center { text-align: center; }
  .ok { color: #16794c; font-weight: bold; }
  .fail { color: #c0392b; font-weight: bold; }
  .unknown { color: #999; }
  a { color: #0b5cff; text-decoration: none; }
  a:hover { text-decoration: underline; }
"""

_REVIEW_SORT_JS = """
  const sortValue = (td) => {
    const nested = td.querySelector("[data-sort]");
    return nested ? nested.dataset.sort : td.innerText;
  };
  document.querySelectorAll("th[data-idx]").forEach((th) => {
    th.addEventListener("click", () => {
      const idx = Number(th.dataset.idx);
      const numeric = th.dataset.numeric === "1";
      const table = th.closest("table");
      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const asc = th.dataset.dir !== "asc";
      rows.sort((a, b) => {
        let x = sortValue(a.children[idx]);
        let y = sortValue(b.children[idx]);
        if (numeric) { x = parseFloat(x) || 0; y = parseFloat(y) || 0; }
        return asc ? (x > y ? 1 : x < y ? -1 : 0) : (x < y ? 1 : x > y ? -1 : 0);
      });
      rows.forEach((row) => tbody.appendChild(row));
      table.querySelectorAll("th").forEach((h) => { h.classList.remove("sorted"); h.dataset.dir = ""; });
      th.classList.add("sorted");
      th.dataset.dir = asc ? "asc" : "desc";
    });
  });
"""


def generate_review_html(run_dir: Path) -> str:
    """Generate a single HTML page indexing every run with links + key metrics.

    Replaces opening one browser tab per transcript: one page, one table,
    sortable by clicking column headers, with links out to each transcript
    and raw output.
    """
    rows = collect_review_rows(run_dir)

    columns = [
        ("Scenario", False),
        ("Skill Set", False),
        ("Model", False),
        ("Result", False),
        ("Score", True),
        ("Duration", True),
        ("Turns", True),
        ("Tool calls", True),
        ("Distinct tools", True),
        ("Subagents", True),
        ("Skills", True),
        ("MCP servers", False),
        ("Cost", True),
        ("Tokens (in/out)", True),
        ("Links", False),
    ]
    header_html = "".join(
        f'<th data-idx="{i}" data-numeric="{"1" if numeric else "0"}">{html_lib.escape(label)}</th>'
        for i, (label, numeric) in enumerate(columns)
    )

    body_rows = []
    for row in rows:
        m = row["metadata"]
        grade = row["grade"]

        success = m.get("success")
        if success:
            status_html = '<span class="ok">&#10003;</span>'
            status_sort = "2"
        elif success is False:
            status_html = '<span class="fail">&#10007;</span>'
            status_sort = "0"
        else:
            status_html = '<span class="unknown">?</span>'
            status_sort = "1"

        score = grade.get("score") if grade else None
        score_html = f"{score}/5" if score is not None else "-"

        skills_available = m.get("skills_available", [])
        skills_invoked = m.get("skills_invoked", [])
        skills_html = f"{len(skills_invoked)}/{len(skills_available)}" if skills_available else "-"
        skills_sort = len(skills_invoked) / len(skills_available) if skills_available else -1

        tools_used = m.get("tools_used", [])
        mcp_servers = m.get("mcp_servers", [])
        mcp_names = (
            ", ".join(s.get("name", "?") if isinstance(s, dict) else str(s) for s in mcp_servers) or "-"
        )

        subagent_count = m.get("subagent_count", 0)
        if m.get("subagents_used"):
            subagent_tools = ", ".join(m.get("subagent_tools_used", []))
            subagent_title = f'title="{html_lib.escape(subagent_tools)} ({m.get("subagent_tool_call_count", 0)} calls)"'
            subagent_html = f'<span {subagent_title}>{subagent_count}</span>'
        else:
            subagent_html = "-"

        links = []
        if row["transcript_rel"]:
            links.append(f'<a href="{html_lib.escape(row["transcript_rel"])}">transcript</a>')
        if row["output_rel"]:
            links.append(f'<a href="{html_lib.escape(row["output_rel"])}">output</a>')
        links_html = " &middot; ".join(links) if links else "-"

        duration_ms = m.get("duration_ms")
        cost = m.get("total_cost_usd")

        cells = [
            html_lib.escape(row["scenario"]),
            html_lib.escape(row["skill_set"]),
            html_lib.escape(m.get("model") or "-"),
            f'<span data-sort="{status_sort}">{status_html}</span>',
            f'<span data-sort="{score if score is not None else -1}">{score_html}</span>',
            f'<span data-sort="{duration_ms or 0}">{_format_duration(duration_ms)}</span>',
            m.get("num_turns") if m.get("num_turns") is not None else "-",
            m.get("tool_call_count", 0),
            len(tools_used),
            f'<span data-sort="{subagent_count}">{subagent_html}</span>',
            f'<span data-sort="{skills_sort}">{skills_html}</span>',
            html_lib.escape(mcp_names),
            f'<span data-sort="{cost or 0}">{_format_cost(cost)}</span>',
            f"{_format_tokens(m.get('input_tokens'))} / {_format_tokens(m.get('output_tokens'))}",
            links_html,
        ]
        classes = ["", "", "", "center", "center", "right", "right", "right", "right", "right", "right", "", "right", "right", ""]
        cells_html = "".join(
            f'<td class="{cls}">{val}</td>' if cls else f"<td>{val}</td>"
            for cls, val in zip(classes, cells)
        )
        body_rows.append(f"<tr>{cells_html}</tr>")

    run_name = html_lib.escape(run_dir.name)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Eval Review: {run_name}</title>
<style>{_REVIEW_CSS}</style>
</head>
<body>
<h1>Eval Review: {run_name}</h1>
<p class="subtitle">{len(rows)} run(s) &middot; click a column header to sort</p>
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>{"".join(body_rows)}</tbody>
</table>
<script>{_REVIEW_SORT_JS}</script>
</body>
</html>
"""


def save_review_html(run_dir: Path) -> Path:
    """Generate and save the review index page inside the run directory."""
    review_file = run_dir / "review.html"
    review_file.write_text(generate_review_html(run_dir))
    return review_file
