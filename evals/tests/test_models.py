"""Tests for skill_eval data models."""

from pathlib import Path

from skill_eval.models import load_scenario


def test_load_scenario_parses_skill_sets(tmp_path: Path) -> None:
    """Scenario loads skill-sets.yaml correctly."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Fix the bug")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: no-skills
    skills: []
  - name: with-debug
    skills:
      - debugging-dbt-errors/baseline.md
"""
    )

    scenario = load_scenario(scenario_dir)

    assert scenario.name == "test-scenario"
    assert scenario.prompt == "Fix the bug"
    assert len(scenario.skill_sets) == 2
    assert scenario.skill_sets[0].name == "no-skills"
    assert scenario.skill_sets[0].skills == []
    assert scenario.skill_sets[1].name == "with-debug"
    assert scenario.skill_sets[1].skills == ["debugging-dbt-errors/baseline.md"]


def test_load_scenario_parses_mcp_servers(tmp_path: Path) -> None:
    """Scenario loads mcp_servers from skill-sets.yaml."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Debug job")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: with-mcp
    skills: []
    mcp_servers:
      dbt:
        command: uvx
        args:
          - --env-file
          - .env
          - dbt-mcp@latest
"""
    )

    scenario = load_scenario(scenario_dir)

    assert len(scenario.skill_sets) == 1
    skill_set = scenario.skill_sets[0]
    assert skill_set.name == "with-mcp"
    assert "dbt" in skill_set.mcp_servers
    assert skill_set.mcp_servers["dbt"]["command"] == "uvx"
    assert "--env-file" in skill_set.mcp_servers["dbt"]["args"]


def test_load_scenario_parses_allowed_tools(tmp_path: Path) -> None:
    """Scenario loads allowed_tools from skill-sets.yaml."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Fix bug")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: restricted
    skills: []
    allowed_tools:
      - Read
      - Glob
      - Grep
      - Bash(git:*)
"""
    )

    scenario = load_scenario(scenario_dir)

    skill_set = scenario.skill_sets[0]
    assert skill_set.allowed_tools == ["Read", "Glob", "Grep", "Bash(git:*)"]


def test_load_scenario_parses_extra_prompt(tmp_path: Path) -> None:
    """Scenario loads extra_prompt from skill-sets.yaml."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Fix the bug")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: no-extra
    skills: []
  - name: with-extra
    skills: []
    extra_prompt: Check if any skill can help with this task.
"""
    )

    scenario = load_scenario(scenario_dir)

    assert scenario.skill_sets[0].extra_prompt == ""
    assert scenario.skill_sets[1].extra_prompt == "Check if any skill can help with this task."


def test_load_scenario_parses_setup_commands(tmp_path: Path) -> None:
    """Scenario loads setup commands from skill-sets.yaml."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Fix the bug")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: no-setup
    skills: []
  - name: with-setup
    setup:
      - npx @anthropic-ai/claude-code-skills add https://example.com/skill
      - echo "ready"
    skills: []
"""
    )

    scenario = load_scenario(scenario_dir)

    assert scenario.skill_sets[0].setup == []
    assert scenario.skill_sets[1].setup == [
        "npx @anthropic-ai/claude-code-skills add https://example.com/skill",
        'echo "ready"',
    ]


def test_load_scenario_parses_multiline_extra_prompt(tmp_path: Path) -> None:
    """Scenario loads multiline extra_prompt using YAML block scalar."""
    scenario_dir = tmp_path / "test-scenario"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.md").write_text("# Test")
    (scenario_dir / "prompt.txt").write_text("Debug this")
    (scenario_dir / "skill-sets.yaml").write_text(
        """
sets:
  - name: with-multiline
    skills: []
    extra_prompt: |
      Before starting:
      1. Check if any skill can help
      2. Use the MCP server if available
"""
    )

    scenario = load_scenario(scenario_dir)

    extra = scenario.skill_sets[0].extra_prompt
    assert "Before starting:" in extra
    assert "1. Check if any skill can help" in extra
    assert "2. Use the MCP server if available" in extra
