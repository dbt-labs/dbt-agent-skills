"""Tests for skill_eval grader."""

from pathlib import Path
from unittest.mock import patch

import yaml

from skill_eval.grader import (
    auto_grade_run,
    build_grading_prompt,
    call_claude_grader,
    compute_skill_usage,
    load_grades,
    parse_grade_response,
)
from skill_eval.models import Grade


def test_build_grading_prompt_includes_all_sections(tmp_path: Path) -> None:
    """Grading prompt includes task, criteria, output, tools, and files."""
    # Create scenario directory
    scenario_dir = tmp_path / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.md").write_text("# Test Scenario\n\nExpected: Fix the bug.")
    (scenario_dir / "prompt.txt").write_text("Please fix the bug in the code.")

    # Create output directory
    output_dir = tmp_path / "runs" / "run-1" / "test-scenario" / "skill-set-1"
    output_dir.mkdir(parents=True)
    (output_dir / "output.md").write_text("I found and fixed the bug.")
    (output_dir / "metadata.yaml").write_text(
        yaml.dump({
            "tools_used": ["Read", "Edit"],
            "skills_available": ["debugging"],
            "skills_invoked": [],
            "mcp_servers": [{"name": "dbt", "status": "connected"}],
        })
    )

    # Create modified files
    changes_dir = output_dir / "changes"
    changes_dir.mkdir()
    (changes_dir / "fixed_file.py").write_text("# fixed")

    prompt = build_grading_prompt(scenario_dir, output_dir)

    # Check all sections are present
    assert "Please fix the bug in the code." in prompt  # Task
    assert "Fix the bug" in prompt  # Criteria
    assert "I found and fixed the bug." in prompt  # Output
    assert "Read" in prompt  # Tools used
    assert "Edit" in prompt
    assert "debugging" in prompt  # Skills available
    assert "dbt" in prompt  # MCP server
    assert "fixed_file.py" in prompt  # Modified files


def test_build_grading_prompt_handles_missing_files(tmp_path: Path) -> None:
    """Grading prompt handles missing scenario/output files gracefully."""
    scenario_dir = tmp_path / "scenarios" / "empty"
    scenario_dir.mkdir(parents=True)

    output_dir = tmp_path / "runs" / "run-1" / "empty" / "skill-set"
    output_dir.mkdir(parents=True)

    prompt = build_grading_prompt(scenario_dir, output_dir)

    assert "No scenario description provided" in prompt
    assert "No prompt provided" in prompt
    assert "No output recorded" in prompt
    assert "No files modified" in prompt


def test_build_grading_prompt_shows_skills_availability(tmp_path: Path) -> None:
    """Grading prompt clearly shows available vs invoked skills."""
    scenario_dir = tmp_path / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "prompt.txt").write_text("Do something")

    output_dir = tmp_path / "runs" / "run-1" / "test" / "skill-set"
    output_dir.mkdir(parents=True)
    (output_dir / "output.md").write_text("Done")
    (output_dir / "metadata.yaml").write_text(
        yaml.dump({
            "tools_used": ["Skill"],
            "skills_available": ["skill-a", "skill-b"],
            "skills_invoked": ["skill-a"],
        })
    )

    prompt = build_grading_prompt(scenario_dir, output_dir)

    assert "Skills available:" in prompt
    assert "skill-a" in prompt
    assert "skill-b" in prompt
    assert "Skills actually invoked:" in prompt


def test_parse_grade_response_parses_yaml(tmp_path: Path) -> None:
    """Parser extracts grade fields from YAML response."""
    response = """success: true
score: 4
tool_usage: appropriate
notes: Good solution that used the right tools."""

    result = parse_grade_response(response)

    assert isinstance(result, Grade)
    assert result.success is True
    assert result.score == 4
    assert result.tool_usage == "appropriate"
    assert "Good solution" in result.notes


def test_parse_grade_response_handles_markdown_fences(tmp_path: Path) -> None:
    """Parser handles YAML wrapped in markdown code fences."""
    response = """Here's my grading:

```yaml
success: false
score: 2
tool_usage: partial
notes: Missed some requirements.
```

That's my assessment."""

    result = parse_grade_response(response)

    assert result.success is False
    assert result.score == 2
    assert result.tool_usage == "partial"


def test_parse_grade_response_handles_yml_fence(tmp_path: Path) -> None:
    """Parser handles ```yml fence variant."""
    response = """```yml
success: true
score: 5
tool_usage: appropriate
notes: Perfect.
```"""

    result = parse_grade_response(response)

    assert result.success is True
    assert result.score == 5


def test_parse_grade_response_handles_invalid_yaml(tmp_path: Path) -> None:
    """Parser returns error info for invalid YAML."""
    response = "This is not valid YAML: [unclosed"

    result = parse_grade_response(response)

    assert result.success is None
    assert result.score is None
    assert "parse" in result.notes.lower() or "error" in result.notes.lower()


def test_parse_grade_response_handles_non_dict_yaml(tmp_path: Path) -> None:
    """Parser handles YAML that parses to non-dict."""
    response = "- item1\n- item2"

    result = parse_grade_response(response)

    assert result.success is None
    assert "Failed to parse" in result.notes


def test_call_claude_grader_builds_correct_command(tmp_path: Path) -> None:
    """Claude grader calls CLI with correct arguments."""
    with patch("skill_eval.grader.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "success: true\nscore: 5"

        call_claude_grader("Test prompt")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "-p" in cmd
        assert "Test prompt" in cmd


def test_call_claude_grader_handles_timeout(tmp_path: Path) -> None:
    """Claude grader handles timeout gracefully."""
    import subprocess

    with patch("skill_eval.grader.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)

        result = call_claude_grader("Test prompt")

        assert "timeout" in result.lower()


def test_auto_grade_run_grades_all_combinations(tmp_path: Path) -> None:
    """Auto-grade processes all scenario/skill-set combinations."""
    # Setup scenarios
    scenarios_dir = tmp_path / "scenarios"
    for scenario in ["scenario-a", "scenario-b"]:
        s_dir = scenarios_dir / scenario
        s_dir.mkdir(parents=True)
        (s_dir / "scenario.md").write_text(f"# {scenario}")
        (s_dir / "prompt.txt").write_text(f"Task for {scenario}")

    # Setup run outputs
    run_dir = tmp_path / "runs" / "test-run"
    for scenario in ["scenario-a", "scenario-b"]:
        for skill_set in ["set-1", "set-2"]:
            out_dir = run_dir / scenario / skill_set
            out_dir.mkdir(parents=True)
            (out_dir / "output.md").write_text(f"Output for {scenario}/{skill_set}")
            (out_dir / "metadata.yaml").write_text(yaml.dump({"tools_used": ["Read"]}))

    # Mock Claude responses
    def mock_grader(prompt: str) -> str:
        return "success: true\nscore: 4\ntool_usage: appropriate\nnotes: Good"

    with patch("skill_eval.grader.call_claude_grader", side_effect=mock_grader):
        grades = auto_grade_run(run_dir, scenarios_dir)

    # Verify structure
    assert grades["grader"] == "claude-auto"
    assert "graded_at" in grades
    assert "scenario-a" in grades["results"]
    assert "scenario-b" in grades["results"]
    assert "set-1" in grades["results"]["scenario-a"]
    assert "set-2" in grades["results"]["scenario-a"]
    assert grades["results"]["scenario-a"]["set-1"]["success"] is True
    assert grades["results"]["scenario-a"]["set-1"]["score"] == 4


def test_auto_grade_run_skips_hidden_dirs(tmp_path: Path) -> None:
    """Auto-grade skips hidden directories like .DS_Store."""
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "test"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Do something")

    run_dir = tmp_path / "runs" / "test-run"
    # Create hidden dir that should be skipped
    (run_dir / ".DS_Store").mkdir(parents=True)
    # Create actual output
    out_dir = run_dir / "test" / "skill-set"
    out_dir.mkdir(parents=True)
    (out_dir / "output.md").write_text("Done")
    (out_dir / "metadata.yaml").write_text(yaml.dump({"tools_used": []}))

    with patch("skill_eval.grader.call_claude_grader", return_value="success: true\nscore: 3"):
        grades = auto_grade_run(run_dir, scenarios_dir)

    # Should only have 'test' scenario, not '.DS_Store'
    assert list(grades["results"].keys()) == ["test"]


# compute_skill_usage tests


def test_compute_skill_usage_calculates_percentage() -> None:
    """compute_skill_usage returns correct percentage when skills are used."""
    metadata = {
        "skills_available": ["skill-a", "skill-b", "skill-c"],
        "skills_invoked": ["skill-a", "skill-c"],
    }

    available, invoked, pct = compute_skill_usage(metadata)

    assert available == ["skill-a", "skill-b", "skill-c"]
    assert invoked == ["skill-a", "skill-c"]
    assert pct is not None
    assert abs(pct - 66.67) < 1  # 2/3 = ~66.67%


def test_compute_skill_usage_handles_no_skills_available() -> None:
    """compute_skill_usage returns None percentage when no skills available."""
    metadata = {"skills_available": [], "skills_invoked": []}

    available, invoked, pct = compute_skill_usage(metadata)

    assert available == []
    assert invoked == []
    assert pct is None


def test_compute_skill_usage_handles_missing_keys() -> None:
    """compute_skill_usage handles missing metadata keys."""
    metadata = {}

    available, invoked, pct = compute_skill_usage(metadata)

    assert available == []
    assert invoked == []
    assert pct is None


def test_compute_skill_usage_handles_all_skills_used() -> None:
    """compute_skill_usage returns 100% when all skills are used."""
    metadata = {
        "skills_available": ["skill-a", "skill-b"],
        "skills_invoked": ["skill-a", "skill-b"],
    }

    available, invoked, pct = compute_skill_usage(metadata)

    assert pct == 100.0


def test_compute_skill_usage_handles_extra_invocations() -> None:
    """compute_skill_usage handles skills invoked that weren't in available list."""
    metadata = {
        "skills_available": ["skill-a"],
        "skills_invoked": ["skill-a", "skill-external"],
    }

    available, invoked, pct = compute_skill_usage(metadata)

    assert invoked == ["skill-a", "skill-external"]
    assert pct == 100.0  # 1/1 available skill was used


def test_load_grades_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    """load_grades returns {} when grades.yaml doesn't exist."""
    assert load_grades(tmp_path) == {}


def test_load_grades_returns_empty_dict_for_empty_file(tmp_path: Path) -> None:
    """An empty grades.yaml (parses to None) doesn't crash load_grades."""
    (tmp_path / "grades.yaml").write_text("")

    assert load_grades(tmp_path) == {}


def test_load_grades_returns_empty_dict_for_non_mapping_yaml(tmp_path: Path) -> None:
    """A grades.yaml that parses to a list, not a mapping, doesn't crash load_grades."""
    (tmp_path / "grades.yaml").write_text("- oops\n- not\n- a\n- mapping\n")

    assert load_grades(tmp_path) == {}


def test_load_grades_returns_valid_grades(tmp_path: Path) -> None:
    """A well-formed grades.yaml is returned as-is."""
    grades = {"graded_at": "2026-01-01", "grader": "human", "results": {"a": {"b": {"success": True}}}}
    (tmp_path / "grades.yaml").write_text(yaml.dump(grades))

    assert load_grades(tmp_path) == grades
