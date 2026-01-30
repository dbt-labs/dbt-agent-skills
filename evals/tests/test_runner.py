"""Tests for skill_eval runner."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_runner_prepares_environment_with_folder_path(tmp_path: Path) -> None:
    """Runner copies entire skill folder when given a directory path."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    scenario_dir = evals_dir / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)

    # Create skill folder with SKILL.md and supporting files
    repo_dir = evals_dir.parent
    skill_dir = repo_dir / "skills" / "fetch-docs"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Fetch docs skill")
    (skill_dir / "helper.sh").write_text("#!/bin/bash\necho 'helper'")

    runner = Runner(evals_dir=evals_dir)
    env_dir, _ = runner.prepare_environment(
        scenario_dir=scenario_dir,
        context_dir=None,
        skills=["skills/fetch-docs"],  # Folder path, not SKILL.md
    )

    claude_dir = env_dir / ".claude"
    # Skill folder is copied using folder name
    skill_dest = claude_dir / "skills" / "fetch-docs"
    assert skill_dest.exists()
    assert (skill_dest / "SKILL.md").exists()
    assert "Fetch docs skill" in (skill_dest / "SKILL.md").read_text()
    # Supporting files are also copied
    assert (skill_dest / "helper.sh").exists()
    assert "helper" in (skill_dest / "helper.sh").read_text()


def test_runner_is_url_detection(tmp_path: Path) -> None:
    """Runner correctly identifies HTTP(S) URLs."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    runner = Runner(evals_dir=evals_dir)

    # Should be detected as URLs
    assert runner._is_url("https://example.com/skills/my-skill/SKILL.md")
    assert runner._is_url("http://example.com/skills/my-skill/SKILL.md")
    assert runner._is_url("https://raw.githubusercontent.com/org/repo/main/skills/SKILL.md")
    assert runner._is_url("https://github.com/org/repo/blob/main/skills/SKILL.md")

    # Should NOT be detected as URLs
    assert not runner._is_url("skills/fetching-dbt-docs")
    assert not runner._is_url("skills/debug")
    assert not runner._is_url("/absolute/path/SKILL.md")
    assert not runner._is_url("")


def test_runner_normalizes_github_blob_urls(tmp_path: Path) -> None:
    """Runner converts GitHub blob URLs to raw URLs."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    runner = Runner(evals_dir=evals_dir)

    # GitHub blob URL should be converted
    blob_url = "https://github.com/org/repo/blob/main/skills/my-skill/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/org/repo/main/skills/my-skill/SKILL.md"
    assert runner._normalize_github_url(blob_url) == raw_url

    # Different branch
    blob_url = "https://github.com/org/repo/blob/feature-branch/path/to/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/org/repo/feature-branch/path/to/SKILL.md"
    assert runner._normalize_github_url(blob_url) == raw_url

    # Tag
    blob_url = "https://github.com/org/repo/blob/v1.2.3/skills/my-skill/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/org/repo/v1.2.3/skills/my-skill/SKILL.md"
    assert runner._normalize_github_url(blob_url) == raw_url

    # Commit SHA
    blob_url = "https://github.com/org/repo/blob/abc123def456/skills/my-skill/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/org/repo/abc123def456/skills/my-skill/SKILL.md"
    assert runner._normalize_github_url(blob_url) == raw_url

    # Already raw URL should be unchanged
    raw_url = "https://raw.githubusercontent.com/org/repo/main/skills/SKILL.md"
    assert runner._normalize_github_url(raw_url) == raw_url

    # Non-GitHub URL should be unchanged
    other_url = "https://example.com/skills/my-skill/SKILL.md"
    assert runner._normalize_github_url(other_url) == other_url


def test_runner_downloads_skill_from_url(tmp_path: Path) -> None:
    """Runner downloads skill from HTTP URL."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)

    # Mock urllib.request.urlopen
    skill_content = "# Downloaded Skill\n\nThis is a test skill."
    mock_response = MagicMock()
    mock_response.read.return_value = skill_content.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            skills=["https://example.com/skills/my-skill/SKILL.md"],
        )

        # Verify urlopen was called with correct URL
        mock_urlopen.assert_called_once_with(
            "https://example.com/skills/my-skill/SKILL.md",
            timeout=30,
        )

        # Verify skill was saved correctly
        skill_file = env_dir / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert skill_file.exists()
        assert "Downloaded Skill" in skill_file.read_text()


def test_runner_downloads_skill_from_raw_github_url(tmp_path: Path) -> None:
    """Runner downloads skill from raw GitHub URL."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)

    skill_content = "# GitHub Skill"
    mock_response = MagicMock()
    mock_response.read.return_value = skill_content.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            skills=["https://raw.githubusercontent.com/org/repo/main/skills/github-skill/SKILL.md"],
        )

        mock_urlopen.assert_called_once_with(
            "https://raw.githubusercontent.com/org/repo/main/skills/github-skill/SKILL.md",
            timeout=30,
        )

        # Skill name extracted from parent folder in URL path
        skill_file = env_dir / ".claude" / "skills" / "github-skill" / "SKILL.md"
        assert skill_file.exists()
        assert "GitHub Skill" in skill_file.read_text()


def test_runner_downloads_skill_from_github_blob_url(tmp_path: Path) -> None:
    """Runner converts GitHub blob URL to raw and downloads."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)

    skill_content = "# Blob Skill"
    mock_response = MagicMock()
    mock_response.read.return_value = skill_content.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            # GitHub blob URL (not raw)
            skills=["https://github.com/org/repo/blob/main/skills/blob-skill/SKILL.md"],
        )

        # Should be converted to raw URL
        mock_urlopen.assert_called_once_with(
            "https://raw.githubusercontent.com/org/repo/main/skills/blob-skill/SKILL.md",
            timeout=30,
        )

        skill_file = env_dir / ".claude" / "skills" / "blob-skill" / "SKILL.md"
        assert skill_file.exists()
        assert "Blob Skill" in skill_file.read_text()


def test_runner_downloads_root_level_skill_uses_hostname(tmp_path: Path) -> None:
    """Runner uses hostname as folder name for root-level skills."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)

    skill_content = "# Root Skill"
    mock_response = MagicMock()
    mock_response.read.return_value = skill_content.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response):
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            skills=["https://example.com/SKILL.md"],
        )

        # Uses hostname (dots replaced with dashes) as folder name
        skill_file = env_dir / ".claude" / "skills" / "example-com" / "SKILL.md"
        assert skill_file.exists()


def test_runner_downloads_github_root_skill_uses_repo_name(tmp_path: Path) -> None:
    """Runner uses repo name for GitHub root-level skills."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    runner = Runner(evals_dir=evals_dir)

    skill_content = "# GitHub Root Skill"
    mock_response = MagicMock()
    mock_response.read.return_value = skill_content.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response):
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            # GitHub blob URL at repo root
            skills=["https://github.com/myorg/my-repo/blob/main/SKILL.md"],
        )

        # Uses repo name as folder
        skill_file = env_dir / ".claude" / "skills" / "my-repo" / "SKILL.md"
        assert skill_file.exists()


def test_runner_mixes_local_and_url_skills(tmp_path: Path) -> None:
    """Runner handles mix of local and URL skills."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    scenario_dir = evals_dir / "scenarios" / "test"
    scenario_dir.mkdir(parents=True)

    # Create local skill
    repo_dir = evals_dir.parent
    local_skill_dir = repo_dir / "skills" / "local-skill"
    local_skill_dir.mkdir(parents=True)
    (local_skill_dir / "SKILL.md").write_text("# Local Skill")

    runner = Runner(evals_dir=evals_dir)

    # Mock for URL skill
    mock_response = MagicMock()
    mock_response.read.return_value = b"# Remote Skill"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("skill_eval.runner.urllib.request.urlopen", return_value=mock_response):
        env_dir, _ = runner.prepare_environment(
            scenario_dir=scenario_dir,
            context_dir=None,
            skills=[
                "skills/local-skill/SKILL.md",  # Local
                "https://example.com/skills/remote-skill/SKILL.md",  # URL
            ],
        )

        # Both skills should be present
        local_file = env_dir / ".claude" / "skills" / "local-skill" / "SKILL.md"
        remote_file = env_dir / ".claude" / "skills" / "remote-skill" / "SKILL.md"

        assert local_file.exists()
        assert "Local Skill" in local_file.read_text()
        assert remote_file.exists()
        assert "Remote Skill" in remote_file.read_text()


def test_generate_transcript_replaces_titles(tmp_path: Path) -> None:
    """Transcript generation replaces default titles with scenario/skill set info."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    # Create mock environment directory with session file
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    claude_projects = env_dir / ".claude" / "projects" / "abc123"
    claude_projects.mkdir(parents=True)
    session_file = claude_projects / "session.jsonl"
    session_file.write_text('{"type":"user","message":{"content":"test"}}\n')

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    runner = Runner(evals_dir=evals_dir)

    # Mock generate_html to create fake transcript files matching real library output
    def mock_generate_html(json_path: Path, transcript_dir: Path) -> None:
        transcript_dir.mkdir(parents=True, exist_ok=True)
        # Create index.html with default title (matches claude_code_transcripts output)
        (transcript_dir / "index.html").write_text(
            "<html><head><title>Claude Code transcript - Index</title></head>"
            "<body><h1>Claude Code transcript</h1></body></html>"
        )
        # Create page-001.html with page title and anchor in h1
        (transcript_dir / "page-001.html").write_text(
            "<html><head><title>Claude Code transcript - page 1</title></head>"
            '<body><h1><a href="index.html">Claude Code transcript</a> - page 1/1</h1></body></html>'
        )

    with patch("skill_eval.runner.generate_html", side_effect=mock_generate_html):
        runner._generate_transcript(env_dir, output_dir, "my-scenario", "test-skill-set")

    transcript_dir = output_dir / "transcript"

    # Check index.html - title and h1 should be replaced
    index_content = (transcript_dir / "index.html").read_text()
    assert "<title>my-scenario / test-skill-set - Index</title>" in index_content
    assert "<h1>my-scenario / test-skill-set</h1>" in index_content

    # Check page-001.html - title and h1 (with anchor) should be replaced
    page_content = (transcript_dir / "page-001.html").read_text()
    assert "<title>my-scenario / test-skill-set - page 1</title>" in page_content
    assert ">my-scenario / test-skill-set</a>" in page_content


def test_generate_transcript_handles_missing_session(tmp_path: Path) -> None:
    """Transcript generation handles missing session file gracefully."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    env_dir = tmp_path / "env"
    env_dir.mkdir()
    # No .claude/projects directory

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    runner = Runner(evals_dir=evals_dir)

    # Should not raise, just return early
    runner._generate_transcript(env_dir, output_dir, "scenario", "skill-set")

    # No transcript directory created
    assert not (output_dir / "transcript").exists()


def test_generate_transcript_handles_empty_projects_dir(tmp_path: Path) -> None:
    """Transcript generation handles empty projects directory."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    env_dir = tmp_path / "env"
    env_dir.mkdir()
    claude_projects = env_dir / ".claude" / "projects"
    claude_projects.mkdir(parents=True)
    # Empty projects directory (no session files)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    runner = Runner(evals_dir=evals_dir)

    # Should not raise, just return early
    runner._generate_transcript(env_dir, output_dir, "scenario", "skill-set")

    # No transcript directory created
    assert not (output_dir / "transcript").exists()


def test_run_parallel_executes_all_tasks(tmp_path: Path) -> None:
    """Parallel runner executes all tasks and returns results."""
    from skill_eval.models import Scenario, SkillSet
    from skill_eval.runner import RunTask

    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    # Create mock scenarios and skill sets
    scenario1 = Scenario(
        name="scenario-1",
        path=tmp_path / "scenarios" / "scenario-1",
        prompt="Test prompt 1",
        skill_sets=[],
    )
    scenario2 = Scenario(
        name="scenario-2",
        path=tmp_path / "scenarios" / "scenario-2",
        prompt="Test prompt 2",
        skill_sets=[],
    )

    skill_set1 = SkillSet(name="skill-set-1", skills=[])
    skill_set2 = SkillSet(name="skill-set-2", skills=[])

    tasks = [
        RunTask(scenario=scenario1, skill_set=skill_set1, run_dir=run_dir),
        RunTask(scenario=scenario1, skill_set=skill_set2, run_dir=run_dir),
        RunTask(scenario=scenario2, skill_set=skill_set1, run_dir=run_dir),
    ]

    # Mock run_scenario to return success
    def mock_run_scenario(scenario, skill_set, run_dir):
        from skill_eval.runner import RunResult
        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output="Test output",
            success=True,
        )

    with patch.object(runner, "run_scenario", side_effect=mock_run_scenario):
        results = runner.run_parallel(tasks, max_workers=2)

    assert len(results) == 3
    assert all(r.success for r in results)
    # Check all scenario/skill-set combinations are present
    result_keys = {(r.scenario_name, r.skill_set_name) for r in results}
    assert result_keys == {
        ("scenario-1", "skill-set-1"),
        ("scenario-1", "skill-set-2"),
        ("scenario-2", "skill-set-1"),
    }


def test_run_parallel_calls_progress_callback(tmp_path: Path) -> None:
    """Parallel runner calls progress callback for each completed task."""
    from skill_eval.models import Scenario, SkillSet
    from skill_eval.runner import RunTask

    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    scenario = Scenario(
        name="test-scenario",
        path=tmp_path / "scenarios" / "test",
        prompt="Test",
        skill_sets=[],
    )

    tasks = [
        RunTask(scenario=scenario, skill_set=SkillSet(name=f"set-{i}", skills=[]), run_dir=run_dir)
        for i in range(3)
    ]

    callback_calls = []

    def on_complete(task, result):
        callback_calls.append((task.skill_set.name, result.success))

    def mock_run_scenario(scenario, skill_set, run_dir):
        from skill_eval.runner import RunResult
        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output="",
            success=True,
        )

    with patch.object(runner, "run_scenario", side_effect=mock_run_scenario):
        runner.run_parallel(tasks, max_workers=2, progress_callback=on_complete)

    assert len(callback_calls) == 3
    assert all(success for _, success in callback_calls)


def test_run_parallel_handles_task_failure(tmp_path: Path) -> None:
    """Parallel runner continues after task failure and captures error."""
    from skill_eval.models import Scenario, SkillSet
    from skill_eval.runner import RunTask

    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    scenario = Scenario(
        name="test-scenario",
        path=tmp_path / "scenarios" / "test",
        prompt="Test",
        skill_sets=[],
    )

    tasks = [
        RunTask(scenario=scenario, skill_set=SkillSet(name="success", skills=[]), run_dir=run_dir),
        RunTask(scenario=scenario, skill_set=SkillSet(name="failure", skills=[]), run_dir=run_dir),
    ]

    def mock_run_scenario(scenario, skill_set, run_dir):
        from skill_eval.runner import RunResult
        if skill_set.name == "failure":
            raise RuntimeError("Simulated failure")
        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output="",
            success=True,
        )

    with patch.object(runner, "run_scenario", side_effect=mock_run_scenario):
        results = runner.run_parallel(tasks, max_workers=2)

    assert len(results) == 2

    # Find results by skill set name
    success_result = next(r for r in results if r.skill_set_name == "success")
    failure_result = next(r for r in results if r.skill_set_name == "failure")

    assert success_result.success is True
    assert failure_result.success is False
    assert "Simulated failure" in failure_result.error


def test_run_parallel_respects_max_workers(tmp_path: Path) -> None:
    """Parallel runner respects max_workers limit."""
    import threading
    import time
    from skill_eval.models import Scenario, SkillSet
    from skill_eval.runner import RunTask

    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    (evals_dir / "runs").mkdir()

    runner = Runner(evals_dir=evals_dir)
    run_dir = runner.create_run_dir()

    scenario = Scenario(
        name="test",
        path=tmp_path / "scenarios" / "test",
        prompt="Test",
        skill_sets=[],
    )

    tasks = [
        RunTask(scenario=scenario, skill_set=SkillSet(name=f"set-{i}", skills=[]), run_dir=run_dir)
        for i in range(6)
    ]

    max_concurrent = 0
    current_concurrent = 0
    lock = threading.Lock()

    def mock_run_scenario(scenario, skill_set, run_dir):
        nonlocal max_concurrent, current_concurrent
        from skill_eval.runner import RunResult

        with lock:
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)

        time.sleep(0.05)  # Simulate work

        with lock:
            current_concurrent -= 1

        return RunResult(
            scenario_name=scenario.name,
            skill_set_name=skill_set.name,
            output="",
            success=True,
        )

    with patch.object(runner, "run_scenario", side_effect=mock_run_scenario):
        runner.run_parallel(tasks, max_workers=2)

    # Should never exceed max_workers
    assert max_concurrent <= 2
