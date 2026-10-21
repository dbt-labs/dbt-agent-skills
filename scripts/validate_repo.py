#!/usr/bin/env python3
"""Validates the dbt-agent-skills repository integrity.

Checks:
1. All skills are listed in tile.json (and paths are correct)
2. All plugin folders under skills/ are listed in marketplace.json
3. Every plugin listed in the Cursor marketplace has a matching Cursor manifest
4. Plugin manifest names and versions agree across marketplaces
5. All non-SKILL.md files within skill folders are referenced via markdown links
6. Every SKILL.md declares valid frontmatter
7. Every versioned file carries the version of the latest changie release
8. Every Claude marketplace entry fetches its plugin from the release branch
9. Changes under skills/ come with a changie fragment, and CHANGELOG.md only
   changes in a release PR (vs. main branch)
10. Every unreleased changie fragment parses and names a known component and kind

Usage:
    uv run python scripts/validate_repo.py
    uv run python scripts/validate_repo.py --base-branch origin/main
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TILE_JSON = REPO_ROOT / "tile.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CURSOR_MARKETPLACE_JSON = REPO_ROOT / ".cursor-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"
CHANGIE_YAML = REPO_ROOT / ".changie.yaml"
CHANGES_DIR = REPO_ROOT / ".changes"
CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"

REPO_GIT_URL = "https://github.com/dbt-labs/dbt-agent-skills.git"
RELEASE_BRANCH = "stable"

# Files that carry the single repo version, relative to REPO_ROOT. Must match
# the `replacements` in .changie.yaml, which rewrite them on release.
VERSIONED_FILE_GLOBS = (
    "skills/*/.claude-plugin/plugin.json",
    "skills/*/.cursor-plugin/plugin.json",
    "skills/*/dbt_project.yml",
    "tile.json",
)

# Per-plugin manifest locations, keyed by the marketplace they serve
PLUGIN_MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "cursor": ".cursor-plugin/plugin.json",
}
# RELEASING.md lists a Claude manifest for every plugin, so a missing one is an
# error. Cursor lists a deliberate subset of the plugins (#93), so its manifest
# is optional per plugin and its absence is checked against that marketplace's
# listing instead.
REQUIRED_PLUGIN_MANIFESTS = {"claude"}

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


def entry_folder(source: object) -> str:
    """The plugin folder an entry's `source` points at, as a name under skills/.

    Handles a relative path ("./skills/dbt", used by Cursor) and a
    `git-subdir` object ({"path": "skills/dbt", ...}, used by Claude).
    """
    if isinstance(source, dict):
        source = source.get("path", "")
    return Path(source if isinstance(source, str) else "").name


def read_marketplace_entries(path: Path) -> dict[str, str]:
    """Return plugin folder name -> declared entry name from a marketplace file."""
    marketplace = json.loads(path.read_text())
    entries: dict[str, str] = {}
    for plugin in marketplace.get("plugins", []):
        entries[entry_folder(plugin.get("source", ""))] = plugin.get("name", "")
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
                if marketplace in REQUIRED_PLUGIN_MANIFESTS:
                    errors.append(
                        f"skills/{folder}/{manifest_rel} is missing — every plugin "
                        f"needs a {marketplace} manifest (see RELEASING.md)"
                    )
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
                f"({detail}) — versions change only in release PRs, see RELEASING.md"
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
def nested_keys(mapping: dict) -> set[str]:
    """Every mapping key below the top level, at any depth.

    Walks lists too, so `metadata: [{user-invocable: false}]` is seen. String
    values are never walked, so a description that merely mentions a key name
    is text, not structure — which a line scanner could not reliably tell.
    """
    found: set[str] = set()

    def walk(node: object, depth: int) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if depth > 0:
                    found.add(str(key))
                walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth)

    walk(mapping, 0)
    return found


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

        try:
            parsed = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            detail = str(exc).replace("\n", " ")
            errors.append(f"Skill '{skill_name}': frontmatter is not valid YAML — {detail}")
            continue

        if not isinstance(parsed, dict):
            errors.append(
                f"Skill '{skill_name}': frontmatter must be a mapping of fields, "
                f"got {type(parsed).__name__}"
            )
            continue

        # YAML resolves unquoted `on`/`yes` keys to booleans, so normalise to
        # text before comparing: such a key is simply an unexpected field.
        top = {str(key): value for key, value in parsed.items()}
        fields = set(top)

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
            elif top[required] is None:
                errors.append(
                    f"Skill '{skill_name}': frontmatter '{required}' is empty"
                )
            elif not isinstance(top[required], str):
                # e.g. `description: false` parses as a bool, not a description
                errors.append(
                    f"Skill '{skill_name}': frontmatter '{required}' must be text, "
                    f"got {type(top[required]).__name__} ({top[required]!r})"
                )
            elif not top[required].strip():
                errors.append(
                    f"Skill '{skill_name}': frontmatter '{required}' is empty"
                )

        declared = top.get("name")
        if isinstance(declared, str) and declared.strip():
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
        # silently does nothing rather than failing loudly. Flag it even when a
        # top-level copy exists: the nested one is still dead, misleading config.
        if "user-invocable" in nested_keys(parsed):
            errors.append(
                f"Skill '{skill_name}': 'user-invocable' is nested (likely under "
                f"'metadata:') — it must be a top-level field"
            )

    return errors


# --------------------------------------------------------------------------- #
# Check 7: lockstep versions
# --------------------------------------------------------------------------- #


def parse_version(value: object) -> tuple[int, ...] | None:
    """A dotted numeric version as a comparable tuple, or None if unparseable."""
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def latest_release() -> str | None:
    """The highest version changie has released, without its 'v', or None.

    Read from the per-release files changie writes (`.changes/v2.0.0.md`) — the
    same source `changie latest` uses — so no changie binary is needed here.
    """
    versions = [
        p.stem.removeprefix("v")
        for p in CHANGES_DIR.glob("v*.md")
        if parse_version(p.stem.removeprefix("v")) is not None
    ]
    return max(versions, key=parse_version, default=None)


def find_versioned_files() -> list[Path]:
    """Every file that carries the repo version (see VERSIONED_FILE_GLOBS)."""
    files: list[Path] = []
    for pattern in VERSIONED_FILE_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return files


def read_version(path: Path) -> object:
    """The top-level `version` of a JSON or YAML file, or None if it has none."""
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text())
        else:
            data = yaml.safe_load(path.read_text())
    except (json.JSONDecodeError, yaml.YAMLError):
        return None
    return data.get("version") if isinstance(data, dict) else None


def check_lockstep_versions() -> list[str]:
    """Every versioned file must carry the version of the latest release.

    Versions move only in release PRs, where `changie merge` rewrites all of
    them at once through the replacements in .changie.yaml. A feature PR that
    bumps a version by hand, or a versioned file that a replacement misses,
    leaves it out of step with `.changes/v<version>.md` and fails here.
    """
    files = find_versioned_files()
    if not files:
        return ["No versioned files found — check VERSIONED_FILE_GLOBS"]

    expected = latest_release()
    if expected is None:
        return [
            (
                f"No release found in {CHANGES_DIR.relative_to(REPO_ROOT)}/ — "
                f"expected at least one v<version>.md written by `changie batch`"
            )
        ]

    errors: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT)
        version = read_version(path)
        if version is None:
            errors.append(f"{rel} has no top-level 'version'")
        elif version != expected:
            errors.append(
                f"{rel} is at version {version!r} but the latest release is "
                f"{expected!r}. Versions change only in release PRs — see RELEASING.md"
            )
    return errors


# --------------------------------------------------------------------------- #
# Check 8: Claude marketplace sources
# --------------------------------------------------------------------------- #


def check_marketplace_sources() -> list[str]:
    """Every Claude marketplace entry must fetch its plugin from the release branch.

    Claude Code reads marketplace.json from main. With a relative-path source
    it would also serve the plugin from main, unreleased changes included, and
    under the previous version number. A `git-subdir` source on the release
    branch serves only released content. Pinning a tag instead would point
    main at a tag that does not exist until release.yml creates it.
    """
    if not MARKETPLACE_JSON.exists():
        return []  # check_marketplace reports this
    rel = MARKETPLACE_JSON.relative_to(REPO_ROOT)
    errors: list[str] = []
    for plugin in json.loads(MARKETPLACE_JSON.read_text()).get("plugins", []):
        name, source = plugin.get("name"), plugin.get("source")
        if not isinstance(source, dict) or source.get("source") != "git-subdir":
            errors.append(
                f"{rel}: plugin '{name}' must use a 'git-subdir' source on the "
                f"{RELEASE_BRANCH!r} branch, not {source!r}"
            )
            continue
        if source.get("url") != REPO_GIT_URL:
            errors.append(
                f"{rel}: plugin '{name}' fetches from {source.get('url')!r}; "
                f"expected {REPO_GIT_URL!r}"
            )
        if source.get("ref") != RELEASE_BRANCH or "sha" in source:
            errors.append(
                f"{rel}: plugin '{name}' must fetch ref {RELEASE_BRANCH!r} with no "
                f"'sha', not ref {source.get('ref')!r}"
                + (f" and sha {source['sha']!r}" if "sha" in source else "")
                + " — see RELEASING.md"
            )
    return errors


# --------------------------------------------------------------------------- #
# Check 9: changelog entries (vs. base branch)
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


def git_changed_files(base: str, diff_filter: str | None = None) -> set[str]:
    filter_args = [f"--diff-filter={diff_filter}"] if diff_filter else []
    result = subprocess.run(
        ["git", "diff", "--name-only", *filter_args, f"{base}...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return set()
    return set(result.stdout.strip().splitlines())


class DiffContext(NamedTuple):
    """The git state the changelog-entry check needs, resolved once.

    `changed` and `added` are None when there is nothing to compare against, in
    which case `errors` explains why — or is empty when skipping is the
    correct, silent outcome (running on the base branch itself). `added` is the
    subset of `changed` that is new, so that editing an old fragment does not
    pass for adding one.
    """

    base_branch: str
    changed: set[str] | None
    added: set[str] | None
    errors: list[str]


def diff_context(base_branch: str) -> DiffContext:
    """Resolve the diff against `base_branch`, or say why we cannot."""
    current = git_current_branch()
    if current is None:
        return DiffContext(base_branch, None, None, ["Could not determine current git branch"])
    if current == base_branch:
        return DiffContext(base_branch, None, None, [])  # nothing to compare on the base branch
    if not git_branch_exists(base_branch):
        return DiffContext(
            base_branch,
            None,
            None,
            [f"Base branch '{base_branch}' not found — skipping changelog checks"],
        )
    return DiffContext(
        base_branch,
        git_changed_files(base_branch),
        git_changed_files(base_branch, diff_filter="A"),
        [],
    )


def check_changelog_entries(diff: DiffContext) -> list[str]:
    """Shipped changes need a changie fragment; only releases touch CHANGELOG.md.

    A release PR is recognised by what it contains — a new `.changes/v*.md` —
    rather than by its branch name or author, so a release cut by hand passes
    the same way as one opened by the release workflow.
    """
    if diff.changed is None:
        return diff.errors

    changes_rel = str(CHANGES_DIR.relative_to(REPO_ROOT))
    release_files = [f for f in diff.added if re.fullmatch(rf"{changes_rel}/v[^/]+\.md", f)]
    if release_files:
        return []

    errors: list[str] = []
    changelog_rel = str(CHANGELOG_MD.relative_to(REPO_ROOT))
    if changelog_rel in diff.changed:
        errors.append(
            f"{changelog_rel} changed outside a release. It is generated by "
            f"`changie merge` in the release PR — add a fragment with `changie new` instead"
        )

    skills_rel = str(SKILLS_DIR.relative_to(REPO_ROOT))
    shipped = sorted(f for f in diff.changed if f.startswith(f"{skills_rel}/"))
    fragments = [f for f in diff.added if f.startswith(f"{changes_rel}/unreleased/")]
    if shipped and not fragments:
        errors.append(
            f"{len(shipped)} file(s) under {skills_rel}/ changed but no changelog "
            f"fragment was added. Run `changie new` and pick the plugin as the "
            f"component. Changed: {', '.join(shipped)}"
        )
    return errors


# --------------------------------------------------------------------------- #
# Check 10: changelog fragments are well-formed
# --------------------------------------------------------------------------- #


def check_changelog_fragments() -> list[str]:
    """Every unreleased fragment must parse and name a known component and kind.

    `changie batch` fails outright on a fragment that is not valid YAML, and
    files one with no component under an empty heading, so either would only
    surface when a release is cut — long after the PR that introduced it.
    """
    if not CHANGIE_YAML.exists():
        return [".changie.yaml not found at repo root"]
    config = yaml.safe_load(CHANGIE_YAML.read_text()) or {}
    components = set(config.get("components") or [])
    kinds = {k.get("label") for k in config.get("kinds") or []}

    errors: list[str] = []
    for path in sorted((CHANGES_DIR / "unreleased").glob("*.yaml")):
        rel = path.relative_to(REPO_ROOT)
        try:
            fragment = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            errors.append(f"{rel} is not valid YAML: {e}".splitlines()[0])
            continue
        if not isinstance(fragment, dict):
            errors.append(f"{rel} is not a YAML mapping")
            continue
        if components and fragment.get("component") not in components:
            errors.append(
                f"{rel} has component {fragment.get('component')!r}; expected one "
                f"of {', '.join(sorted(components))}"
            )
        if fragment.get("kind") not in kinds:
            errors.append(
                f"{rel} has kind {fragment.get('kind')!r}; expected one of "
                f"{', '.join(sorted(kinds))}"
            )
        if not str(fragment.get("body") or "").strip():
            errors.append(f"{rel} has an empty body")
    return errors


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dbt-agent-skills repo")
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Branch to compare for the changelog-entry check (default: main)",
    )
    args = parser.parse_args()

    skills = find_all_skills()
    plugin_dirs = find_all_plugin_dirs()
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
            "Lockstep versions",
            check_lockstep_versions,
            lambda: (
                f"All {len(find_versioned_files())} versioned files are at "
                f"{latest_release()}, the latest release"
            ),
        ),
        (
            "Claude marketplace sources",
            check_marketplace_sources,
            lambda: f"All Claude marketplace entries fetch the {RELEASE_BRANCH!r} branch",
        ),
        (
            "Changelog entries",
            lambda: check_changelog_entries(diff),
            lambda: "Changelog entries are in place",
        ),
        (
            "Changelog fragments",
            check_changelog_fragments,
            lambda: (
                f"All {len(list((CHANGES_DIR / 'unreleased').glob('*.yaml')))} "
                f"unreleased fragments are well-formed"
            ),
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
