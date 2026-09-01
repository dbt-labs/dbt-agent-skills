"""Tests for skill_eval reporter."""

from pathlib import Path

import yaml

from skill_eval.reporter import (
    _compute_skill_set_stats,
    _format_cost,
    _format_duration,
    _format_tokens,
    collect_review_rows,
    generate_review_html,
)


def test_compute_skill_set_stats_aggregates_across_scenarios() -> None:
    """Stats are aggregated per skill set across all scenarios."""
    results = {
        "scenario-a": {
            "set-1": {"success": True, "score": 5, "tool_usage": "appropriate"},
            "set-2": {"success": False, "score": 2, "tool_usage": "partial"},
        },
        "scenario-b": {
            "set-1": {"success": True, "score": 4, "tool_usage": "appropriate"},
        },
    }

    stats = _compute_skill_set_stats(results)

    assert stats["set-1"]["total"] == 2
    assert stats["set-1"]["passed"] == 2
    assert stats["set-1"]["scores"] == [5, 4]
    assert stats["set-2"]["total"] == 1
    assert stats["set-2"]["passed"] == 0


def test_compute_skill_set_stats_counts_tool_usage() -> None:
    """Tool usage is counted correctly."""
    results = {
        "scenario-a": {
            "set-1": {"tool_usage": "appropriate"},
        },
        "scenario-b": {
            "set-1": {"tool_usage": "appropriate"},
        },
        "scenario-c": {
            "set-1": {"tool_usage": "partial"},
        },
    }

    stats = _compute_skill_set_stats(results)

    assert stats["set-1"]["tool_usage"]["appropriate"] == 2
    assert stats["set-1"]["tool_usage"]["partial"] == 1
    assert stats["set-1"]["tool_usage"]["inappropriate"] == 0


def test_compute_skill_set_stats_tracks_skill_usage() -> None:
    """Skill usage is tracked as (invoked, available) tuples."""
    results = {
        "scenario-a": {
            "set-1": {
                "skills_available": ["skill-a", "skill-b"],
                "skills_invoked": ["skill-a"],
            },
        },
        "scenario-b": {
            "set-1": {
                "skills_available": ["skill-a"],
                "skills_invoked": ["skill-a"],
            },
        },
    }

    stats = _compute_skill_set_stats(results)

    assert stats["set-1"]["skill_usage"] == [(1, 2), (1, 1)]


def test_compute_skill_set_stats_handles_missing_fields() -> None:
    """Missing fields are handled gracefully."""
    results = {
        "scenario-a": {
            "set-1": {},  # No fields at all
        },
    }

    stats = _compute_skill_set_stats(results)

    assert stats["set-1"]["total"] == 1
    assert stats["set-1"]["passed"] == 0
    assert stats["set-1"]["scores"] == []
    assert stats["set-1"]["skill_usage"] == []


def test_compute_skill_set_stats_handles_empty_results() -> None:
    """Empty results return empty stats."""
    stats = _compute_skill_set_stats({})

    assert stats == {}


def test_format_duration() -> None:
    assert _format_duration(None) == "-"
    assert _format_duration(3200) == "3.2s"
    assert _format_duration(65000) == "1m 05s"


def test_format_cost() -> None:
    assert _format_cost(None) == "-"
    assert _format_cost(0.1426) == "$0.1426"


def test_format_tokens() -> None:
    assert _format_tokens(None) == "-"
    assert _format_tokens(125241) == "125,241"


def _make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "2026-01-01-000000"
    skill_set_dir = run_dir / "my-scenario" / "with-mcp"
    skill_set_dir.mkdir(parents=True)
    metadata = {
        "success": True,
        "skills_invoked": ["my-skill"],
        "skills_available": ["my-skill"],
        "skills_available_other": ["design-sync"],
        "tools_used": ["Read", "mcp__dbt__list_projects"],
        "tool_call_count": 5,
        "mcp_servers": [{"name": "dbt", "status": "connected"}],
        "model": "claude-sonnet-5",
        "duration_ms": 52856,
        "num_turns": 8,
        "total_cost_usd": 0.2031766,
        "input_tokens": 267958,
        "output_tokens": 3130,
    }
    (skill_set_dir / "metadata.yaml").write_text(yaml.dump(metadata))
    (skill_set_dir / "output.md").write_text("Some output")
    transcript_dir = skill_set_dir / "transcript"
    transcript_dir.mkdir()
    (transcript_dir / "index.html").write_text("<html></html>")
    return run_dir


def test_collect_review_rows_reads_metadata_and_links(tmp_path: Path) -> None:
    """collect_review_rows gathers metadata and relative links per skill set."""
    run_dir = _make_run(tmp_path)

    rows = collect_review_rows(run_dir)

    assert len(rows) == 1
    row = rows[0]
    assert row["scenario"] == "my-scenario"
    assert row["skill_set"] == "with-mcp"
    assert row["metadata"]["total_cost_usd"] == 0.2031766
    assert row["transcript_rel"] == "my-scenario/with-mcp/transcript/index.html"
    assert row["output_rel"] == "my-scenario/with-mcp/output.md"
    assert row["grade"] is None  # No grades.yaml in this run


def test_collect_review_rows_attaches_grade_when_present(tmp_path: Path) -> None:
    """collect_review_rows pulls in the score from grades.yaml if it exists."""
    run_dir = _make_run(tmp_path)
    grades = {"results": {"my-scenario": {"with-mcp": {"success": True, "score": 4}}}}
    (run_dir / "grades.yaml").write_text(yaml.dump(grades))

    rows = collect_review_rows(run_dir)

    assert rows[0]["grade"]["score"] == 4


def test_generate_review_html_includes_key_metrics_and_links(tmp_path: Path) -> None:
    """The generated review page surfaces cost, tool calls, and transcript links."""
    run_dir = _make_run(tmp_path)

    html = generate_review_html(run_dir)

    assert "my-scenario" in html
    assert "with-mcp" in html
    assert "$0.2032" in html
    assert ">5<" in html  # tool_call_count
    assert 'href="my-scenario/with-mcp/transcript/index.html"' in html
    assert "design-sync" not in html  # skills_available_other isn't shown as if configured


def test_generate_review_html_flags_subagent_usage(tmp_path: Path) -> None:
    """The review page shows a subagent count when a set used the Task tool."""
    run_dir = _make_run(tmp_path)
    metadata_file = run_dir / "my-scenario" / "with-mcp" / "metadata.yaml"
    metadata = yaml.safe_load(metadata_file.read_text())
    metadata["subagents_used"] = True
    metadata["subagent_count"] = 2
    metadata["subagent_tool_call_count"] = 30
    metadata["subagent_tools_used"] = ["Read", "Glob"]
    metadata_file.write_text(yaml.dump(metadata))

    html = generate_review_html(run_dir)

    assert ">2<" in html
    assert "Read, Glob" in html
    assert "30 calls" in html


def test_generate_review_html_shows_dash_when_no_subagents(tmp_path: Path) -> None:
    """Sets that never spawned a subagent show a dash, not a false zero-count row."""
    run_dir = _make_run(tmp_path)

    html = generate_review_html(run_dir)

    assert "<th data-idx=\"9\" data-numeric=\"1\">Subagents</th>" in html
