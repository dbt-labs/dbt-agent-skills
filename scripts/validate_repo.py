#!/usr/bin/env python3
"""Validates the dbt-agent-skills repository integrity.

Checks:
1. All skills are listed in tile.json (and paths are correct)
2. All plugin folders under skills/ are listed in marketplace.json
3. All non-SKILL.md files within skill folders are referenced via markdown links
4. Plugin versions are incremented when skill content changes (vs. main branch)

Usage:
    python scripts/validate_repo.py
    python scripts/validate_repo.py --base-branch origin/main
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TILE_JSON = REPO_ROOT / "tile.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"

# Matches [text](path) and [text](path#heading)
MARKDOWN_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")


def find_all_skills() -> dict[str, Path]:
    """Find all skill directories (containing SKILL.md).

    Returns dict of skill_name -> skill_dir_path.
    """
    skills = {}
    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        skills[skill_dir.name] = skill_dir
    return skills


def find_all_plugin_dirs() -> dict[str, Path]:
    """Find top-level directories under skills/ that are plugins.

    Returns dict of plugin_name -> plugin_dir_path.
    """
    plugins = {}
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            plugins[d.name] = d
    return plugins


# --------------------------------------------------------------------------- #
# Check 1: tile.json
# --------------------------------------------------------------------------- #


def check_tile_json(skills: dict[str, Path]) -> list[str]:
    """Verify every skill on disk is in tile.json and vice versa."""
    errors: list[str] = []

    if not TILE_JSON.exists():
        return ["tile.json not found at repo root"]

    tile = json.loads(TILE_JSON.read_text())
    tile_skills = tile.get("skills", {})

    listed = set(tile_skills.keys())
    on_disk = set(skills.keys())

    for name in sorted(on_disk - listed):
        errors.append(f"Skill '{name}' exists on disk but is missing from tile.json")

    for name in sorted(listed - on_disk):
        errors.append(f"Skill '{name}' is in tile.json but has no SKILL.md on disk")

    # Validate paths for skills that exist in both
    for name in sorted(listed & on_disk):
        expected = str(skills[name].relative_to(REPO_ROOT) / "SKILL.md")
        actual = tile_skills[name].get("path", "")
        if actual != expected:
            errors.append(
                f"tile.json path for '{name}': expected '{expected}', got '{actual}'"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 2: marketplace.json
# --------------------------------------------------------------------------- #


def check_marketplace(plugin_dirs: dict[str, Path]) -> list[str]:
    """Verify every plugin folder is listed in marketplace.json."""
    errors: list[str] = []

    if not MARKETPLACE_JSON.exists():
        return [".claude-plugin/marketplace.json not found"]

    marketplace = json.loads(MARKETPLACE_JSON.read_text())

    # Build a set of plugin directory names from marketplace sources
    listed_names: set[str] = set()
    for plugin in marketplace.get("plugins", []):
        source = plugin.get("source", "")
        # "./skills/dbt" -> "dbt"
        listed_names.add(Path(source).name)

    on_disk = set(plugin_dirs.keys())

    for name in sorted(on_disk - listed_names):
        errors.append(
            f"Plugin folder 'skills/{name}' exists but is missing from marketplace.json"
        )

    for name in sorted(listed_names - on_disk):
        errors.append(
            f"Plugin '{name}' is in marketplace.json but has no folder under skills/"
        )

    return errors


# --------------------------------------------------------------------------- #
# Check 3: file references via markdown links
# --------------------------------------------------------------------------- #


def extract_link_targets(file_path: Path) -> set[Path]:
    """Return resolved filesystem paths from markdown links in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return set()

    targets: set[Path] = set()
    for match in MARKDOWN_LINK_RE.finditer(content):
        raw = match.group(1)
        # Strip anchor fragments
        path_part = raw.split("#")[0]

        if not path_part:
            continue
        if path_part.startswith(("http://", "https://", "mailto:", "data:")):
            continue

        resolved = (file_path.parent / path_part).resolve()
        targets.add(resolved)

    return targets


def find_non_link_mentions(
    filename: str, skill_dir: Path, all_files: list[Path]
) -> list[Path]:
    """Find files that mention a filename outside of a proper markdown link."""
    mentioners: list[Path] = []
    for f in all_files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        if filename not in content:
            continue
        # Check it's not solely via markdown links — strip all markdown links
        # and see if the filename still appears
        stripped = MARKDOWN_LINK_RE.sub("", content)
        if filename in stripped:
            mentioners.append(f)
    return mentioners


def check_file_references(skills: dict[str, Path]) -> list[str]:
    """Verify every non-SKILL.md file in a skill dir is referenced by a markdown link."""
    errors: list[str] = []

    for skill_name, skill_dir in sorted(skills.items()):
        # Collect all files in the skill directory
        all_files = [f for f in skill_dir.rglob("*") if f.is_file()]

        non_skill_md_files = [
            f
            for f in all_files
            if f.name != "SKILL.md" and f.suffix == ".md"
        ]
        if not non_skill_md_files:
            continue

        # Gather every link target from markdown files in this skill
        md_files = [f for f in all_files if f.suffix == ".md"]
        all_referenced: set[Path] = set()
        for f in md_files:
            all_referenced.update(extract_link_targets(f))

        for f in sorted(non_skill_md_files):
            if f.resolve() not in all_referenced:
                rel = f.relative_to(skill_dir)
                # Search for non-link mentions (backticks, code blocks, plain text)
                mentioned_in = find_non_link_mentions(f.name, skill_dir, all_files)
                msg = (
                    f"'{rel}' in skill '{skill_name}' is not referenced "
                    f"by any markdown link within the skill"
                )
                if mentioned_in:
                    files_str = ", ".join(
                        str(m.relative_to(skill_dir)) for m in mentioned_in
                    )
                    msg += f" (but mentioned in: {files_str})"
                errors.append(msg)

    return errors


# --------------------------------------------------------------------------- #
# Check 4: plugin version increments
# --------------------------------------------------------------------------- #


def git_current_branch() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.returncode == 0


def git_changed_files(base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return set()
    return set(result.stdout.strip().splitlines())


def git_file_at_ref(ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout if result.returncode == 0 else None


def check_version_increments(
    plugin_dirs: dict[str, Path], base_branch: str
) -> list[str]:
    """If skills changed vs. base branch, the plugin version must be bumped."""
    errors: list[str] = []

    current = git_current_branch()
    if current is None:
        return ["Could not determine current git branch"]
    if current == base_branch:
        return []  # nothing to compare on the base branch itself

    if not git_branch_exists(base_branch):
        return [f"Base branch '{base_branch}' not found — skipping version check"]

    changed = git_changed_files(base_branch)
    if not changed:
        return []

    for plugin_name, plugin_dir in sorted(plugin_dirs.items()):
        plugin_rel = str(plugin_dir.relative_to(REPO_ROOT))
        skills_prefix = f"{plugin_rel}/skills/"
        plugin_json_rel = f"{plugin_rel}/.claude-plugin/plugin.json"

        skill_changes = sorted(f for f in changed if f.startswith(skills_prefix))
        if not skill_changes:
            continue

        # Read current version
        plugin_json_path = REPO_ROOT / plugin_json_rel
        if not plugin_json_path.exists():
            errors.append(f"Plugin '{plugin_name}': {plugin_json_rel} not found")
            continue
        current_version = json.loads(plugin_json_path.read_text()).get("version")

        # Read base version
        base_content = git_file_at_ref(base_branch, plugin_json_rel)
        if base_content is None:
            # Plugin is new — version check not applicable
            continue
        base_version = json.loads(base_content).get("version")

        if current_version == base_version:
            errors.append(
                f"Plugin '{plugin_name}' has skill changes but version "
                f"({current_version}) was not incremented in {plugin_json_rel}. "
                f"Changed: {', '.join(skill_changes)}"
            )

    return errors


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dbt-agent-skills repo")
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Branch to compare for version-increment check (default: main)",
    )
    args = parser.parse_args()

    skills = find_all_skills()
    plugin_dirs = find_all_plugin_dirs()
    all_errors: list[str] = []

    checks = [
        (
            "tile.json completeness",
            lambda: check_tile_json(skills),
            lambda: f"All {len(skills)} skills listed correctly",
        ),
        (
            "marketplace.json completeness",
            lambda: check_marketplace(plugin_dirs),
            lambda: f"All {len(plugin_dirs)} plugin folders listed correctly",
        ),
        (
            "File references within skills",
            lambda: check_file_references(skills),
            lambda: (
                f"All {sum(len([f for f in d.rglob('*') if f.is_file() and f.name != 'SKILL.md' and f.suffix == '.md']) for d in skills.values())} "
                f"non-SKILL.md markdown files are properly referenced"
            ),
        ),
        (
            "Plugin version increments",
            lambda: check_version_increments(plugin_dirs, args.base_branch),
            lambda: "Plugin versions are up to date",
        ),
    ]

    for title, run_check, ok_msg in checks:
        print(f"Checking {title}...")
        errors = run_check()
        all_errors.extend(errors)
        for e in errors:
            print(f"  FAIL: {e}")
        if not errors:
            print(f"  OK: {ok_msg()}")
        print()

    if all_errors:
        print(f"FAILED: {len(all_errors)} issue(s) found")
        return 1
    else:
        print("ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
