#!/usr/bin/env python3
"""Validate the upgrading-dbt-core issue corpus.

Checks, for every kb/**/*.yaml file:
  1. Conformance to issues/_schema.json.
  2. issue_id uniqueness across the whole corpus.
  3. sort_order uniqueness across the whole corpus.
  4. sort_order is monotonic with version order (the hop encoded by
     from_version/to_version must line up with the sort_order band).
  5. Filename stem == issue_id.
  6. The directory a file lives in matches its component/adapter_type.

Exits non-zero on any violation so it can gate CI.

Depends only on the stdlib plus `jsonschema` if available; if jsonschema is
not installed it falls back to a minimal built-in structural check so the
script still runs in a bare environment.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CHANGES_DIR = Path(__file__).resolve().parent.parent / "kb"
SCHEMA_PATH = CHANGES_DIR / "_schema.json"

# sort_order band per version (from_version -> (low, high) inclusive)
HOP_BANDS = {
    "1.3": (1000, 1999),
    "1.4": (2000, 2999),
    "1.5": (3000, 3999),
    "1.6": (4000, 4999),
    "1.7": (5000, 5999),
    "1.8": (6000, 6999),
    "1.9": (7000, 7999),
    "1.10": (8000, 8999),
    "1.11": (9000, 9999),
}
ADAPTERS = {"snowflake", "redshift", "bigquery", "databricks", "spark"}

# Every behavior-change flag dbt-core actually recognizes, i.e. the keys of
# dbt.contracts.project.ProjectFlags.project_only_flags. This list MUST be
# validated against, because dbt silently ignores unknown `flags:` keys — a
# typo'd flag name would produce a project that looks migrated but has not
# actually pinned anything, with no error anywhere.
#
# Regenerate against a target-version dbt-core with:
#   python -c "from dbt.contracts.project import ProjectFlags as P; \
#              print(sorted(P().project_only_flags))"
KNOWN_BEHAVIOR_FLAGS = {
    "allow_jinja_file_extensions",
    "enable_grouped_warn_error_parser_logs",
    "latest_version_pointer_enabled_by_default",
    "require_all_warnings_handled_by_warn_error",
    "require_batched_execution_for_custom_microbatch_strategy",
    "require_corrected_analysis_fqns",
    "require_explicit_package_overrides_for_builtin_materializations",
    "require_generic_test_arguments_property",
    "require_nested_cumulative_type_params",
    "require_ref_searches_node_package_before_root",
    "require_resource_names_without_spaces",
    "require_source_and_semantic_model_names_without_spaces",
    "require_sql_header_in_test_configs",
    "require_unique_project_resource_names",
    "require_valid_schema_from_generate_schema_name",
    "require_yaml_configuration_for_mf_time_spines",
    "skip_nodes_if_on_run_start_fails",
    "source_freshness_run_project_hooks",
    "state_modified_compare_more_unrendered_values",
    "state_modified_compare_vars",
    "support_custom_ref_kwargs",
    "use_catalogs_v2",
    "validate_macro_args",
}  # dbt-core 1.12.0


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def load_change(path: Path) -> dict:
    import yaml  # PyYAML; run via `uv run --with pyyaml python validate.py`

    with path.open() as fh:
        return yaml.safe_load(fh)


def iter_change_files():
    for path in sorted(CHANGES_DIR.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        yield path


def validate_schema(records, schema, errors):
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft7Validator(schema)
        for path, data in records:
            for err in validator.iter_errors(data):
                errors.append(f"{path.name}: schema: {err.message}")
    except ImportError:
        required = schema["required"]
        for path, data in records:
            missing = [k for k in required if k not in data]
            if missing:
                errors.append(f"{path.name}: missing required keys: {missing}")
            extra = [k for k in data if k not in schema["properties"]]
            if extra:
                errors.append(f"{path.name}: unexpected keys: {extra}")


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 2

    schema = load_json(SCHEMA_PATH)
    records = [(p, load_change(p)) for p in iter_change_files()]

    if not records:
        print("ERROR: no change files found", file=sys.stderr)
        return 2

    errors: list[str] = []
    validate_schema(records, schema, errors)

    seen_ids: dict[str, str] = {}
    seen_orders: dict[int, str] = {}

    for path, data in records:
        cid = data.get("issue_id")
        order = data.get("sort_order")
        component = data.get("component")
        adapter = data.get("adapter_type")
        from_v = data.get("from_version")

        # filename stem == issue_id
        if cid and path.stem != cid:
            errors.append(f"{path.name}: filename stem != issue_id ({cid})")

        # issue_id uniqueness
        if cid in seen_ids:
            errors.append(f"duplicate issue_id {cid}: {path.name} and {seen_ids[cid]}")
        elif cid:
            seen_ids[cid] = path.name

        # sort_order uniqueness
        if order in seen_orders:
            errors.append(
                f"duplicate sort_order {order}: {path.name} and {seen_orders[order]}"
            )
        elif order is not None:
            seen_orders[order] = path.name

        # sort_order band matches hop
        if from_v in HOP_BANDS and isinstance(order, int):
            low, high = HOP_BANDS[from_v]
            if not (low <= order <= high):
                errors.append(
                    f"{path.name}: sort_order {order} outside band {low}-{high} "
                    f"for from_version {from_v}"
                )

        # directory matches component/adapter_type
        parent = path.parent.name
        if component == "core":
            if parent != "core":
                errors.append(f"{path.name}: component core but in dir '{parent}'")
        elif component == "adapter":
            if adapter not in ADAPTERS:
                errors.append(f"{path.name}: adapter component but adapter_type={adapter!r}")
            elif parent != adapter:
                errors.append(
                    f"{path.name}: adapter_type {adapter} but in dir '{parent}'"
                )

        # behavior_flag issues must name a flag dbt actually recognizes
        if data.get("automation_type") == "behavior_flag":
            bf = data.get("behavior_flag") or {}
            fname = bf.get("name")
            if fname and fname not in KNOWN_BEHAVIOR_FLAGS:
                errors.append(
                    f"{path.name}: behavior_flag.name {fname!r} is not a recognized dbt "
                    f"behavior flag (dbt silently ignores unknown flags, so this would "
                    f"be a no-op). Known: {sorted(KNOWN_BEHAVIOR_FLAGS)}"
                )
            if bf.get("set_to") is not False:
                errors.append(
                    f"{path.name}: behavior_flag.set_to must be false — the point is to "
                    f"preserve legacy behavior"
                )

        # issue_id encodes the version whose boundary introduced the change
        if cid and from_v:
            if not isinstance(cid, str):
                # bare 1_3_001 parses as int 13001 under YAML 1.1 digit-separator rules
                errors.append(
                    f"{path.name}: issue_id parsed as {type(cid).__name__} {cid!r} — quote it in YAML"
                )
            else:
                m = re.match(r"^1_(\d+)_\d{3}$", cid)
                if not m:
                    errors.append(f"{path.name}: issue_id malformed: {cid} (want 1_<minor>_<NNN>)")
                elif f"1.{m.group(1)}" != from_v:
                    errors.append(
                        f"{path.name}: issue_id version 1.{m.group(1)} != from_version {from_v}"
                    )

    if errors:
        print(f"FAILED: {len(errors)} problem(s) in {len(records)} file(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(records)} issue files valid (unique ids + sort_order, bands consistent).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
