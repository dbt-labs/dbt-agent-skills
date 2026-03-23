"""Integration tests for CLI commands using Typer's CliRunner."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from skill_eval.cli import app

runner = CliRunner()


class TestRunCommand:
    """Tests for the 'run' command."""

    def test_run_requires_scenario_or_all(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command errors when no scenario specified and not interactive."""
        monkeypatch.chdir(tmp_path)
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()
        (scenarios_dir / "test-scenario").mkdir()

        with patch("skill_eval.cli.is_interactive", return_value=False):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1
        assert "Specify scenario names or use --all" in result.output

    def test_run_with_all_flag(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command with --all runs all scenarios."""
        monkeypatch.chdir(tmp_path)

        # Create scenario
        scenarios_dir = tmp_path / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "prompt.txt").write_text("Do something")
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "baseline", "skills": []}]})
        )

        # Mock the runner to avoid actually running Claude
        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = tmp_path / "runs" / "test-run"
            mock_runner.run_scenario.return_value = MagicMock(success=True, error=None)

            result = runner.invoke(app, ["run", "--all"])

        assert result.exit_code == 0
        assert "Run directory:" in result.output
        mock_runner.run_scenario.assert_called()

    def test_run_with_specific_scenario(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command with scenario name runs that scenario."""
        monkeypatch.chdir(tmp_path)

        # Create scenario
        scenarios_dir = tmp_path / "scenarios"
        scenario_dir = scenarios_dir / "my-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "prompt.txt").write_text("Do something")
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "baseline", "skills": []}]})
        )

        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = tmp_path / "runs" / "test-run"
            mock_runner.run_scenario.return_value = MagicMock(success=True, error=None)

            result = runner.invoke(app, ["run", "my-scenario"])

        assert result.exit_code == 0
        mock_runner.run_scenario.assert_called_once()

    def test_run_parallel_flag(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command with --parallel uses parallel execution."""
        monkeypatch.chdir(tmp_path)

        # Create scenario
        scenarios_dir = tmp_path / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "prompt.txt").write_text("Do something")
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "set1"}, {"name": "set2"}]})
        )

        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = tmp_path / "runs" / "test-run"
            mock_runner.run_parallel.return_value = []

            result = runner.invoke(app, ["run", "--all", "--parallel"])

        assert result.exit_code == 0
        mock_runner.run_parallel.assert_called_once()

    def test_run_includes_prefixed_scenarios(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command includes _prefixed scenarios."""
        monkeypatch.chdir(tmp_path)

        scenarios_dir = tmp_path / "scenarios"
        for name in ["regular", "_sensitive"]:
            d = scenarios_dir / name
            d.mkdir(parents=True)
            (d / "prompt.txt").write_text("Do something")
            (d / "skill-sets.yaml").write_text(yaml.dump({"sets": [{"name": "baseline"}]}))

        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = tmp_path / "runs" / "test-run"
            mock_runner.run_scenario.return_value = MagicMock(success=True, error=None)

            result = runner.invoke(app, ["run", "--all"])

        assert result.exit_code == 0
        # Should have run both scenarios
        assert mock_runner.run_scenario.call_count == 2


class TestGradeCommand:
    """Tests for the 'grade' command."""

    def test_grade_manual_creates_grades_file(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """grade command without --auto creates grades.yaml template."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        # Create run directory structure
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        skill_set_dir = run_dir / "test-scenario" / "skill-set-1"
        skill_set_dir.mkdir(parents=True)
        (skill_set_dir / "output.md").write_text("Test output")

        with patch("skill_eval.cli.is_interactive", return_value=False):
            result = runner.invoke(app, ["grade"])

        assert result.exit_code == 0
        assert "Grades file:" in result.output
        assert (run_dir / "grades.yaml").exists()

    def test_grade_with_run_id(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """grade command with run_id uses that run."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        for name in ["2024-01-01-100000", "2024-01-02-100000"]:
            run_dir = runs_dir / name
            skill_set_dir = run_dir / "test-scenario" / "skill-set-1"
            skill_set_dir.mkdir(parents=True)
            (skill_set_dir / "output.md").write_text("Output")

        result = runner.invoke(app, ["grade", "01-01"])

        assert result.exit_code == 0
        assert "2024-01-01-100000" in result.output

    def test_grade_latest_flag(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """grade --latest uses most recent run without prompting."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        for name in ["2024-01-01-100000", "2024-01-02-100000"]:
            run_dir = runs_dir / name
            skill_set_dir = run_dir / "scenario" / "skill-set"
            skill_set_dir.mkdir(parents=True)
            (skill_set_dir / "output.md").write_text("Output")

        result = runner.invoke(app, ["grade", "--latest"])

        assert result.exit_code == 0
        assert "2024-01-02-100000" in result.output

    def test_grade_auto_calls_grader(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """grade --auto calls Claude grader for each output."""
        monkeypatch.chdir(tmp_path)

        # Create scenario
        scenarios_dir = tmp_path / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "scenario.md").write_text("# Test")
        (scenario_dir / "prompt.txt").write_text("Do something")

        # Create run output
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        skill_set_dir = run_dir / "test-scenario" / "skill-set-1"
        skill_set_dir.mkdir(parents=True)
        (skill_set_dir / "output.md").write_text("I did the thing")
        (skill_set_dir / "metadata.yaml").write_text(
            yaml.dump({"skills_available": ["skill-a"], "skills_invoked": ["skill-a"]})
        )

        with patch("skill_eval.grader.call_claude_grader") as mock_grader:
            mock_grader.return_value = "success: true\nscore: 4\ntool_usage: appropriate\nnotes: Good"

            with patch("skill_eval.cli.is_interactive", return_value=False):
                result = runner.invoke(app, ["grade", "--auto"])

        assert result.exit_code == 0
        mock_grader.assert_called_once()
        assert (run_dir / "grades.yaml").exists()

    def test_grade_auto_computes_skill_usage(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """grade --auto computes skill usage from metadata."""
        monkeypatch.chdir(tmp_path)

        scenarios_dir = tmp_path / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "scenario.md").write_text("# Test")
        (scenario_dir / "prompt.txt").write_text("Do something")

        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        skill_set_dir = run_dir / "test-scenario" / "skill-set-1"
        skill_set_dir.mkdir(parents=True)
        (skill_set_dir / "output.md").write_text("Done")
        (skill_set_dir / "metadata.yaml").write_text(
            yaml.dump({
                "skills_available": ["skill-a", "skill-b"],
                "skills_invoked": ["skill-a"],
            })
        )

        with patch("skill_eval.grader.call_claude_grader") as mock_grader:
            mock_grader.return_value = "success: true\nscore: 4"

            with patch("skill_eval.cli.is_interactive", return_value=False):
                result = runner.invoke(app, ["grade", "--auto"])

        assert result.exit_code == 0

        # Check grades.yaml has skill usage data
        grades = yaml.safe_load((run_dir / "grades.yaml").read_text())
        grade_data = grades["results"]["test-scenario"]["skill-set-1"]
        assert grade_data["skills_available"] == ["skill-a", "skill-b"]
        assert grade_data["skills_invoked"] == ["skill-a"]
        assert grade_data["skill_usage_pct"] == 50.0


class TestReportCommand:
    """Tests for the 'report' command."""

    def test_report_generates_output(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """report command generates report file."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        # Create run with grades
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        skill_set_dir = run_dir / "test-scenario" / "skill-set-1"
        skill_set_dir.mkdir(parents=True)
        (skill_set_dir / "output.md").write_text("Output")
        (skill_set_dir / "metadata.yaml").write_text(yaml.dump({"tools_used": ["Read"]}))
        (run_dir / "grades.yaml").write_text(
            yaml.dump({
                "graded_at": "2024-01-15",
                "grader": "human",
                "results": {
                    "test-scenario": {
                        "skill-set-1": {"success": True, "score": 4}
                    }
                },
            })
        )

        with patch("skill_eval.cli.is_interactive", return_value=False):
            result = runner.invoke(app, ["report"])

        assert result.exit_code == 0
        assert "Saved to:" in result.output

        # Check reports directory was created
        reports_dir = tmp_path / "reports"
        assert reports_dir.exists()

    def test_report_latest_flag(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """report --latest uses most recent run."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        for name in ["2024-01-01-100000", "2024-01-02-100000"]:
            run_dir = runs_dir / name
            ss_dir = run_dir / "scenario" / "skill-set"
            ss_dir.mkdir(parents=True)
            (ss_dir / "output.md").write_text("Output")
            (ss_dir / "metadata.yaml").write_text(yaml.dump({}))
            (run_dir / "grades.yaml").write_text(
                yaml.dump({"results": {"scenario": {"skill-set": {"success": True}}}})
            )

        result = runner.invoke(app, ["report", "--latest"])

        assert result.exit_code == 0
        assert "2024-01-02-100000" in result.output


class TestReviewCommand:
    """Tests for the 'review' command."""

    def test_review_finds_transcripts(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """review command finds and reports transcript files."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        transcript_dir = run_dir / "test-scenario" / "skill-set-1" / "transcript"
        transcript_dir.mkdir(parents=True)
        (transcript_dir / "index.html").write_text("<html></html>")

        with patch("skill_eval.cli.is_interactive", return_value=False):
            with patch("webbrowser.open") as mock_open:
                result = runner.invoke(app, ["review"])

        assert result.exit_code == 0
        assert "Opening 1 transcript" in result.output
        mock_open.assert_called_once()

    def test_review_no_transcripts_errors(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """review command errors when no transcripts found."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        run_dir.mkdir(parents=True)

        with patch("skill_eval.cli.is_interactive", return_value=False):
            result = runner.invoke(app, ["review"])

        assert result.exit_code == 1
        assert "No transcripts found" in result.output

    def test_review_latest_flag(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """review --latest uses most recent run."""
        monkeypatch.chdir(tmp_path)

        # Create scenarios dir so find_evals_root can locate evals root
        (tmp_path / "scenarios").mkdir()

        runs_dir = tmp_path / "runs"
        for name in ["2024-01-01-100000", "2024-01-02-100000"]:
            run_dir = runs_dir / name
            transcript_dir = run_dir / "scenario" / "skill-set" / "transcript"
            transcript_dir.mkdir(parents=True)
            (transcript_dir / "index.html").write_text("<html></html>")

        with patch("webbrowser.open"):
            result = runner.invoke(app, ["review", "--latest"])

        assert result.exit_code == 0
        assert "2024-01-02-100000" in result.output


class TestRootDiscovery:
    """Tests that commands find evals root automatically."""

    def test_run_finds_evals_root_from_parent(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command works when cwd is parent of evals dir."""
        evals_dir = tmp_path / "evals"
        scenarios_dir = evals_dir / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "prompt.txt").write_text("Do something")
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "baseline", "skills": []}]})
        )

        monkeypatch.chdir(tmp_path)

        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = evals_dir / "runs" / "test-run"
            mock_runner.run_scenario.return_value = MagicMock(success=True, error=None)

            result = runner.invoke(app, ["run", "--all"])

        assert result.exit_code == 0
        mock_runner.run_scenario.assert_called()


class TestNewCommand:
    """Tests for the 'new' command."""

    def test_new_creates_scenario(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command creates scenario directory with all template files."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios").mkdir()

        result = runner.invoke(app, ["new", "my-test-scenario"])

        assert result.exit_code == 0
        scenario_dir = tmp_path / "scenarios" / "my-test-scenario"
        assert scenario_dir.exists()
        assert (scenario_dir / "skill-sets.yaml").exists()
        assert (scenario_dir / "scenario.md").exists()
        assert (scenario_dir / "prompt.txt").exists()
        assert (scenario_dir / ".env").exists()
        assert "Created scenario" in result.output

    def test_new_shows_files_to_edit(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command prints summary of files to edit."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios").mkdir()

        result = runner.invoke(app, ["new", "my-test"])

        assert "prompt.txt" in result.output
        assert "scenario.md" in result.output
        assert "skill-sets.yaml" in result.output
        assert ".env" in result.output

    def test_new_rejects_invalid_name(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command rejects invalid scenario names."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios").mkdir()

        result = runner.invoke(app, ["new", "My_Scenario"])

        assert result.exit_code == 1

    def test_new_errors_if_exists(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command errors when scenario already exists."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios" / "existing").mkdir(parents=True)

        result = runner.invoke(app, ["new", "existing"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_new_with_context_file(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command copies context file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios").mkdir()
        src = tmp_path / "models.yml"
        src.write_text("version: 2")

        result = runner.invoke(app, ["new", "my-test", "--context", str(src)])

        assert result.exit_code == 0
        assert (tmp_path / "scenarios" / "my-test" / "context" / "models.yml").exists()

    def test_new_with_context_directory(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command copies context directory tree."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "scenarios").mkdir()
        models = tmp_path / "models"
        models.mkdir()
        (models / "a.sql").write_text("SELECT 1")

        result = runner.invoke(app, ["new", "my-test", "--context", str(models)])

        assert result.exit_code == 0
        assert (tmp_path / "scenarios" / "my-test" / "context" / "models" / "a.sql").exists()

    def test_new_with_base_dir(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command uses --base-dir when provided."""
        custom_dir = tmp_path / "custom"
        (custom_dir / "scenarios").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["new", "my-test", "--base-dir", str(custom_dir)])

        assert result.exit_code == 0
        assert (custom_dir / "scenarios" / "my-test" / "scenario.md").exists()


class TestBaseDirOption:
    """Tests that --base-dir works across commands."""

    def test_new_defaults_to_cwd_evals(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """new command defaults to cwd/evals/ when no evals root found."""
        monkeypatch.chdir(tmp_path)
        # No scenarios/ directory exists anywhere

        result = runner.invoke(app, ["new", "my-test"])

        assert result.exit_code == 0
        assert (tmp_path / "evals" / "scenarios" / "my-test" / "scenario.md").exists()

    def test_run_with_base_dir(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """run command uses --base-dir when provided."""
        custom_dir = tmp_path / "custom-evals"
        scenarios_dir = custom_dir / "scenarios"
        scenario_dir = scenarios_dir / "test-scenario"
        scenario_dir.mkdir(parents=True)
        (scenario_dir / "prompt.txt").write_text("Do something")
        (scenario_dir / "skill-sets.yaml").write_text(
            yaml.dump({"sets": [{"name": "baseline", "skills": []}]})
        )
        monkeypatch.chdir(tmp_path)

        with patch("skill_eval.runner.Runner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.create_run_dir.return_value = custom_dir / "runs" / "test-run"
            mock_runner.run_scenario.return_value = MagicMock(success=True, error=None)

            result = runner.invoke(app, ["run", "--all", "--base-dir", str(custom_dir)])

        assert result.exit_code == 0
        mock_runner.run_scenario.assert_called()

    def test_review_with_base_dir(self, tmp_path: Path, monkeypatch: MagicMock) -> None:
        """review command uses --base-dir when provided."""
        custom_dir = tmp_path / "my-evals"
        runs_dir = custom_dir / "runs"
        run_dir = runs_dir / "2024-01-15-120000"
        transcript_dir = run_dir / "scenario" / "skill-set" / "transcript"
        transcript_dir.mkdir(parents=True)
        (transcript_dir / "index.html").write_text("<html></html>")
        monkeypatch.chdir(tmp_path)

        with patch("webbrowser.open"):
            result = runner.invoke(app, ["review", "--base-dir", str(custom_dir)])

        assert result.exit_code == 0
        assert "Opening 1 transcript" in result.output


class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_shows_version(self) -> None:
        """--version shows the version number."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "skill-eval" in result.output
