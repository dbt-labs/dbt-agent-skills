#!/usr/bin/env python3
"""Audit dbt model documentation coverage from the dbt manifest.

Reads `target/manifest.json` (produced by `dbt parse` or
`dbt docs generate --empty-catalog`) and reports, per folder, how many models
have a `description` and how many of their declared columns are documented.
With a folder argument, lists the undocumented models and partially-documented
models for that folder — the unit of work for the maintaining-dbt-documentation skill.

Using the manifest (rather than parsing YAML by hand) means the audit is
correct regardless of the project's YAML layout, `{% docs %}` blocks, or naming
conventions: dbt has already resolved every `description` for us.

Column coverage counts only columns *declared* in YAML. Columns that exist in
the warehouse but are not yet declared don't appear here (that needs a catalog,
which requires a warehouse connection) — so 100% here means "every declared
column has a description", not "every physical column is declared".

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
            "Generate it first from the dbt project root, e.g.:\n"
            "  dbt parse\n"
            "  dbt docs generate --empty-catalog   # if parse alone isn't enough"
        )
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    return [
        n for n in manifest.get("nodes", {}).values()
        if n.get("resource_type") == "model"
    ]


def col_stats(node):
    """(#columns with a description, #declared columns) for a model node."""
    cols = node.get("columns", {}) or {}
    documented = sum(1 for c in cols.values() if (c.get("description") or "").strip())
    return documented, len(cols)


def main():
    parser = argparse.ArgumentParser(description="Audit dbt doc coverage from the manifest.")
    parser.add_argument("folder", nargs="?", help="Limit to one folder (suffix match).")
    parser.add_argument("--manifest", default=os.path.join("target", "manifest.json"),
                        help="Path to manifest.json (default: target/manifest.json).")
    args = parser.parse_args()

    models = load_models(args.manifest)
    if not models:
        sys.exit("No models found in the manifest.")

    folders = defaultdict(list)
    for n in models:
        folders[os.path.dirname(n.get("original_file_path", ""))].append(n)

    def is_doc(n):
        return bool((n.get("description") or "").strip())

    if args.folder:
        target = args.folder.rstrip("/")
        matches = [f for f in folders if f == target or f.endswith("/" + target)]
        if not matches:
            print(f"No folder matches '{target}'. Folders:")
            for f in sorted(folders):
                print("  ", f)
            sys.exit(1)
        for folder in sorted(matches):
            nodes = sorted(folders[folder], key=lambda n: n["name"])
            documented = [n for n in nodes if is_doc(n)]
            undoc = [n for n in nodes if not is_doc(n)]
            print(f"\n# {folder}  ({len(documented)}/{len(nodes)} models documented)")
            if undoc:
                print(f"  undocumented models ({len(undoc)}):")
                for n in undoc:
                    print("   -", n["name"])
            # Documented models that still have undocumented declared columns.
            partial = []
            for n in documented:
                d, total = col_stats(n)
                if total and d < total:
                    partial.append((n["name"], d, total))
            if partial:
                print(f"  documented models missing column docs ({len(partial)}):")
                for name, d, total in partial:
                    print(f"   - {name}  ({d}/{total} columns)")
        return

    total = len(models)
    doc = sum(1 for n in models if is_doc(n))
    print(f"Model description coverage: {doc}/{total} ({100 * doc // total}%)\n")
    print("models    columns    folder")
    for folder in sorted(folders):
        nodes = folders[folder]
        d = sum(1 for n in nodes if is_doc(n))
        col_d = col_t = 0
        for n in nodes:
            cd, ct = col_stats(n)
            col_d += cd
            col_t += ct
        col_str = f"{col_d}/{col_t}" if col_t else "-"
        flag = "  <-- gap" if d < len(nodes) or (col_t and col_d < col_t) else ""
        print(f"  {d:3d}/{len(nodes):<3d}  {col_str:>9s}  {folder}{flag}")


if __name__ == "__main__":
    main()
