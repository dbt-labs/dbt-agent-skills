"""Tests for scenario scaffolding."""

from pathlib import Path

import pytest

from skill_eval.scaffold import (
    ALWAYS_EXCLUDED,
    DBT_EXCLUDED,
    copy_context,
    create_scenario,
    get_templates_dir,
    is_dbt_project,
    validate_scenario_name,
)


def test_templates_directory_exists() -> None:
    """Template files are accessible from the package."""
    templates_dir = Path(__file__).parent.parent / "src" / "skill_eval" / "templates"
    assert templates_dir.exists()
    assert (templates_dir / "skill-sets.yaml").exists()
    assert (templates_dir / "scenario.md").exists()
    assert (templates_dir / "prompt.txt").exists()
    assert (templates_dir / ".env").exists()


# validate_scenario_name tests


def test_validate_scenario_name_valid() -> None:
    """Valid scenario names pass validation."""
    assert validate_scenario_name("my-scenario") is None
    assert validate_scenario_name("dbt-job-failure-123") is None
    assert validate_scenario_name("a") is None
    assert validate_scenario_name("_test-scenario") is None
    assert validate_scenario_name("_wip") is None
    assert validate_scenario_name("_copy_ia") is None


def test_validate_scenario_name_uppercase() -> None:
    """Uppercase names are rejected."""
    error = validate_scenario_name("My-Scenario")
    assert error is not None
    assert "lowercase" in error


def test_validate_scenario_name_special_chars() -> None:
    """Special characters are rejected."""
    error = validate_scenario_name("my scenario")
    assert error is not None
    error = validate_scenario_name("my.scenario")
    assert error is not None


def test_validate_scenario_name_empty() -> None:
    """Empty names are rejected."""
    error = validate_scenario_name("")
    assert error is not None


# get_templates_dir tests


def test_get_templates_dir() -> None:
    """Templates directory is found inside the package."""
    templates = get_templates_dir()
    assert templates.exists()
    assert (templates / "skill-sets.yaml").exists()


# is_dbt_project tests


def test_is_dbt_project_detects_project(tmp_path: Path) -> None:
    """Detects dbt project by dbt_project.yml."""
    (tmp_path / "dbt_project.yml").write_text("name: test")
    assert is_dbt_project(tmp_path) is True


def test_is_dbt_project_detects_parent(tmp_path: Path) -> None:
    """Detects dbt project in parent directory."""
    (tmp_path / "dbt_project.yml").write_text("name: test")
    sub = tmp_path / "models"
    sub.mkdir()
    assert is_dbt_project(sub) is True


def test_is_dbt_project_false(tmp_path: Path) -> None:
    """Returns False when no dbt_project.yml found."""
    assert is_dbt_project(tmp_path) is False


# create_scenario tests


def test_create_scenario_basic(tmp_path: Path) -> None:
    """Creates scenario with all template files."""
    scenario_dir = create_scenario("my-test", tmp_path)

    assert scenario_dir == tmp_path / "scenarios" / "my-test"
    assert (scenario_dir / "skill-sets.yaml").exists()
    assert (scenario_dir / "scenario.md").exists()
    assert (scenario_dir / "prompt.txt").exists()
    assert (scenario_dir / ".env").exists()


def test_create_scenario_replaces_name(tmp_path: Path) -> None:
    """scenario.md has the humanized scenario name."""
    scenario_dir = create_scenario("dbt-job-failure", tmp_path)
    content = (scenario_dir / "scenario.md").read_text()
    assert "# Dbt Job Failure" in content
    assert "{{scenario_name}}" not in content


def test_create_scenario_errors_if_exists(tmp_path: Path) -> None:
    """Raises error if scenario directory already exists."""
    (tmp_path / "scenarios" / "existing").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        create_scenario("existing", tmp_path)


# copy_context tests


def test_copy_context_file(tmp_path: Path) -> None:
    """Copies a single file into context/."""
    src = tmp_path / "source.yml"
    src.write_text("content")
    target = tmp_path / "scenarios" / "test"
    target.mkdir(parents=True)

    copy_context(src, target)

    assert (target / "context" / "source.yml").read_text() == "content"


def test_copy_context_directory(tmp_path: Path) -> None:
    """Copies a directory tree into context/."""
    src = tmp_path / "models"
    src.mkdir()
    (src / "a.sql").write_text("SELECT 1")
    (src / "sub").mkdir()
    (src / "sub" / "b.sql").write_text("SELECT 2")

    target = tmp_path / "scenarios" / "test"
    target.mkdir(parents=True)

    copy_context(src, target)

    assert (target / "context" / "models" / "a.sql").exists()
    assert (target / "context" / "models" / "sub" / "b.sql").exists()


def test_copy_context_excludes_always(tmp_path: Path) -> None:
    """Always-excluded directories are skipped."""
    src = tmp_path / "project"
    src.mkdir()
    (src / "models").mkdir()
    (src / "models" / "a.sql").write_text("SELECT 1")
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("git stuff")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "mod.pyc").write_text("bytecode")

    target = tmp_path / "scenarios" / "test"
    target.mkdir(parents=True)

    copy_context(src, target)

    assert (target / "context" / "project" / "models" / "a.sql").exists()
    assert not (target / "context" / "project" / ".git").exists()
    assert not (target / "context" / "project" / "__pycache__").exists()


def test_copy_context_excludes_dbt_dirs(tmp_path: Path) -> None:
    """dbt-specific directories are excluded when dbt project is detected."""
    src = tmp_path / "dbt_project"
    src.mkdir()
    (src / "dbt_project.yml").write_text("name: test")
    (src / "models").mkdir()
    (src / "models" / "a.sql").write_text("SELECT 1")
    (src / "target").mkdir()
    (src / "target" / "compiled.sql").write_text("compiled")
    (src / "dbt_packages").mkdir()
    (src / "dbt_packages" / "pkg").write_text("pkg")
    (src / "logs").mkdir()
    (src / "logs" / "dbt.log").write_text("log")

    target = tmp_path / "scenarios" / "test"
    target.mkdir(parents=True)

    copy_context(src, target)

    assert (target / "context" / "dbt_project" / "models" / "a.sql").exists()
    assert not (target / "context" / "dbt_project" / "target").exists()
    assert not (target / "context" / "dbt_project" / "dbt_packages").exists()
    assert not (target / "context" / "dbt_project" / "logs").exists()


def test_copy_context_no_dbt_exclusions_for_non_dbt(tmp_path: Path) -> None:
    """dbt directories are NOT excluded when no dbt_project.yml is present."""
    src = tmp_path / "project"
    src.mkdir()
    (src / "target").mkdir()
    (src / "target" / "output.txt").write_text("output")
    (src / "logs").mkdir()
    (src / "logs" / "app.log").write_text("log")

    target = tmp_path / "scenarios" / "test"
    target.mkdir(parents=True)

    copy_context(src, target)

    assert (target / "context" / "project" / "target" / "output.txt").exists()
    assert (target / "context" / "project" / "logs" / "app.log").exists()


def test_copy_context_excludes_self_reference(tmp_path: Path) -> None:
    """When source contains the target, the scenarios dir is excluded."""
    target = tmp_path / "scenarios" / "my-test"
    target.mkdir(parents=True)

    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "a.sql").write_text("SELECT 1")

    copy_context(tmp_path, target)

    # models/ should be copied (under the tmp_path dir name)
    context_root = target / "context"
    # scenarios/ must not appear anywhere in context
    assert not any(p.name == "scenarios" for p in context_root.rglob("*") if p.is_dir())
    # But models should be there
    assert any(p.name == "a.sql" for p in context_root.rglob("*"))
