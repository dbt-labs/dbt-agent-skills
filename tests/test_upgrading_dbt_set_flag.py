"""`tools.py set-flag` edits a user's dbt_project.yml in place, line by line."""

import importlib.util
from pathlib import Path

import pytest
import yaml

TOOLS = (
    Path(__file__).resolve().parent.parent
    / "skills/dbt-migration/skills/upgrading-dbt/scripts/tools.py"
)


@pytest.fixture(scope="module")
def tools():
    spec = importlib.util.spec_from_file_location("upgrading_dbt_tools", TOOLS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("trailing", ["\n", ""])
def test_adds_a_flag_to_an_existing_block_at_the_end_of_the_file(tools, trailing):
    text = "name: jaffle_shop\nflags:\n  send_anonymous_usage_stats: false" + trailing

    new_text, actions = tools._set_flags_in_text(text, {"source_freshness_run_project_hooks": False})

    assert actions == {"source_freshness_run_project_hooks": "added"}
    assert yaml.safe_load(new_text)["flags"] == {
        "send_anonymous_usage_stats": False,
        "source_freshness_run_project_hooks": False,
    }


def test_adds_a_flag_without_touching_the_rest_of_the_file(tools):
    text = "name: jaffle_shop\nflags:\n  send_anonymous_usage_stats: false"

    new_text, _ = tools._set_flags_in_text(text, {"source_freshness_run_project_hooks": False})

    assert new_text == (
        "name: jaffle_shop\n"
        "flags:\n"
        "  send_anonymous_usage_stats: false\n"
        "  source_freshness_run_project_hooks: false\n"
    )


def test_adds_a_new_flags_block_to_a_file_without_a_trailing_newline(tools):
    new_text, actions = tools._set_flags_in_text(
        "name: jaffle_shop", {"source_freshness_run_project_hooks": False}
    )

    assert actions == {"source_freshness_run_project_hooks": "added (new flags: block)"}
    assert yaml.safe_load(new_text) == {
        "name": "jaffle_shop",
        "flags": {"source_freshness_run_project_hooks": False},
    }
