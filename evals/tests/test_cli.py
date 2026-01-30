"""Tests for skill_eval CLI."""

from pathlib import Path

import pytest
from click.exceptions import Exit

from skill_eval.cli import find_run, get_latest_run


def test_get_latest_run_returns_most_recent(tmp_path: Path) -> None:
    """get_latest_run returns the most recently named run directory."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-02-100000").mkdir()
    (runs_dir / "2024-01-01-150000").mkdir()

    result = get_latest_run(runs_dir)

    assert result.name == "2024-01-02-100000"


def test_get_latest_run_ignores_hidden_dirs(tmp_path: Path) -> None:
    """get_latest_run ignores hidden directories."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / ".DS_Store").mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()

    result = get_latest_run(runs_dir)

    assert result.name == "2024-01-01-100000"


def test_get_latest_run_exits_when_no_runs(tmp_path: Path) -> None:
    """get_latest_run exits with error when no runs exist."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    with pytest.raises(Exit):
        get_latest_run(runs_dir)


def test_get_latest_run_exits_when_dir_missing(tmp_path: Path) -> None:
    """get_latest_run exits with error when runs dir doesn't exist."""
    runs_dir = tmp_path / "runs"  # Not created

    with pytest.raises(Exit):
        get_latest_run(runs_dir)


def test_find_run_returns_latest_when_none(tmp_path: Path) -> None:
    """find_run returns latest run when run_id is None."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-02-100000").mkdir()

    result = find_run(runs_dir, None)

    assert result.name == "2024-01-02-100000"


def test_find_run_exact_match(tmp_path: Path) -> None:
    """find_run returns exact match when provided."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-02-100000").mkdir()

    result = find_run(runs_dir, "2024-01-01-100000")

    assert result.name == "2024-01-01-100000"


def test_find_run_partial_match(tmp_path: Path) -> None:
    """find_run returns partial match when unique."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-02-01-100000").mkdir()

    result = find_run(runs_dir, "01-01")

    assert result.name == "2024-01-01-100000"


def test_find_run_exits_on_ambiguous_match(tmp_path: Path) -> None:
    """find_run exits with error when multiple runs match."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-01-150000").mkdir()

    with pytest.raises(Exit):
        find_run(runs_dir, "01-01")


def test_find_run_exits_on_no_match(tmp_path: Path) -> None:
    """find_run exits with error when no runs match."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()

    with pytest.raises(Exit):
        find_run(runs_dir, "nonexistent")
