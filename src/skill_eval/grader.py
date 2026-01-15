"""Grading utilities for skill evaluation."""

from datetime import datetime
from pathlib import Path

import yaml


def init_grades_file(run_dir: Path) -> Path:
    """Create initial grades.yaml file for a run."""
    grades_file = run_dir / "grades.yaml"

    if grades_file.exists():
        return grades_file

    results: dict = {}
    for scenario_dir in run_dir.iterdir():
        if not scenario_dir.is_dir():
            continue
        scenario_name = scenario_dir.name
        results[scenario_name] = {}

        for skill_set_dir in scenario_dir.iterdir():
            if not skill_set_dir.is_dir():
                continue
            skill_set_name = skill_set_dir.name
            results[scenario_name][skill_set_name] = {
                "success": None,
                "score": None,
                "criteria": {},
                "notes": "",
                "observations": "",
            }

    grades = {
        "graded_at": None,
        "grader": "human",
        "results": results,
    }

    with grades_file.open("w") as f:
        yaml.dump(grades, f, default_flow_style=False, sort_keys=False)

    return grades_file


def load_grades(run_dir: Path) -> dict:
    """Load grades from a run directory."""
    grades_file = run_dir / "grades.yaml"
    if not grades_file.exists():
        return {}
    with grades_file.open() as f:
        return yaml.safe_load(f)


def save_grades(run_dir: Path, grades: dict) -> None:
    """Save grades to a run directory."""
    grades["graded_at"] = datetime.now().isoformat()
    grades_file = run_dir / "grades.yaml"
    with grades_file.open("w") as f:
        yaml.dump(grades, f, default_flow_style=False, sort_keys=False)
