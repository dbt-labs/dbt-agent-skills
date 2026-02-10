"""Tests for scenario scaffolding."""

from pathlib import Path


def test_templates_directory_exists() -> None:
    """Template files are accessible from the package."""
    templates_dir = Path(__file__).parent.parent / "src" / "skill_eval" / "templates"
    assert templates_dir.exists()
    assert (templates_dir / "skill-sets.yaml").exists()
    assert (templates_dir / "scenario.md").exists()
    assert (templates_dir / "prompt.txt").exists()
    assert (templates_dir / ".env.example").exists()
