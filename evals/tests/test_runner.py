"""Tests for skill_eval runner."""

import json
from pathlib import Path

from skill_eval.runner import Runner


def test_runner_creates_output_directory(tmp_path: Path) -> None:
    """Runner creates timestamped output directory."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    assert run_dir.exists()
    assert run_dir.parent == evals_dir / "runs"
    assert len(run_dir.name) == 17  # e.g., 2025-01-15-103045 (with seconds)


def test_runner_prepares_isolated_environment(tmp_path: Path) -> None:
    """Runner creates isolated Claude config with only specified skills."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    # Create scenario dir with skill reference
    scenario_dir = evals_dir / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)

    # Create skill in repo (evals_dir parent simulates repo_dir)
    repo_dir = evals_dir.parent
    skill_dir = repo_dir / "skills" / "debug"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Debug skill v1")

    runner = Runner(evals_dir=evals_dir)
    env_dir, _ = runner.prepare_environment(
        scenario_dir=scenario_dir,
        context_dir=None,
        skills=["skills/debug/SKILL.md"],
    )

    claude_dir = env_dir / ".claude"
    assert claude_dir.exists()
    # Skill is copied using parent dir name: skills/debug/SKILL.md -> debug/SKILL.md
    skill_file = claude_dir / "skills" / "debug" / "SKILL.md"
    assert skill_file.exists()
    assert "Debug skill v1" in skill_file.read_text()


def test_runner_creates_mcp_config(tmp_path: Path) -> None:
    """Runner creates mcp-servers.json when mcp_servers provided."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)
    mcp_servers = {
        "dbt": {
            "command": "uvx",
            "args": ["dbt-mcp@latest"],
        }
    }

    env_dir, mcp_config_path = runner.prepare_environment(
        scenario_dir=scenario_dir,
        context_dir=None,
        skills=[],
        mcp_servers=mcp_servers,
    )

    assert mcp_config_path is not None
    assert mcp_config_path.exists()

    config = json.loads(mcp_config_path.read_text())
    assert "mcpServers" in config
    assert "dbt" in config["mcpServers"]
    assert config["mcpServers"]["dbt"]["command"] == "uvx"


def test_runner_copies_env_file_with_mcp(tmp_path: Path) -> None:
    """Runner copies .env file when mcp_servers are configured."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / ".env").write_text("DBT_TOKEN=secret123")

    runner = Runner(evals_dir=evals_dir)
    # .env is only copied when mcp_servers are provided
    mcp_servers = {"dbt": {"command": "uvx", "args": ["dbt-mcp"]}}

    env_dir, _ = runner.prepare_environment(
        scenario_dir=scenario_dir,
        context_dir=None,
        skills=[],
        mcp_servers=mcp_servers,
    )

    env_file = env_dir / ".env"
    assert env_file.exists()
    assert "DBT_TOKEN=secret123" in env_file.read_text()


def test_parse_json_output_extracts_metadata(tmp_path: Path) -> None:
    """NDJSON parser extracts metadata from stream-json output."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    runner = Runner(evals_dir=evals_dir)

    # Simulate stream-json output
    ndjson = """{"type":"system","subtype":"init","model":"claude-opus-4-5","skills":["debug"],"mcp_servers":[{"name":"dbt","status":"connected"}]}
{"type":"assistant","message":{"content":[{"type":"text","text":"I found the issue."}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","content":"file contents"}]}}
{"type":"result","subtype":"success","duration_ms":5000,"num_turns":2,"total_cost_usd":0.05,"usage":{"input_tokens":1000,"output_tokens":100}}"""

    result = runner._parse_json_output(ndjson)

    assert result["model"] == "claude-opus-4-5"
    assert result["skills_available"] == ["debug"]
    assert result["mcp_servers"] == [{"name": "dbt", "status": "connected"}]
    assert result["duration_ms"] == 5000
    assert result["num_turns"] == 2
    assert result["total_cost_usd"] == 0.05
    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 100
    assert "Read" in result["tools_used"]
    assert "I found the issue." in result["output_text"]


def test_parse_json_output_handles_empty_input(tmp_path: Path) -> None:
    """NDJSON parser handles empty input gracefully."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    runner = Runner(evals_dir=evals_dir)

    result = runner._parse_json_output("")

    assert result["output_text"] == ""
    assert result["tools_used"] == []
    assert result["skills_invoked"] == []
