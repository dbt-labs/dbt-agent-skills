#!/usr/bin/env python3
"""Audit dbt model documentation coverage from the dbt manifest.

Reads `target/manifest.json` (produced by `dbt parse`) and reports, per folder,
how many models have a `description` and how many of their declared columns are
documented.
With a folder argument, lists the undocumented models and partially-documented
models for that folder — the unit of work for the maintaining-dbt-documentation skill.

Using the manifest (rather than parsing YAML by hand) means the audit is
correct regardless of the project's YAML layout, `{% docs %}` blocks, or naming
conventions: dbt has already resolved every `description` for us.

Column coverage counts only columns *declared* in YAML. This audit reads the
manifest, not the catalog, so columns that exist in the warehouse but aren't yet
declared in YAML are out of scope — 100% here means "every declared column has a
description", not "every physical column is declared". Surfacing undeclared
columns would require `dbt docs generate` (a live warehouse) and reading
`target/catalog.json`, which this script does not do.

Usage:
    dbt parse                              # (re)generate target/manifest.json first
    python3 audit_coverage.py              # whole-project coverage summary
    python3 audit_coverage.py <folder>     # one folder, undocumented + partial list
    python3 audit_coverage.py --manifest path/to/manifest.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict


def load_models(manifest_path):
    if not os.path.isfile(manifest_path):
        sys.exit(
            f"Manifest not found at '{manifest_path}'.\n"
            "Generate it first by running `dbt parse` from the dbt project root,\n"
            "or point --manifest at an existing manifest.json."
        )
    with open(manifest_path, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    return [
        node
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model"
    ]


def col_stats(node):
    """(#columns with a description, #declared columns) for a model node."""
    columns = node.get("columns", {}) or {}
    documented_columns = sum(
        1 for c in columns.values() if (c.get("description") or "").strip()
    )
    return documented_columns, len(columns)


def main():
    parser = argparse.ArgumentParser(
        description="Audit dbt doc coverage from the manifest."
    )
    parser.add_argument("folder", nargs="?", help="Limit to one folder (suffix match).")
    parser.add_argument(
        "--manifest",
        default=os.path.join("target", "manifest.json"),
        help="Path to manifest.json (default: target/manifest.json).",
    )
    args = parser.parse_args()

    models = load_models(args.manifest)
    if not models:
        sys.exit("No models found in the manifest.")

    folders = defaultdict(list)
    for model in models:
        folders[os.path.dirname(model.get("original_file_path", ""))].append(model)

    def is_documented(model):
        return bool((model.get("description") or "").strip())

    if args.folder:
        target = args.folder.rstrip("/")
        matches = [
            folder
            for folder in folders
            if folder == target or folder.endswith("/" + target)
        ]
        if not matches:
            print(f"No folder matches '{target}'. Folders:")
            for folder in sorted(folders):
                print("  ", folder)
            sys.exit(1)
        for folder in sorted(matches):
            models_in_folder = sorted(folders[folder], key=lambda model: model["name"])
            documented_models = [
                model for model in models_in_folder if is_documented(model)
            ]
            undocumented_models = [
                model for model in models_in_folder if not is_documented(model)
            ]
            print(
                f"\n# {folder}  ({len(documented_models)}/{len(models_in_folder)} models documented)"
            )
            if undocumented_models:
                print(f"  undocumented models ({len(undocumented_models)}):")
                for model in undocumented_models:
                    print("   -", model["name"])
            # Documented models that still have undocumented declared columns.
            partially_documented = []
            for model in documented_models:
                documented_columns, total_columns = col_stats(model)
                if total_columns and documented_columns < total_columns:
                    partially_documented.append(
                        (model["name"], documented_columns, total_columns)
                    )
            if partially_documented:
                print(
                    f"  documented models missing column docs ({len(partially_documented)}):"
                )
                for name, documented_columns, total_columns in partially_documented:
                    print(
                        f"   - {name}  ({documented_columns}/{total_columns} columns)"
                    )
        return

    total_models = len(models)
    documented_model_count = sum(1 for model in models if is_documented(model))
    print(
        f"Model description coverage: {documented_model_count}/{total_models} "
        f"({100 * documented_model_count // total_models}%)\n"
    )
    print("models    columns    folder")
    for folder in sorted(folders):
        models_in_folder = folders[folder]
        documented_model_count = sum(
            1 for model in models_in_folder if is_documented(model)
        )
        folder_documented_columns = folder_total_columns = 0
        for model in models_in_folder:
            model_documented_columns, model_total_columns = col_stats(model)
            folder_documented_columns += model_documented_columns
            folder_total_columns += model_total_columns
        col_str = (
            f"{folder_documented_columns}/{folder_total_columns}"
            if folder_total_columns
            else "-"
        )
        has_gap = documented_model_count < len(models_in_folder) or (
            folder_total_columns and folder_documented_columns < folder_total_columns
        )
        flag = "  <-- gap" if has_gap else ""
        print(
            f"  {documented_model_count:3d}/{len(models_in_folder):<3d}  {col_str:>9s}  {folder}{flag}"
        )


if __name__ == "__main__":
    main()
