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
                skill_set_stats[skill_set_name] = {"passed": 0, "total": 0, "scores": []}

            skill_set_stats[skill_set_name]["total"] += 1
            if data.get("success"):
                skill_set_stats[skill_set_name]["passed"] += 1
            if data.get("score") is not None:
                skill_set_stats[skill_set_name]["scores"].append(data["score"])

    lines.append("| Skill Set | Passed | Avg Score |")
    lines.append("|-----------|--------|-----------|")

    for skill_set_name, stats in sorted(skill_set_stats.items()):
        passed = stats["passed"]
        total = stats["total"]
        pct = (passed / total * 100) if total > 0 else 0
        scores = stats["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0
        lines.append(f"| {skill_set_name} | {passed}/{total} ({pct:.0f}%) | {avg_score:.1f} |")

    lines.append("")
    lines.append("## By Scenario")
    lines.append("")

    for scenario_name, skill_sets in sorted(results.items()):
        lines.append(f"### {scenario_name}")
        lines.append("")
        for skill_set_name, data in sorted(skill_sets.items()):
            success = data.get("success")
            score = data.get("score")
            notes = data.get("notes", "")

            icon = "✓" if success else "❌" if success is False else "?"
            score_str = f"({score})" if score is not None else ""
            notes_str = f" - {notes}" if notes else ""

            lines.append(f"- **{skill_set_name}**: {icon} {score_str}{notes_str}")
        lines.append("")

    return "\n".join(lines)


def save_report(run_dir: Path, reports_dir: Path) -> Path:
    """Generate and save report to reports directory."""
    report = generate_report(run_dir)
    report_file = reports_dir / f"{run_dir.name}.md"
    report_file.write_text(report)
    return report_file
