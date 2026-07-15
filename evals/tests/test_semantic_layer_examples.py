import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = (
    REPO_ROOT
    / "skills/dbt/skills/building-dbt-semantic-layer/SKILL.md"
)
LATEST_SPEC_PATH = SKILL_PATH.parent / "references/latest-spec.md"


def extract_yaml_example(marker: str) -> dict:
    content = SKILL_PATH.read_text()
    match = re.search(
        rf"\*\*{re.escape(marker)}.*?```yaml\n(.*?)```",
        content,
        re.DOTALL,
    )
    assert match, f"Could not find {marker} YAML example"
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict)
    return parsed


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for child in value.values()
            for key in nested_keys(child)
        }
    if isinstance(value, list):
        return {
            key
            for child in value
            for key in nested_keys(child)
        }
    return set()


def test_latest_example_uses_model_embedded_spec() -> None:
    example = extract_yaml_example("Minimal latest spec example")
    model = example["models"][0]

    assert model["semantic_model"]["enabled"] is True
    assert model["agg_time_dimension"] == "order_date"
    assert "entities" not in model["semantic_model"]
    assert "dimensions" not in model["semantic_model"]

    columns = {column["name"]: column for column in model["columns"]}
    assert columns["order_id"]["entity"] == {
        "type": "primary",
        "name": "order",
    }
    assert columns["customer_id"]["entity"] == {
        "type": "foreign",
        "name": "customer",
    }
    assert columns["order_date"]["granularity"] == "day"
    assert columns["order_date"]["dimension"] == {"type": "time"}
    assert columns["status"]["dimension"] == {"type": "categorical"}

    metric = model["metrics"][0]
    assert metric["type"] == "simple"
    assert metric["agg"] == "sum"
    assert metric["expr"] == "amount"
    assert "measures" not in nested_keys(example)
    assert "type_params" not in nested_keys(example)


def test_legacy_example_includes_default_aggregation_time() -> None:
    example = extract_yaml_example("Minimal legacy spec example")
    semantic_model = example["semantic_models"][0]

    assert semantic_model["defaults"]["agg_time_dimension"] == "order_date"
    assert semantic_model["measures"][0] == {
        "name": "revenue",
        "agg": "sum",
        "expr": "amount",
    }
    assert example["metrics"][0]["type_params"]["measure"] == "revenue"


def test_latest_reference_uses_valid_average_aggregation() -> None:
    content = LATEST_SPEC_PATH.read_text()

    assert not re.search(r"^\s*agg:\s+avg\s*$", content, re.MULTILINE)
    assert re.search(r"^\s*agg:\s+average\s*$", content, re.MULTILINE)
