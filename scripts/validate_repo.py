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

Checks 7 and 8 share one resolved diff against the base branch (see DiffContext).

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
from typing import NamedTuple

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
            version = manifest.get("version")
            if not isinstance(version, str) or not version.strip():
                errors.append(
                    f"skills/{folder}/{manifest_rel} has no usable 'version' "
                    f"(got {version!r})"
                )
                continue
            versions[marketplace] = version

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
KEY_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    # A key may be quoted; `"author": me` is the same field as `author: me`
    r"""(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<plain>[A-Za-z0-9_-]+))"""
    r"[ \t]*:[ \t]*(?P<value>.*)$"
)


def scalar_value(raw: str) -> str:
    """The value of a YAML scalar, without quotes or a trailing comment."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        quote, end = raw[0], raw.find(raw[0], 1)
        return raw[1:end] if end > 0 else raw[1:]
    # A '#' only starts a comment when preceded by whitespace
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


class Frontmatter(NamedTuple):
    """A parsed frontmatter block.

    `flow_keys` are keys written in flow style (`metadata: {a: b}`). Keys
    hidden inside one are invisible to a line scanner, so rather than appear
    to validate them, they are reported and the author asked for block style.
    """

    top: dict[str, str]
    nested: set[str]
    flow_keys: set[str]


def parse_frontmatter(block: str) -> Frontmatter:
    """Split a frontmatter block into (top-level key -> value, nested key names).

    Block scalars (`description: |` / `>`) are understood: their indented body
    is free text, so a line inside one that merely looks like `key: value` is
    not structure and is ignored. A regex alone cannot tell those apart, which
    is why this is a scanner.
    """
    top: dict[str, str] = {}
    nested: set[str] = set()
    flow_keys: set[str] = set()
    # Indentation of the key that opened the current block scalar, if any. Its
    # body is every following line indented deeper than it — which is how a
    # scalar nested under `metadata:` is handled as well as a top-level one.
    scalar_indent: int | None = None
    # The top-level key that scalar belongs to, so its body becomes the value.
    # Storing the `|` marker instead would make an empty scalar look non-empty.
    scalar_key: str | None = None

    for line in block.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.expandtabs().lstrip())
        if scalar_indent is not None:
            if indent > scalar_indent:
                if scalar_key is not None:
                    top[scalar_key] = f"{top[scalar_key]} {line.strip()}".strip()
                continue  # still inside the scalar's body
            scalar_indent = None
            scalar_key = None

        match = KEY_RE.match(line)
        if not match:
            continue
        key = match["dq"] or match["sq"] or match["plain"]
        raw = match["value"]

        if raw.strip()[:1] == "{":
            flow_keys.add(key)

        if indent == 0:
            top[key] = scalar_value(raw)
        else:
            nested.add(key)

        # Covers |, >, and the |- / >- / |+ chomping variants
        if raw.strip()[:1] in ("|", ">"):
            scalar_indent = indent
            if indent == 0:
                scalar_key = key
                top[key] = ""  # the body, if any, fills this in

    return Frontmatter(top, nested, flow_keys)


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

        parsed = parse_frontmatter(match.group(1))
        top, nested = parsed.top, parsed.nested
        fields = set(top)

        if parsed.flow_keys:
            errors.append(
                f"Skill '{skill_name}': frontmatter key(s) "
                f"{sorted(parsed.flow_keys)} use flow style (`key: {{...}}`) — "
                f"use block style so field placement can be validated"
            )

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
            elif not top[required].strip():
                errors.append(
                    f"Skill '{skill_name}': frontmatter '{required}' is empty"
                )

        declared = top.get("name")
        if declared:
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
        if "user-invocable" in nested and "user-invocable" not in top:
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


class DiffContext(NamedTuple):
    """The git state both version-increment checks need, resolved once.

    `changed` is None when there is nothing to compare against, in which case
    `errors` explains why — or is empty when skipping is the correct, silent
    outcome (running on the base branch itself). Resolving this once keeps the
    two checks' skip rules identical by construction rather than by convention,
    and keeps `validate_repo.py` to one `git` invocation per fact.
    """

    base_branch: str
    changed: set[str] | None
    errors: list[str]


def diff_context(base_branch: str) -> DiffContext:
    """Resolve the diff against `base_branch`, or say why we cannot."""
    current = git_current_branch()
    if current is None:
        return DiffContext(base_branch, None, ["Could not determine current git branch"])
    if current == base_branch:
        return DiffContext(base_branch, None, [])  # nothing to compare on the base branch
    if not git_branch_exists(base_branch):
        return DiffContext(
            base_branch,
            None,
            [f"Base branch '{base_branch}' not found — skipping version checks"],
        )
    return DiffContext(base_branch, git_changed_files(base_branch), [])


def parse_version(value: object) -> tuple[int, ...] | None:
    """A dotted numeric version as a comparable tuple, or None if unparseable."""
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def version_increased(current: object, base: object) -> bool | None:
    """Whether `current` is strictly greater than `base`; None if either is unparseable.

    An equality test is not enough: it accepts a downgrade, which is as wrong
    as forgetting the bump and harder to notice.
    """
    current_parsed, base_parsed = parse_version(current), parse_version(base)
    if current_parsed is None or base_parsed is None:
        return None
    return current_parsed > base_parsed


def check_version_increments(
    plugin_dirs: dict[str, Path], diff: DiffContext
) -> list[str]:
    """If skills changed vs. base branch, the plugin version must be bumped.

    This check owns reporting the shared context errors; the tile check stays
    silent about them so they are not reported twice.
    """
    errors: list[str] = []

    if diff.changed is None:
        return diff.errors
    changed = diff.changed
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
        base_content = git_file_at_ref(diff.base_branch, plugin_json_rel)
        if base_content is None:
            # Plugin is new — version check not applicable
            continue
        base_version = json.loads(base_content).get("version")

        increased = version_increased(current_version, base_version)
        if increased is None:
            errors.append(
                f"Plugin '{plugin_name}': cannot compare versions in "
                f"{plugin_json_rel} (base {base_version!r}, current "
                f"{current_version!r}) — expected dotted numbers like '1.5.1'"
            )
        elif not increased:
            errors.append(
                f"Plugin '{plugin_name}' has skill changes but version "
                f"({current_version}) is not an increase over the base "
                f"({base_version}) in {plugin_json_rel}. "
                f"Changed: {', '.join(skill_changes)}"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 8: tile.json version increment
# --------------------------------------------------------------------------- #


def check_tile_version_increment(diff: DiffContext) -> list[str]:
    """If any skill's content changed vs. base branch, tile.json must be bumped.

    tile.json versions the Tessl tile as a whole (see RELEASING.md), so it moves
    on any skill change regardless of which plugin the skill belongs to. Like
    the per-plugin check, this counts only skill content — files matching
    skills/<plugin>/skills/. A plugin manifest bump on its own changes nothing
    Tessl publishes and must not force a tile bump.
    """
    # Context errors are reported by the plugin version check, not here.
    if not diff.changed:
        return []

    # Matched on path shape rather than against the plugin directories that
    # exist now: a PR that deletes a whole plugin still has its skill files in
    # the diff, and that is exactly when the tile's skill list changes.
    skills_root = re.escape(str(SKILLS_DIR.relative_to(REPO_ROOT)))
    skill_content = re.compile(rf"^{skills_root}/[^/]+/skills/.+")
    skill_changes = sorted(f for f in diff.changed if skill_content.match(f))
    if not skill_changes:
        return []

    tile_rel = str(TILE_JSON.relative_to(REPO_ROOT))
    if not TILE_JSON.exists():
        # check_tile_json already reported this; do not crash on read_text()
        return []
    base_content = git_file_at_ref(diff.base_branch, tile_rel)
    if base_content is None:
        return []

    current_version = json.loads(TILE_JSON.read_text()).get("version")
    base_version = json.loads(base_content).get("version")

    increased = version_increased(current_version, base_version)
    if increased is None:
        return [
            f"Cannot compare {tile_rel} versions (base {base_version!r}, current "
            f"{current_version!r}) — expected dotted numbers like '1.5.2'"
        ]
    if increased:
        return []

    return [
        f"{len(skill_changes)} skill file(s) changed but the {tile_rel} version "
        f"({current_version}) is not an increase over the base ({base_version}). "
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
    # Resolved once and shared: both version checks apply the same skip rules.
    diff = diff_context(args.base_branch)
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
            lambda: check_version_increments(plugin_dirs, diff),
            lambda: "Plugin versions are up to date",
        ),
        (
            "tile.json version increment",
            lambda: check_tile_version_increment(diff),
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
