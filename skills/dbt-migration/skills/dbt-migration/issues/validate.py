#!/usr/bin/env python3
"""Validate the dbt-migration issue corpus.

Checks, for every issues/**/*.yaml file:
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

CHANGES_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = CHANGES_DIR / "_schema.json"

# sort_order band per hop (from_version -> (low, high) inclusive)
HOP_BANDS = {
    "1.3": (1000, 1999),
    "1.4": (2000, 2999),
    "1.5": (3000, 3999),
    "1.6": (4000, 4999),
    "1.7": (5000, 5999),
}
ADAPTERS = {"snowflake", "redshift", "bigquery", "databricks", "spark"}


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

        # issue_id encodes the hop
        if cid and from_v:
            m = re.match(r"^from_(1\.\d)_to_(1\.\d)_\d{3}$", cid)
            if not m:
                errors.append(f"{path.name}: issue_id malformed: {cid}")
            elif m.group(1) != from_v:
                errors.append(
                    f"{path.name}: issue_id hop {m.group(1)} != from_version {from_v}"
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
