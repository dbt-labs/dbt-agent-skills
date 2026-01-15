"""CLI entry point for skill-eval."""

from pathlib import Path
from typing import Optional

import typer

from skill_eval import __version__

app = typer.Typer(help="A/B test skill variations against recorded scenarios.")


def version_callback(value: bool) -> None:
    if value:
        print(f"skill-eval {__version__}")
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
) -> None:
    """Run scenarios against skill variants."""
    from skill_eval.models import load_scenario
    from skill_eval.runner import Runner

    evals_dir = Path.cwd() / "evals"
    scenarios_dir = evals_dir / "scenarios"

    if all_scenarios:
        scenario_dirs = [
            d for d in scenarios_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
    elif scenario:
        scenario_path = scenarios_dir / scenario
        if not scenario_path.exists():
            print(f"Error: Scenario not found: {scenario}")
            raise typer.Exit(1)
        scenario_dirs = [scenario_path]
    else:
        print("Error: Specify a scenario name or use --all")
        raise typer.Exit(1)

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    print(f"Run directory: {run_dir}")

    for scenario_dir in scenario_dirs:
        scenario_obj = load_scenario(scenario_dir)
        print(f"\nScenario: {scenario_obj.name}")

        for skill_set in scenario_obj.skill_sets:
            print(f"  Running: {skill_set.name}...", end="", flush=True)
            result = runner.run_scenario(scenario_obj, skill_set, run_dir)
            if result.success:
                print(" done")
            else:
                print(f" FAILED: {result.error}")

    print(f"\nRun complete: {run_dir}")
    print(f"Next: uv run skill-eval grade {run_dir.name}")


@app.command()
def grade(run_id: str = typer.Argument(..., help="Run ID (timestamp directory name)")) -> None:
    """Grade outputs from a run."""
    print("grade command - not implemented yet")


@app.command()
def report(run_id: str = typer.Argument(..., help="Run ID (timestamp directory name)")) -> None:
    """Generate comparison report for a run."""
    print("report command - not implemented yet")


if __name__ == "__main__":
    app()
