"""The local profile's run outcome, recorded by `tools.py report` (RFC-487).

The VS Code extension sends migration telemetry from this outcome, so it has to be
derived from the same records the report is rendered from and must never need the
agent to write anything extra.
"""

import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import pytest

TOOLS = (
    Path(__file__).resolve().parent.parent
    / "skills/dbt-migration/skills/upgrading-dbt/scripts/tools.py"
)


@pytest.fixture(scope="module")
def tools():
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location("upgrading_dbt_tools", TOOLS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(tmp_path: Path, tools, *, results: dict, parse: str | None) -> Path:
    """A project with a results file and, unless `parse` is None, a status file whose
    `parse` phase has that status."""
    tools._write_results(tmp_path, results)
    if parse is not None:
        tools.cmd_status_init(Namespace(project_dir=str(tmp_path)))
        tools.cmd_status_set(
            Namespace(project_dir=str(tmp_path), step="parse", status=parse, note=None)
        )
    return tmp_path


def _report(tools, project: Path) -> dict:
    assert tools.cmd_report(Namespace(project_dir=str(project))) == 0
    return json.loads((project / "target/dbt_migration_status.json").read_text())


def _issue(status: str, *files: str) -> dict:
    return {"status": status, "files_changed": list(files), "notes": ""}


def test_completed_when_parse_passed_and_nothing_is_outstanding(tools, tmp_path):
    project = _project(
        tmp_path,
        tools,
        results={
            "a": _issue("fixed", "models/a.sql"),
            "b": _issue("handled-by-autofix", "models/b.sql"),
            "c": _issue("skipped-not-present"),
        },
        parse="complete",
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["outcome"] == "completed"
    assert outcome["reason"] is None
    assert outcome["files_changed_count"] == 2
    assert outcome["manual_actions_count"] == 0


@pytest.mark.parametrize("status", ["manual-required", "failed", "detected"])
def test_completed_partial_when_something_still_needs_a_person(tools, tmp_path, status):
    project = _project(
        tmp_path,
        tools,
        results={"a": _issue("fixed", "models/a.sql"), "b": _issue(status)},
        parse="complete",
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["outcome"] == "completed_partial"
    assert outcome["manual_actions_count"] == 1


def test_advisory_is_reported_but_does_not_block_completion(tools, tmp_path):
    project = _project(
        tmp_path,
        tools,
        results={"a": _issue("fixed", "models/a.sql"), "b": _issue("advisory")},
        parse="complete",
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["outcome"] == "completed"
    # It is still in the report's "Needs your review", so it still counts there.
    assert outcome["manual_actions_count"] == 1


@pytest.mark.parametrize("parse", ["failed", "in_progress", "pending", None])
def test_failed_when_parse_never_passed(tools, tmp_path, parse):
    project = _project(
        tmp_path,
        tools,
        results={"a": _issue("fixed", "models/a.sql")},
        parse=parse if parse is not None else "pending",
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["outcome"] == "failed"
    assert outcome["gate"]["parse"] == ("failed" if parse == "failed" else "not_run")


def test_the_gate_is_parse_only_and_unknowns_are_null(tools, tmp_path):
    project = _project(
        tmp_path, tools, results={"a": _issue("fixed", "models/a.sql")}, parse="complete"
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["gate"] == {
        "parse": "passed",
        "compile": "not_run",
        "test": "not_run",
        "build": "not_run",
    }
    assert outcome["repair_attempts"] is None
    assert outcome["jobs_to_flip_count"] is None


def test_files_are_counted_once_and_flags_are_counted_per_issue(tools, tmp_path):
    project = _project(
        tmp_path,
        tools,
        results={
            "a": _issue("fixed", "models/a.sql", "models/b.sql"),
            "b": _issue("applied", "models/b.sql"),
            "c": _issue("flag-set", "dbt_project.yml"),
            "d": _issue("flag-set", "dbt_project.yml"),
        },
        parse="complete",
    )

    outcome = _report(tools, project)["outcome"]

    assert outcome["files_changed_count"] == 3
    assert outcome["flags_pinned_count"] == 2


def test_the_steps_the_extension_renders_are_left_alone(tools, tmp_path):
    project = _project(
        tmp_path, tools, results={"a": _issue("fixed")}, parse="complete"
    )
    before = json.loads((project / "target/dbt_migration_status.json").read_text())

    after = _report(tools, project)

    assert after["steps"] == before["steps"]
    assert after["version"] == before["version"]


def test_no_status_file_is_created_just_to_hold_an_outcome(tools, tmp_path):
    project = _project(tmp_path, tools, results={"a": _issue("fixed")}, parse=None)

    assert tools.cmd_report(Namespace(project_dir=str(project))) == 0

    assert (project / "migration_report.md").exists()
    assert not (project / "target/dbt_migration_status.json").exists()


def test_a_fresh_status_init_clears_a_previous_outcome(tools, tmp_path):
    project = _project(
        tmp_path, tools, results={"a": _issue("fixed")}, parse="complete"
    )
    assert "outcome" in _report(tools, project)

    tools.cmd_status_init(Namespace(project_dir=str(project)))

    status = json.loads((project / "target/dbt_migration_status.json").read_text())
    assert "outcome" not in status
