"""Scenario scaffolding for skill-eval new command."""

import re
import shutil
from collections.abc import Callable
from pathlib import Path

ALWAYS_EXCLUDED = {".git", "__pycache__", ".venv", "node_modules", ".env", ".claude", ".agents"}

DBT_EXCLUDED = {"logs", "target", "dbt_packages", "integration_tests", "dbt_internal_packages"}


def get_templates_dir() -> Path:
    """Return the path to the bundled template files."""
    return Path(__file__).parent / "templates"


def validate_scenario_name(name: str) -> str | None:
    """Validate a scenario name. Returns error message or None if valid."""
    if not name:
        return "Scenario name cannot be empty"
    if name != name.lower():
        return "Scenario name must be lowercase"
    if not re.match(r"^[_a-z][a-z0-9_-]*$", name):
        return "Scenario name must start with a letter or underscore and contain only lowercase letters, digits, hyphens, and underscores"
    return None


def is_dbt_project(path: Path) -> bool:
    """Check if path is inside a dbt project (has dbt_project.yml in path or ancestors)."""
    current = path.resolve()
    for directory in [current, *current.parents]:
        if (directory / "dbt_project.yml").is_file():
            return True
    return False


def _build_ignore_fn(
    excluded_dirs: set[str], target_abs: Path
) -> Callable[[str, list[str]], set[str]]:
    """Build a shutil.copytree ignore function."""
    def _ignore(directory: str, contents: list[str]) -> set[str]:
        ignored = set()
        dir_path = Path(directory).resolve()
        for item in contents:
            if item in excluded_dirs:
                ignored.add(item)
                continue
            # Exclude the target directory if it's inside the source
            item_path = (dir_path / item).resolve()
            if item_path == target_abs or target_abs.is_relative_to(item_path):
                ignored.add(item)
        return ignored
    return _ignore


def copy_context(source: Path, target_scenario_dir: Path) -> None:
    """Copy a file or directory into the scenario's context/ directory.

    Args:
        source: File or directory to copy
        target_scenario_dir: The scenario directory (context/ will be created inside it)
    """
    context_dir = target_scenario_dir / "context"
    context_dir.mkdir(exist_ok=True)

    source = source.resolve()
    target_abs = target_scenario_dir.resolve()

    if source.is_file():
        shutil.copy2(source, context_dir / source.name)
        return

    # Directory copy with exclusions
    excluded = set(ALWAYS_EXCLUDED)
    if is_dbt_project(source):
        excluded |= DBT_EXCLUDED

    ignore_fn = _build_ignore_fn(excluded, target_abs)
    dest = context_dir / source.name
    shutil.copytree(source, dest, ignore=ignore_fn)


def create_scenario(name: str, base_dir: Path) -> Path:
    """Create a new scenario from templates.

    Args:
        name: Scenario name (validated, lowercase-with-hyphens)
        base_dir: The evals root directory

    Returns:
        Path to the created scenario directory

    Raises:
        FileExistsError: If scenario directory already exists
    """
    scenario_dir = base_dir / "scenarios" / name
    if scenario_dir.exists():
        raise FileExistsError(f"Scenario already exists: {scenario_dir}")

    scenario_dir.mkdir(parents=True)
    (scenario_dir / "context").mkdir()

    templates_dir = get_templates_dir()

    # Copy template files
    for template_file in templates_dir.iterdir():
        dest = scenario_dir / template_file.name
        content = template_file.read_text()

        # Replace placeholders in scenario.md
        if template_file.name == "scenario.md":
            human_name = name.replace("-", " ").title()
            content = content.replace("{{scenario_name}}", human_name)

        dest.write_text(content)

    return scenario_dir
