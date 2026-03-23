"""Tests for skill_eval CLI."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.exceptions import Exit

from skill_eval.cli import find_evals_root, find_run, find_scenarios, get_latest_run


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


def test_find_run_returns_latest_when_none_non_interactive(tmp_path: Path) -> None:
    """find_run returns latest run when run_id is None in non-interactive mode."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-02-100000").mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=False):
        result = find_run(runs_dir, None)

    assert result.name == "2024-01-02-100000"


def test_find_run_returns_latest_with_flag(tmp_path: Path) -> None:
    """find_run returns latest run when --latest flag is used."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-02-100000").mkdir()

    result = find_run(runs_dir, None, latest=True)

    assert result.name == "2024-01-02-100000"


def test_find_run_interactive_calls_selector(tmp_path: Path) -> None:
    """find_run shows selector when interactive and no run_id."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run1 = runs_dir / "2024-01-01-100000"
    run2 = runs_dir / "2024-01-02-100000"
    run1.mkdir()
    run2.mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_run", return_value=run1) as mock_select:
            result = find_run(runs_dir, None)

    mock_select.assert_called_once()
    assert result == run1


def test_find_run_interactive_cancelled(tmp_path: Path) -> None:
    """find_run exits when interactive selection is cancelled."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_run", return_value=None):
            with pytest.raises(Exit):
                find_run(runs_dir, None)


def test_find_run_ambiguous_interactive_shows_selector(tmp_path: Path) -> None:
    """find_run shows selector for ambiguous matches in interactive mode."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run1 = runs_dir / "2024-01-01-100000"
    run2 = runs_dir / "2024-01-01-150000"
    run1.mkdir()
    run2.mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_run", return_value=run1) as mock_select:
            result = find_run(runs_dir, "01-01")

    # Should be called with only the matching runs
    mock_select.assert_called_once()
    call_args = mock_select.call_args[0][0]
    assert len(call_args) == 2
    assert result == run1


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


def test_find_run_exits_on_ambiguous_match_non_interactive(tmp_path: Path) -> None:
    """find_run exits with error when multiple runs match in non-interactive mode."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()
    (runs_dir / "2024-01-01-150000").mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=False):
        with pytest.raises(Exit):
            find_run(runs_dir, "01-01")


def test_find_run_exits_on_no_match(tmp_path: Path) -> None:
    """find_run exits with error when no runs match."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "2024-01-01-100000").mkdir()

    with pytest.raises(Exit):
        find_run(runs_dir, "nonexistent")


# find_scenarios tests


def test_find_scenarios_all_flag(tmp_path: Path) -> None:
    """find_scenarios returns all scenarios when --all flag is used."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()
    (scenarios_dir / "scenario-b").mkdir()
    (scenarios_dir / ".hidden").mkdir()
    (scenarios_dir / "_prefixed").mkdir()

    result = find_scenarios(scenarios_dir, None, all_flag=True)

    # Should include _prefixed (used for gitignore), exclude .hidden
    assert len(result) == 3
    names = [r.name for r in result]
    assert "scenario-a" in names
    assert "scenario-b" in names
    assert "_prefixed" in names
    assert ".hidden" not in names


def test_find_scenarios_exact_match(tmp_path: Path) -> None:
    """find_scenarios returns exact match when name provided."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()
    (scenarios_dir / "scenario-b").mkdir()

    result = find_scenarios(scenarios_dir, ["scenario-a"])

    assert len(result) == 1
    assert result[0].name == "scenario-a"


def test_find_scenarios_partial_match(tmp_path: Path) -> None:
    """find_scenarios returns unique partial match."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "test-scenario-a").mkdir()
    (scenarios_dir / "other-scenario-b").mkdir()

    result = find_scenarios(scenarios_dir, ["test"])

    assert len(result) == 1
    assert result[0].name == "test-scenario-a"


def test_find_scenarios_multiple_names(tmp_path: Path) -> None:
    """find_scenarios returns multiple scenarios for multiple names."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()
    (scenarios_dir / "scenario-b").mkdir()
    (scenarios_dir / "scenario-c").mkdir()

    result = find_scenarios(scenarios_dir, ["scenario-a", "scenario-c"])

    assert len(result) == 2
    names = [r.name for r in result]
    assert "scenario-a" in names
    assert "scenario-c" in names


def test_find_scenarios_ambiguous_match_exits(tmp_path: Path) -> None:
    """find_scenarios exits when partial name matches multiple scenarios."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()
    (scenarios_dir / "scenario-b").mkdir()

    with pytest.raises(Exit):
        find_scenarios(scenarios_dir, ["scenario"])


def test_find_scenarios_no_match_exits(tmp_path: Path) -> None:
    """find_scenarios exits when no match found."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()

    with pytest.raises(Exit):
        find_scenarios(scenarios_dir, ["nonexistent"])


def test_find_scenarios_interactive_calls_selector(tmp_path: Path) -> None:
    """find_scenarios shows selector when interactive and no names provided."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    s1 = scenarios_dir / "scenario-a"
    s2 = scenarios_dir / "scenario-b"
    s1.mkdir()
    s2.mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_scenarios", return_value=[s1]) as mock_select:
            result = find_scenarios(scenarios_dir, None)

    mock_select.assert_called_once()
    assert result == [s1]


def test_find_scenarios_interactive_includes_prefixed(tmp_path: Path) -> None:
    """find_scenarios includes _prefixed scenarios in interactive mode."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    s1 = scenarios_dir / "scenario-a"
    s2 = scenarios_dir / "_wip-scenario"
    s1.mkdir()
    s2.mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_scenarios", return_value=[s2]) as mock_select:
            result = find_scenarios(scenarios_dir, None)

    # Verify _prefixed was passed to selector
    call_args = mock_select.call_args[0][0]
    names = [p.name for p in call_args]
    assert "_wip-scenario" in names
    assert result == [s2]


def test_find_scenarios_interactive_cancelled(tmp_path: Path) -> None:
    """find_scenarios exits when interactive selection returns empty."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=True):
        with patch("skill_eval.cli.select_scenarios", return_value=[]):
            with pytest.raises(Exit):
                find_scenarios(scenarios_dir, None)


def test_find_scenarios_non_interactive_no_names_exits(tmp_path: Path) -> None:
    """find_scenarios exits in non-interactive mode without names or --all."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario-a").mkdir()

    with patch("skill_eval.cli.is_interactive", return_value=False):
        with pytest.raises(Exit):
            find_scenarios(scenarios_dir, None)


def test_find_evals_root_from_evals_dir(tmp_path: Path) -> None:
    """find_evals_root finds root when cwd is the evals directory."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    result = find_evals_root(tmp_path)
    assert result == tmp_path


def test_find_evals_root_from_subdirectory(tmp_path: Path) -> None:
    """find_evals_root finds root when cwd is a subdirectory."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    sub = tmp_path / "sub"
    sub.mkdir()
    result = find_evals_root(sub)
    assert result == tmp_path


def test_find_evals_root_from_repo_with_evals_subdir(tmp_path: Path) -> None:
    """find_evals_root finds evals/ when cwd is the repo root."""
    evals_dir = tmp_path / "evals"
    scenarios_dir = evals_dir / "scenarios"
    scenarios_dir.mkdir(parents=True)
    result = find_evals_root(tmp_path)
    assert result == evals_dir


def test_find_evals_root_returns_none_when_not_found(tmp_path: Path) -> None:
    """find_evals_root returns None when no scenarios/ directory found."""
    result = find_evals_root(tmp_path)
    assert result is None
