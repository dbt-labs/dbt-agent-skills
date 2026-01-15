"""CLI entry point for skill-eval."""

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
    print("run command - not implemented yet")


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
