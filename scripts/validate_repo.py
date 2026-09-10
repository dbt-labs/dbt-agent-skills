#!/usr/bin/env python3
"""Validates the dbt-agent-skills repository integrity.

Checks:
1. All skills are listed in tile.json (and paths are correct)
2. All plugin folders under skills/ are listed in marketplace.json
3. Every plugin listed in the Cursor marketplace has a matching Cursor manifest
4. Plugin manifest names and versions agree across marketplaces
5. All non-SKILL.md files within skill folders are referenced via markdown links
6. Every SKILL.md declares valid frontmatter
7. Plugin versions are incremented when skill content changes (vs. main branch)
8. tile.json is versioned alongside skill changes (vs. main branch)

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
CURSOR_MARKETPLACE_JSON = REPO_ROOT / ".cursor-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"

# Per-plugin manifest locations, keyed by the marketplace they serve
PLUGIN_MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "cursor": ".cursor-plugin/plugin.json",
}

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


def read_marketplace_entries(path: Path) -> dict[str, str]:
    """Return plugin folder name -> declared entry name from a marketplace file."""
    marketplace = json.loads(path.read_text())
    entries: dict[str, str] = {}
    for plugin in marketplace.get("plugins", []):
        # "./skills/dbt" -> "dbt"
        folder = Path(plugin.get("source", "")).name
        entries[folder] = plugin.get("name", "")
    return entries


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

    listed_names = set(read_marketplace_entries(MARKETPLACE_JSON))
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
# Check 3: Cursor marketplace
# --------------------------------------------------------------------------- #


def check_cursor_marketplace(plugin_dirs: dict[str, Path]) -> list[str]:
    """Verify the Cursor marketplace and its per-plugin manifests agree.

    Unlike the Claude marketplace, Cursor deliberately lists a *subset* of the
    plugins (see #93 — the Cursor team asked for the single `dbt` plugin), so a
    plugin folder that is absent from this marketplace is not an error. What is
    an error is a listing without a manifest, or a manifest without a listing.
    """
    errors: list[str] = []

    if not CURSOR_MARKETPLACE_JSON.exists():
        return [".cursor-plugin/marketplace.json not found"]

    listed = read_marketplace_entries(CURSOR_MARKETPLACE_JSON)
    manifest_rel = PLUGIN_MANIFESTS["cursor"]

    for folder in sorted(listed):
        if folder not in plugin_dirs:
            errors.append(
                f"Plugin '{folder}' is in .cursor-plugin/marketplace.json but "
                f"has no folder under skills/"
            )
        elif not (plugin_dirs[folder] / manifest_rel).exists():
            errors.append(
                f"Plugin '{folder}' is in .cursor-plugin/marketplace.json but "
                f"skills/{folder}/{manifest_rel} is missing"
            )

    for folder, plugin_dir in sorted(plugin_dirs.items()):
        if (plugin_dir / manifest_rel).exists() and folder not in listed:
            errors.append(
                f"skills/{folder}/{manifest_rel} exists but '{folder}' is not "
                f"listed in .cursor-plugin/marketplace.json"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 4: cross-marketplace manifest coherence
# --------------------------------------------------------------------------- #


def check_manifest_coherence(plugin_dirs: dict[str, Path]) -> list[str]:
    """Verify plugin names match their folder, and versions match across manifests."""
    errors: list[str] = []

    marketplaces = {
        "claude": MARKETPLACE_JSON,
        "cursor": CURSOR_MARKETPLACE_JSON,
    }
    for marketplace, path in marketplaces.items():
        if not path.exists():
            continue
        for folder, entry_name in sorted(read_marketplace_entries(path).items()):
            if entry_name != folder:
                errors.append(
                    f"{marketplace} marketplace entry for 'skills/{folder}' is named "
                    f"'{entry_name}' — expected '{folder}' to match the folder"
                )

    for folder, plugin_dir in sorted(plugin_dirs.items()):
        versions: dict[str, str] = {}
        for marketplace, manifest_rel in PLUGIN_MANIFESTS.items():
            manifest_path = plugin_dir / manifest_rel
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text())

            if manifest.get("name") != folder:
                errors.append(
                    f"skills/{folder}/{manifest_rel} declares name "
                    f"'{manifest.get('name')}' — expected '{folder}'"
                )
            versions[marketplace] = manifest.get("version")

        if len(set(versions.values())) > 1:
            detail = ", ".join(f"{m}={v}" for m, v in sorted(versions.items()))
            errors.append(
                f"Plugin '{folder}' has mismatched versions across manifests "
                f"({detail}) — bump every manifest listed in RELEASING.md together"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 5: file references via markdown links
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
# Check 6: SKILL.md frontmatter
# --------------------------------------------------------------------------- #

# Fields a SKILL.md may declare at the top level. Anything else (version,
# author, tags, ...) belongs under `metadata:` and is rejected by the
# marketplaces that ingest these files.
ALLOWED_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "allowed-tools",
    "compatibility",
    "license",
    "metadata",
    "user-invocable",
}

VALID_SKILL_NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.DOTALL)
# Top-level keys only: nested keys and wrapped scalars are always indented
TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):", re.MULTILINE)
NESTED_USER_INVOCABLE_RE = re.compile(r"^[ \t]+user-invocable:", re.MULTILINE)


def check_frontmatter(skills: dict[str, Path]) -> list[str]:
    """Verify each SKILL.md declares valid, complete frontmatter.

    These rules are what skills.sh, Tessl and the plugin marketplaces validate
    on ingest, so a violation breaks publishing on every surface at once.
    """
    errors: list[str] = []

    for skill_name, skill_dir in sorted(skills.items()):
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        match = FRONTMATTER_RE.match(content)
        if not match:
            errors.append(f"Skill '{skill_name}': SKILL.md has no YAML frontmatter")
            continue
        block = match.group(1)

        fields = set(TOP_LEVEL_KEY_RE.findall(block))

        unexpected = fields - ALLOWED_FRONTMATTER_FIELDS
        if unexpected:
            errors.append(
                f"Skill '{skill_name}': unexpected frontmatter field(s) "
                f"{sorted(unexpected)} — only {sorted(ALLOWED_FRONTMATTER_FIELDS)} "
                f"are allowed at the top level"
            )

        for required in ("name", "description"):
            if required not in fields:
                errors.append(
                    f"Skill '{skill_name}': frontmatter is missing '{required}'"
                )

        name_match = re.search(r"^name:[ \t]*(.+?)[ \t]*$", block, re.MULTILINE)
        if name_match:
            declared = name_match.group(1).strip("\"'")
            if not VALID_SKILL_NAME_RE.fullmatch(declared):
                errors.append(
                    f"Skill '{skill_name}': name '{declared}' must be lowercase "
                    f"letters, digits and single hyphens only"
                )
            elif declared != skill_dir.name:
                errors.append(
                    f"Skill '{skill_name}': name '{declared}' does not match its "
                    f"directory '{skill_dir.name}'"
                )

        # `user-invocable` is only honoured at the top level, so a nested one
        # silently does nothing rather than failing loudly.
        if NESTED_USER_INVOCABLE_RE.search(block):
            errors.append(
                f"Skill '{skill_name}': 'user-invocable' is nested (likely under "
                f"'metadata:') — it must be a top-level field"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 7: plugin version increments
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
# Check 8: tile.json version increment
# --------------------------------------------------------------------------- #


def check_tile_version_increment(base_branch: str) -> list[str]:
    """If any skill changed vs. base branch, tile.json must be bumped.

    tile.json versions the Tessl tile as a whole (see RELEASING.md), so it moves
    on any skill change regardless of which plugin the skill belongs to.
    """
    current = git_current_branch()
    if current is None or current == base_branch:
        return []
    if not git_branch_exists(base_branch):
        # Already reported by the plugin version check
        return []

    skills_prefix = f"{SKILLS_DIR.relative_to(REPO_ROOT)}/"
    skill_changes = sorted(
        f for f in git_changed_files(base_branch) if f.startswith(skills_prefix)
    )
    if not skill_changes:
        return []

    tile_rel = str(TILE_JSON.relative_to(REPO_ROOT))
    base_content = git_file_at_ref(base_branch, tile_rel)
    if base_content is None:
        return []

    current_version = json.loads(TILE_JSON.read_text()).get("version")
    if current_version != json.loads(base_content).get("version"):
        return []

    return [
        f"{len(skill_changes)} skill file(s) changed but the {tile_rel} version "
        f"({current_version}) was not incremented. "
        f"Changed: {', '.join(skill_changes)}"
    ]


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
            "Cursor marketplace manifests",
            lambda: check_cursor_marketplace(plugin_dirs),
            lambda: (
                f"All {len(read_marketplace_entries(CURSOR_MARKETPLACE_JSON))} "
                f"listed Cursor plugin(s) have manifests"
            ),
        ),
        (
            "Manifest names and versions across marketplaces",
            lambda: check_manifest_coherence(plugin_dirs),
            lambda: "Plugin names and versions agree across manifests",
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
            "SKILL.md frontmatter",
            lambda: check_frontmatter(skills),
            lambda: f"All {len(skills)} skills have valid frontmatter",
        ),
        (
            "Plugin version increments",
            lambda: check_version_increments(plugin_dirs, args.base_branch),
            lambda: "Plugin versions are up to date",
        ),
        (
            "tile.json version increment",
            lambda: check_tile_version_increment(args.base_branch),
            lambda: "tile.json version is up to date",
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
