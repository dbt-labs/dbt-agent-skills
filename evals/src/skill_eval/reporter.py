"""Report generation for skill evaluation."""

from collections import Counter, defaultdict
from pathlib import Path

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
