"""Tests for skill_eval reporter."""

from skill_eval.reporter import _compute_skill_set_stats


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
