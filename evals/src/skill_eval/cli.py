"""CLI entry point for skill-eval."""

from pathlib import Path
from typing import Optional

import typer

from skill_eval import __version__
from skill_eval.logging import logger
from skill_eval.selector import is_interactive, select_run, select_scenarios

app = typer.Typer(help="A/B test skill variations against recorded scenarios.")


def find_evals_root(start: Path | None = None) -> Path | None:
    """Find the evals root directory by looking for a 'scenarios/' subdirectory.

    Walks up from `start` (or cwd) looking for a directory containing 'scenarios/'.
    Also checks for an 'evals/scenarios/' child (repo root case).

    Returns:
        The evals root directory, or None if not found.
    """
    current = (start or Path.cwd()).resolve()

    # Walk up the directory tree
    for directory in [current, *current.parents]:
        if (directory / "scenarios").is_dir():
            return directory
        # Check for evals/ subdirectory (running from repo root)
        if (directory / "evals" / "scenarios").is_dir():
            return directory / "evals"

    return None


def _get_evals_dir(base_dir: Path | None = None) -> Path:
    """Get the evals root directory, or exit with error.

    Args:
        base_dir: Explicit base directory override. If provided, use it directly.
    """
    if base_dir:
        return base_dir
    evals_dir = find_evals_root()
    if evals_dir is None:
        typer.echo(
            "Error: Could not find evals root (no scenarios/ directory found).\n"
            "Run from inside your evals directory or use --base-dir.",
            err=True,
        )
        raise typer.Exit(1)
    return evals_dir


def get_latest_run(runs_dir: Path, *, silent: bool = False) -> Path:
    """Get the most recent run directory.

    Args:
        runs_dir: Directory containing runs
        silent: If True, don't print the run name

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

    if not silent:
        typer.echo(f"Using latest run: {run_dirs[0].name}")
    return run_dirs[0]


def find_run(runs_dir: Path, run_id: Optional[str], *, latest: bool = False) -> Path:
    """Find a run by exact or partial ID match, or get latest/prompt if no ID provided.

    Args:
        runs_dir: Directory containing runs
        run_id: Full or partial run ID, or None for latest/interactive
        latest: If True and no run_id, use latest without prompting

    Returns:
        Path to the matching run directory

    Raises:
        typer.Exit: If no match or multiple matches found
    """
    if not runs_dir.exists():
        typer.echo("Error: No runs directory found", err=True)
        raise typer.Exit(1)

    # Get all run directories
    all_runs = [
        d for d in runs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]

    if not all_runs:
        typer.echo("Error: No runs found", err=True)
        raise typer.Exit(1)

    if run_id is None:
        # No run_id provided - decide behavior based on flags and interactivity
        if latest:
            return get_latest_run(runs_dir)

        if is_interactive():
            # Show interactive selector
            selected = select_run(all_runs, "Select a run")
            if selected is None:
                typer.echo("Selection cancelled", err=True)
                raise typer.Exit(1)
            typer.echo(f"Selected run: {selected.name}")
            return selected
        else:
            # Non-interactive: fall back to latest
            return get_latest_run(runs_dir)

    # Try exact match first
    exact_match = runs_dir / run_id
    if exact_match.exists() and exact_match.is_dir():
        return exact_match

    # Try partial match (contains)
    matches = [d for d in all_runs if run_id in d.name]

    if len(matches) == 1:
        typer.echo(f"Matched run: {matches[0].name}")
        return matches[0]
    elif len(matches) > 1:
        # Multiple matches
        if is_interactive():
            # Show selector with only the matching runs
            selected = select_run(matches, f"Multiple runs match '{run_id}'")
            if selected is None:
                typer.echo("Selection cancelled", err=True)
                raise typer.Exit(1)
            typer.echo(f"Selected run: {selected.name}")
            return selected
        else:
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


def find_scenarios(
    scenarios_dir: Path, names: list[str] | None, *, all_flag: bool = False
) -> list[Path]:
    """Find scenarios by name or prompt for selection.

    Args:
        scenarios_dir: Directory containing scenarios
        names: List of scenario names (can be partial matches), or None
        all_flag: If True, return all scenarios without prompting

    Returns:
        List of scenario directory paths

    Raises:
        typer.Exit: If no scenarios found or selection cancelled
    """
    if not scenarios_dir.exists():
        typer.echo("Error: No scenarios directory found", err=True)
        raise typer.Exit(1)

    # Get all scenario directories (exclude only hidden dirs starting with .)
    all_scenarios = [
        d
        for d in scenarios_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]

    if not all_scenarios:
        typer.echo("Error: No scenarios found", err=True)
        raise typer.Exit(1)

    if all_flag:
        return sorted(all_scenarios, key=lambda d: d.name)

    if names:
        # Match provided names
        matched: list[Path] = []
        for name in names:
            # Try exact match first
            exact = scenarios_dir / name
            if exact.exists() and exact.is_dir():
                matched.append(exact)
                continue
            # Try partial match
            partial_matches = [d for d in all_scenarios if name in d.name]
            if len(partial_matches) == 1:
                matched.append(partial_matches[0])
            elif len(partial_matches) > 1:
                typer.echo(f"Error: '{name}' matches multiple scenarios:", err=True)
                for m in partial_matches:
                    typer.echo(f"  - {m.name}", err=True)
                raise typer.Exit(1)
            else:
                typer.echo(f"Error: No scenario matching '{name}'", err=True)
                raise typer.Exit(1)
        return matched

    # No names provided - decide behavior based on interactivity
    if is_interactive():
        # Show interactive multi-selector
        selected = select_scenarios(all_scenarios, "Select scenarios to run")
        if not selected:
            typer.echo("No scenarios selected", err=True)
            raise typer.Exit(1)
        typer.echo(f"Selected {len(selected)} scenario(s)")
        return selected
    else:
        # Non-interactive without --all: error
        typer.echo("Error: Specify scenario names or use --all", err=True)
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
    scenarios: Optional[list[str]] = typer.Argument(
        None, help="Scenario names to run (supports partial matches)"
    ),
    all_scenarios: bool = typer.Option(False, "--all", help="Run all scenarios"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run tasks in parallel"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress (tool calls)"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", "-d", help="Evals root directory (default: auto-detected)"),
) -> None:
    """Run scenarios against skill variants."""
    from skill_eval.logging import set_level
    from skill_eval.models import load_scenario
    from skill_eval.runner import Runner, RunTask

    if verbose:
        set_level("DEBUG")

    evals_dir = _get_evals_dir(base_dir)
    scenarios_dir = evals_dir / "scenarios"

    scenario_dirs = find_scenarios(scenarios_dir, scenarios, all_flag=all_scenarios)

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    typer.echo(f"Run directory: {run_dir}")

    # Load all scenarios
    loaded_scenarios = [load_scenario(d) for d in sorted(scenario_dirs)]

    if parallel:
        # Build task list for all scenario/skill-set combinations
        tasks = [
            RunTask(scenario=s, skill_set=ss, run_dir=run_dir)
            for s in loaded_scenarios
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
            logger.info(f"[{completed}/{total}] {task.scenario.name}/{task.skill_set.name} {icon}")

        runner.run_parallel(tasks, max_workers=workers, progress_callback=on_complete)

        logger.success(f"Run complete: {passed} passed, {failed} failed")
    else:
        # Sequential execution (original behavior)
        for scenario_obj in loaded_scenarios:
            logger.info(f"Scenario: {scenario_obj.name}")

            for skill_set in scenario_obj.skill_sets:
                logger.info(f"  Starting: {skill_set.name}")
                result = runner.run_scenario(scenario_obj, skill_set, run_dir)
                if result.success:
                    logger.success(f"  Completed: {skill_set.name}")
                else:
                    logger.error(f"  Failed: {skill_set.name} - {result.error}")

        logger.success(f"Run complete: {run_dir}")

    typer.echo(f"Next: uv run skill-eval grade {run_dir.name}")


@app.command()
def grade(
    run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run."),
    auto: bool = typer.Option(False, "--auto", help="Auto-grade using Claude"),
    latest: bool = typer.Option(False, "--latest", "-l", help="Use latest run without prompting"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", "-d", help="Evals root directory (default: auto-detected)"),
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

    evals_dir = _get_evals_dir(base_dir)
    runs_dir = evals_dir / "runs"
    scenarios_dir = evals_dir / "scenarios"

    run_dir = find_run(runs_dir, run_id, latest=latest)

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
def report(
    run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run."),
    latest: bool = typer.Option(False, "--latest", "-l", help="Use latest run without prompting"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", "-d", help="Evals root directory (default: auto-detected)"),
) -> None:
    """Generate comparison report for a run."""
    from skill_eval.reporter import print_rich_report, save_report

    evals_dir = _get_evals_dir(base_dir)
    runs_dir = evals_dir / "runs"

    run_dir = find_run(runs_dir, run_id, latest=latest)

    reports_dir = evals_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_file = save_report(run_dir, reports_dir)
    print_rich_report(run_dir)

    typer.echo(f"\nSaved to: {report_file}")


@app.command()
def review(
    run_id: Optional[str] = typer.Argument(None, help="Run ID (full or partial). Defaults to latest run."),
    latest: bool = typer.Option(False, "--latest", "-l", help="Use latest run without prompting"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", "-d", help="Evals root directory (default: auto-detected)"),
) -> None:
    """Open HTML transcripts in browser for review."""
    import webbrowser

    evals_dir = _get_evals_dir(base_dir)
    runs_dir = evals_dir / "runs"

    run_dir = find_run(runs_dir, run_id, latest=latest)

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


@app.command()
def new(
    name: str = typer.Argument(..., help="Scenario name (lowercase, hyphens only)"),
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", "-d", help="Evals root directory (default: auto-detected)"),
    context: Optional[list[Path]] = typer.Option(None, "--context", "-c", help="Files or directories to copy into context/"),
) -> None:
    """Create a new scenario from templates."""
    from skill_eval.scaffold import copy_context, create_scenario, validate_scenario_name

    # Validate name
    error = validate_scenario_name(name)
    if error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    # Find evals root (default to cwd/evals/ for bootstrapping)
    if base_dir:
        evals_dir = base_dir
    else:
        evals_dir = find_evals_root()
        if evals_dir is None:
            evals_dir = Path.cwd() / "evals"

    # Create scenario
    try:
        scenario_dir = create_scenario(name, evals_dir)
    except FileExistsError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Copy context files
    if context:
        for ctx_path in context:
            if not ctx_path.exists():
                typer.echo(f"Warning: Context path not found: {ctx_path}", err=True)
                continue
            copy_context(ctx_path, scenario_dir)

    # Print summary with paths relative to cwd
    cwd = Path.cwd().resolve()
    scenario_abs = scenario_dir.resolve()
    if scenario_abs.is_relative_to(cwd):
        rel = scenario_abs.relative_to(cwd)
    else:
        rel = scenario_abs
    typer.echo(f"\nCreated scenario: {rel}/")
    typer.echo("\nFiles to edit:")
    typer.echo(f"  - {rel}/prompt.txt        <- write your prompt")
    typer.echo(f"  - {rel}/scenario.md       <- describe background, expected outcome, grading criteria")
    typer.echo(f"  - {rel}/skill-sets.yaml   <- configure skill sets to compare")
    typer.echo(f"  - {rel}/.env              <- add credentials")
    if context:
        typer.echo(f"  - {rel}/context/          <- review copied context files")
    else:
        typer.echo(f"  - {rel}/context/          <- add files the agent needs")


if __name__ == "__main__":
    app()
