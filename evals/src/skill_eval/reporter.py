"""Report generation for skill evaluation."""

from pathlib import Path

from skill_eval.grader import load_grades


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

    skill_set_stats: dict[str, dict] = {}
    for scenario_name, skill_sets in results.items():
        for skill_set_name, data in skill_sets.items():
            if skill_set_name not in skill_set_stats:
                skill_set_stats[skill_set_name] = {
                    "passed": 0,
                    "total": 0,
                    "scores": [],
                    "tool_usage": {"appropriate": 0, "partial": 0, "inappropriate": 0},
                }

            skill_set_stats[skill_set_name]["total"] += 1
            if data.get("success"):
                skill_set_stats[skill_set_name]["passed"] += 1
            if data.get("score") is not None:
                skill_set_stats[skill_set_name]["scores"].append(data["score"])
            tool_usage = data.get("tool_usage", "").lower()
            if tool_usage in skill_set_stats[skill_set_name]["tool_usage"]:
                skill_set_stats[skill_set_name]["tool_usage"][tool_usage] += 1

    lines.append("| Skill Set | Passed | Avg Score | Tool Usage |")
    lines.append("|-----------|--------|-----------|------------|")

    for skill_set_name, stats in sorted(skill_set_stats.items()):
        passed = stats["passed"]
        total = stats["total"]
        pct = (passed / total * 100) if total > 0 else 0
        scores = stats["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0
        tool_stats = stats["tool_usage"]
        tool_str = f"{tool_stats['appropriate']}✓ {tool_stats['partial']}~ {tool_stats['inappropriate']}✗"
        lines.append(f"| {skill_set_name} | {passed}/{total} ({pct:.0f}%) | {avg_score:.1f} | {tool_str} |")

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

            icon = "✓" if success else "❌" if success is False else "?"
            score_str = f"({score})" if score is not None else ""
            tool_str = f" [tools: {tool_usage}]" if tool_usage else ""
            notes_str = f" - {notes}" if notes else ""

            lines.append(f"- **{skill_set_name}**: {icon} {score_str}{tool_str}{notes_str}")
        lines.append("")

    return "\n".join(lines)


def save_report(run_dir: Path, reports_dir: Path) -> Path:
    """Generate and save report to reports directory."""
    report = generate_report(run_dir)
    report_file = reports_dir / f"{run_dir.name}.md"
    report_file.write_text(report)
    return report_file
