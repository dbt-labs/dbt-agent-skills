"""Tests for skill_eval selector module."""

from pathlib import Path
from unittest.mock import patch

import yaml

from skill_eval.selector import (
    RunInfo,
    ScenarioInfo,
    is_interactive,
    select_run,
    select_scenarios,
)


class TestRunInfo:
    """Tests for RunInfo dataclass."""

    def test_from_path_basic(self, tmp_path: Path) -> None:
        """RunInfo.from_path creates info from a run directory."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()
        (run_dir / "scenario1").mkdir()
        (run_dir / "scenario2").mkdir()

        info = RunInfo.from_path(run_dir)

        assert info.path == run_dir
        assert info.name == "2024-01-15-120000"
        assert info.scenario_count == 2
        assert info.graded is False

    def test_from_path_with_grades(self, tmp_path: Path) -> None:
        """RunInfo detects graded status from grades.yaml."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()
        (run_dir / "grades.yaml").write_text("graded_at: 2024-01-15")

        info = RunInfo.from_path(run_dir)

        assert info.graded is True

    def test_from_path_ignores_hidden_dirs(self, tmp_path: Path) -> None:
        """RunInfo ignores hidden directories in scenario count."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()
        (run_dir / ".hidden").mkdir()
        (run_dir / "scenario1").mkdir()

        info = RunInfo.from_path(run_dir)

        assert info.scenario_count == 1

    def test_display_text_all_fields(self, tmp_path: Path) -> None:
        """display_text shows all available information."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()
        (run_dir / "scenario1").mkdir()
        (run_dir / "grades.yaml").write_text("graded_at: 2024-01-15")

        info = RunInfo.from_path(run_dir)
        display = info.display_text()

        assert "2024-01-15-120000" in display
        assert "1 scenario(s)" in display
        assert "graded" in display

    def test_display_text_minimal(self, tmp_path: Path) -> None:
        """display_text works with minimal information."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()

        info = RunInfo.from_path(run_dir)
        display = info.display_text()

        assert "2024-01-15-120000" in display
        assert "0 scenario(s)" in display
        assert "graded" not in display
        assert "$" not in display


class TestScenarioInfo:
    """Tests for ScenarioInfo dataclass."""

    def test_from_path_basic(self, tmp_path: Path) -> None:
        """ScenarioInfo.from_path creates info from a scenario directory."""
        scenario_dir = tmp_path / "my-scenario"
        scenario_dir.mkdir()

        skill_sets = {"sets": [{"name": "a"}, {"name": "b"}]}
        (scenario_dir / "skill-sets.yaml").write_text(yaml.dump(skill_sets))

        info = ScenarioInfo.from_path(scenario_dir)

        assert info.path == scenario_dir
        assert info.name == "my-scenario"
        assert info.skill_set_count == 2
        assert info.description == ""

    def test_from_path_with_description(self, tmp_path: Path) -> None:
        """ScenarioInfo extracts description from scenario.md."""
        scenario_dir = tmp_path / "my-scenario"
        scenario_dir.mkdir()
        (scenario_dir / "skill-sets.yaml").write_text(yaml.dump({"sets": []}))
        (scenario_dir / "scenario.md").write_text("# Title\n\nThis is the description.")

        info = ScenarioInfo.from_path(scenario_dir)

        assert info.description == "This is the description."

    def test_from_path_description_truncation(self, tmp_path: Path) -> None:
        """ScenarioInfo truncates long descriptions."""
        scenario_dir = tmp_path / "my-scenario"
        scenario_dir.mkdir()
        (scenario_dir / "skill-sets.yaml").write_text(yaml.dump({"sets": []}))

        long_desc = "A" * 100
        (scenario_dir / "scenario.md").write_text(long_desc)

        info = ScenarioInfo.from_path(scenario_dir)

        assert len(info.description) <= 63  # 60 chars + "..."
        assert info.description.endswith("...")

    def test_from_path_missing_files(self, tmp_path: Path) -> None:
        """ScenarioInfo handles missing files gracefully."""
        scenario_dir = tmp_path / "my-scenario"
        scenario_dir.mkdir()

        info = ScenarioInfo.from_path(scenario_dir)

        assert info.name == "my-scenario"
        assert info.skill_set_count == 0
        assert info.description == ""

    def test_display_text_all_fields(self, tmp_path: Path) -> None:
        """display_text shows all available information."""
        scenario_dir = tmp_path / "my-scenario"
        scenario_dir.mkdir()
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "a"}, {"name": "b"}]})
        )
        (scenario_dir / "scenario.md").write_text("Test description")

        info = ScenarioInfo.from_path(scenario_dir)
        display = info.display_text()

        assert "my-scenario" in display
        assert "2 skill set(s)" in display
        assert "Test description" in display


class TestIsInteractive:
    """Tests for is_interactive function."""

    def test_returns_true_when_tty(self) -> None:
        """is_interactive returns True when stdin is a TTY."""
        with patch("skill_eval.selector.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert is_interactive() is True

    def test_returns_false_when_not_tty(self) -> None:
        """is_interactive returns False when stdin is not a TTY."""
        with patch("skill_eval.selector.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            assert is_interactive() is False


class TestSelectRun:
    """Tests for select_run function."""

    def test_returns_none_for_empty_list(self) -> None:
        """select_run returns None when no runs provided."""
        result = select_run([])
        assert result is None

    def test_returns_single_run_without_prompt(self, tmp_path: Path) -> None:
        """select_run returns the only run without showing selector."""
        run_dir = tmp_path / "2024-01-15-120000"
        run_dir.mkdir()

        result = select_run([run_dir])

        assert result == run_dir


class TestSelectScenarios:
    """Tests for select_scenarios function."""

    def test_returns_empty_for_empty_list(self) -> None:
        """select_scenarios returns empty list when no scenarios provided."""
        result = select_scenarios([])
        assert result == []
