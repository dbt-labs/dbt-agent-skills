"""CLI entry point for skill-eval."""

from pathlib import Path
from typing import Optional

import typer

from skill_eval import __version__

app = typer.Typer(help="A/B test skill variations against recorded scenarios.")


def get_latest_run(runs_dir: Path) -> Path:
    """Get the most recent run directory.

    Args:
        runs_dir: Directory containing runs

    Returns:
        Path to the most recent run directory

    Raises:
        typer.Exit: If no runs found
    """
    if not runs_dir.exists():
        typer.echo("Error: No runs directory found", err=True)
        raise typer.Exit(1)

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")],
        reverse=True,
    )
    if not run_dirs:
        typer.echo("Error: No runs found", err=True)
        raise typer.Exit(1)

    typer.echo(f"Using latest run: {run_dirs[0].name}")
    return run_dirs[0]


def find_run(runs_dir: Path, run_id: Optional[str]) -> Path:
    """Find a run by exact or partial ID match, or get latest if no ID provided.

    Args:
        runs_dir: Directory containing runs
        run_id: Full or partial run ID, or None for latest

    Returns:
        Path to the matching run directory

    Raises:
        typer.Exit: If no match or multiple matches found
    """
    if run_id is None:
        return get_latest_run(runs_dir)

    # Try exact match first
    exact_match = runs_dir / run_id
    if exact_match.exists() and exact_match.is_dir():
        return exact_match

    # Get all run directories
    all_runs = [
        d for d in runs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]

    # Try partial match (contains)
    matches = [d for d in all_runs if run_id in d.name]

    if len(matches) == 1:
        typer.echo(f"Matched run: {matches[0].name}")
        return matches[0]
    elif len(matches) > 1:
        typer.echo(f"Error: '{run_id}' matches multiple runs:", err=True)
        for m in sorted(matches, key=lambda d: d.name, reverse=True)[:10]:
            typer.echo(f"  - {m.name}", err=True)
        if len(matches) > 10:
            typer.echo(f"  ... and {len(matches) - 10} more", err=True)
        raise typer.Exit(1)
    else:
        typer.echo(f"Error: No run matching '{run_id}'", err=True)
        recent = sorted(all_runs, key=lambda d: d.name, reverse=True)[:5]
        if recent:
            typer.echo("Recent runs:", err=True)
            for r in recent:
                typer.echo(f"  - {r.name}", err=True)
        raise typer.Exit(1)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"skill-eval {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True
    ),
) -> None:
    """Skill evaluation CLI."""
    pass


@app.command()
def run(
    scenario: Optional[str] = typer.Argument(None, help="Scenario name to run"),
    all_scenarios: bool = typer.Option(False, "--all", help="Run all scenarios"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run tasks in parallel"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
) -> None:
    """Run scenarios against skill variants."""
    from skill_eval.models import load_scenario
    from skill_eval.runner import Runner, RunTask

    evals_dir = Path.cwd()
    scenarios_dir = evals_dir / "scenarios"

    if all_scenarios:
        scenario_dirs = [
            d for d in scenarios_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
    elif scenario:
        scenario_path = scenarios_dir / scenario
        if not scenario_path.exists():
            typer.echo(f"Error: Scenario not found: {scenario}", err=True)
            raise typer.Exit(1)
        scenario_dirs = [scenario_path]
    else:
        typer.echo("Error: Specify a scenario name or use --all", err=True)
        raise typer.Exit(1)

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    typer.echo(f"Run directory: {run_dir}")

    # Load all scenarios
    scenarios = [load_scenario(d) for d in sorted(scenario_dirs)]

    if parallel:
        # Build task list for all scenario/skill-set combinations
        tasks = [
            RunTask(scenario=s, skill_set=ss, run_dir=run_dir)
            for s in scenarios
            for ss in s.skill_sets
        ]

        total = len(tasks)
        typer.echo(f"\nRunning {total} tasks with {workers} workers...\n")

        completed = 0
        passed = 0
        failed = 0

        def on_complete(task: RunTask, result) -> None:
            nonlocal completed, passed, failed
            completed += 1
            if result.success:
                passed += 1
                icon = "✓"
            else:
                failed += 1
                icon = "✗"
            typer.echo(f"  [{completed}/{total}] {task.scenario.name}/{task.skill_set.name} {icon}")

        runner.run_parallel(tasks, max_workers=workers, progress_callback=on_complete)

        typer.echo(f"\nRun complete: {passed} passed, {failed} failed")
    else:
        # Sequential execution (original behavior)
        for scenario_obj in scenarios:
            typer.echo(f"\nScenario: {scenario_obj.name}")

            for skill_set in scenario_obj.skill_sets:
                typer.echo(f"  Running: {skill_set.name}...", nl=False)
                result = runner.run_scenario(scenario_obj, skill_set, run_dir)
                if result.success:
                    typer.echo(" done")
                else:
                    typer.echo(f" FAILED: {result.error}")

        typer.echo(f"\nRun complete: {run_dir}")

    typer.echo(f"Next: uv run skill-eval grade {run_dir.name}")


@app.command()
def grade(
    run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run."),
    auto: bool = typer.Option(False, "--auto", help="Auto-grade using Claude"),
) -> None:
    """Grade outputs from a run."""
    import yaml

    from skill_eval.grader import (
        auto_grade_run,
        build_grading_prompt,
        call_claude_grader,
        compute_skill_usage,
        init_grades_file,
        parse_grade_response,
        save_grades,
    )

    evals_dir = Path.cwd()
    runs_dir = evals_dir / "runs"
    scenarios_dir = evals_dir / "scenarios"

    run_dir = find_run(runs_dir, run_id)

    if auto:
        typer.echo(f"Auto-grading run: {run_id}")
        typer.echo()

        # Count scenarios and skill sets for progress
        total = sum(
            1
            for scenario_dir in run_dir.iterdir()
            if scenario_dir.is_dir() and not scenario_dir.name.startswith(".")
            for skill_set_dir in scenario_dir.iterdir()
            if skill_set_dir.is_dir()
        )

        current = 0
        results: dict[str, dict[str, dict]] = {}

        for scenario_dir in sorted(run_dir.iterdir()):
            if not scenario_dir.is_dir() or scenario_dir.name.startswith("."):
                continue

            scenario_name = scenario_dir.name
            results[scenario_name] = {}

            for skill_set_dir in sorted(scenario_dir.iterdir()):
                if not skill_set_dir.is_dir():
                    continue

                skill_set_name = skill_set_dir.name
                current += 1
                typer.echo(f"  [{current}/{total}] Grading {scenario_name}/{skill_set_name}...", nl=False)

                from dataclasses import asdict

                # Load metadata for skill usage computation
                metadata_file = skill_set_dir / "metadata.yaml"
                metadata = {}
                if metadata_file.exists():
                    with metadata_file.open() as f:
                        metadata = yaml.safe_load(f) or {}

                grading_prompt = build_grading_prompt(scenarios_dir / scenario_name, skill_set_dir)
                response = call_claude_grader(grading_prompt)
                grade = parse_grade_response(response)

                # Add skill usage data (computed from metadata, not from Claude)
                available, invoked, pct = compute_skill_usage(metadata)
                grade.skills_available = available
                grade.skills_invoked = invoked
                grade.skill_usage_pct = pct

                results[scenario_name][skill_set_name] = asdict(grade)

                # Show result
                success_icon = "✓" if grade.success else "✗" if grade.success is False else "?"
                score = grade.score if grade.score is not None else "?"
                typer.echo(f" {success_icon} (score: {score})")

        grades = {"graded_at": None, "grader": "claude-auto", "results": results}
        save_grades(run_dir, grades)
        grades_file = run_dir / "grades.yaml"
        typer.echo(f"\nGrades saved to: {grades_file}")
        typer.echo(f"Run: uv run skill-eval report {run_id}")
    else:
        grades_file = init_grades_file(run_dir)

        typer.echo(f"Grades file: {grades_file}")
        typer.echo("\nOutputs to review:")

        for scenario_dir in sorted(run_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            typer.echo(f"\n  {scenario_dir.name}/")
            for skill_set_dir in sorted(scenario_dir.iterdir()):
                if not skill_set_dir.is_dir():
                    continue
                typer.echo(f"    {skill_set_dir.name}/output.md")

        typer.echo(f"\nEdit {grades_file} to record your grades.")
        typer.echo(f"Then run: uv run skill-eval report {run_id}")


@app.command()
def report(run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run.")) -> None:
    """Generate comparison report for a run."""
    from skill_eval.reporter import print_rich_report, save_report

    evals_dir = Path.cwd()
    runs_dir = evals_dir / "runs"

    run_dir = find_run(runs_dir, run_id)

    reports_dir = evals_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_file = save_report(run_dir, reports_dir)
    print_rich_report(run_dir)

    typer.echo(f"\nSaved to: {report_file}")


@app.command()
def review(
    run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run."),
) -> None:
    """Open HTML transcripts in browser for review."""
    import webbrowser

    evals_dir = Path.cwd()
    runs_dir = evals_dir / "runs"

    run_dir = find_run(runs_dir, run_id)

    # Find all transcript index.html files
    transcripts = list(run_dir.glob("**/transcript/index.html"))

    if not transcripts:
        typer.echo(f"Error: No transcripts found in {run_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Opening {len(transcripts)} transcript(s)...")

    for transcript in sorted(transcripts):
        # Show which transcript we're opening
        rel_path = transcript.relative_to(run_dir)
        typer.echo(f"  {rel_path}")
        webbrowser.open(f"file://{transcript}")


if __name__ == "__main__":
    app()
