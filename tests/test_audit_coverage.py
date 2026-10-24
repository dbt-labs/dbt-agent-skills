"""The maintaining-dbt-documentation skill's manifest coverage audit."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

AUDIT = (
    Path(__file__).resolve().parent.parent
    / "skills/dbt/skills/maintaining-dbt-documentation/audit_coverage.py"
)


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_coverage", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _model(package, name, path, description=""):
    return {
        "resource_type": "model",
        "package_name": package,
        "name": name,
        "original_file_path": path,
        "description": description,
        "columns": {},
    }


def _write_manifest(tmp_path, nodes, metadata):
    manifest = {
        "metadata": metadata,
        "nodes": {
            f"model.{node['package_name']}.{node['name']}": node for node in nodes
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


NODES = [
    _model("jaffle_shop", "stg_orders", "models/staging/stg_orders.sql", "Orders."),
    # Installed package models have paths relative to the package root.
    _model("fivetran_log", "stg_fivetran_log__log", "models/staging/stg_log.sql"),
]


def test_package_models_are_excluded(audit, tmp_path):
    path = _write_manifest(tmp_path, NODES, {"project_name": "jaffle_shop"})

    names = [model["name"] for model in audit.load_models(str(path))]

    assert names == ["stg_orders"]


def test_folder_audit_does_not_list_package_models(
    audit, tmp_path, monkeypatch, capsys
):
    path = _write_manifest(tmp_path, NODES, {"project_name": "jaffle_shop"})
    monkeypatch.setattr(
        sys, "argv", ["audit_coverage.py", "models/staging", "--manifest", str(path)]
    )

    audit.main()

    out = capsys.readouterr().out
    assert "(1/1 models documented)" in out
    assert "stg_fivetran_log__log" not in out


def test_manifest_without_project_name_keeps_all_models(audit, tmp_path):
    path = _write_manifest(tmp_path, NODES, {})

    assert len(audit.load_models(str(path))) == 2
