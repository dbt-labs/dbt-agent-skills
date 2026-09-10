"""Tests for scripts/validate_repo.py.

The script is a standalone stdlib-only file rather than a package, so it is
loaded by path. Checks that read the repo layout do so through module-level
constants, which these tests point at a synthetic repo in tmp_path.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_repo.py"


@pytest.fixture(scope="module")
def vr():
    spec = importlib.util.spec_from_file_location("validate_repo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def make_skill(parent: Path, dir_name: str, frontmatter: str | None) -> Path:
    """Create a skill dir; frontmatter=None writes a SKILL.md with none at all."""
    skill_dir = parent / dir_name
    skill_dir.mkdir(parents=True)
    body = "# Heading\n" if frontmatter is None else f"---\n{frontmatter}\n---\n\n# Heading\n"
    (skill_dir / "SKILL.md").write_text(body)
    return skill_dir


def write_marketplace(path: Path, folders: list[str], names: dict[str, str] | None = None):
    names = names or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "dbt-agent-marketplace",
                "plugins": [
                    {"name": names.get(f, f), "source": f"./skills/{f}"} for f in folders
                ],
            }
        )
    )


def write_manifest(vr, plugin_dir: Path, marketplace: str, name: str, version: str):
    path = plugin_dir / vr.PLUGIN_MANIFESTS[marketplace]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "version": version}))


# --------------------------------------------------------------------------- #
# check_frontmatter
# --------------------------------------------------------------------------- #


def test_frontmatter_accepts_a_valid_skill(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", "name: doing-a-thing\ndescription: Use when doing a thing.")
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_accepts_block_scalar_and_nested_metadata(vr, tmp_path):
    """Regression guard: top-level keys are found by regex, not a YAML parser.

    A folded description whose continuation lines contain a colon, alongside a
    nested metadata block and a legitimate top-level user-invocable, must not
    be mistaken for extra top-level fields.
    """
    frontmatter = (
        "name: doing-a-thing\n"
        "description: >\n"
        "  A description that wraps across lines\n"
        "  and contains a colon: like this.\n"
        "metadata:\n"
        "  author: dbt-labs\n"
        "user-invocable: false"
    )
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_rejects_unexpected_top_level_fields(vr, tmp_path):
    skill = make_skill(
        tmp_path, "doing-a-thing", "name: doing-a-thing\ndescription: d\nversion: 1.0.0\nauthor: me"
    )
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert len(errors) == 1
    assert "'author', 'version'" in errors[0].replace('"', "'").replace("[", "").replace("]", "")


def test_frontmatter_rejects_missing_frontmatter(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", None)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert len(errors) == 1
    assert "no YAML frontmatter" in errors[0]


def test_frontmatter_rejects_missing_description(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", "name: doing-a-thing")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("missing 'description'" in e for e in errors)


@pytest.mark.parametrize("bad_name", ["Doing_A_Thing", "DoingAThing", "doing a thing", "doing--a-thing", "-doing"])
def test_frontmatter_rejects_non_kebab_case_names(vr, tmp_path, bad_name):
    skill = make_skill(tmp_path, bad_name, f"name: {bad_name}\ndescription: d")
    errors = vr.check_frontmatter({bad_name: skill})
    assert any("must be lowercase" in e for e in errors)


def test_frontmatter_rejects_name_not_matching_directory(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", "name: something-else\ndescription: d")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("does not match its directory" in e for e in errors)


def test_frontmatter_rejects_nested_user_invocable(vr, tmp_path):
    frontmatter = "name: doing-a-thing\ndescription: d\nmetadata:\n  user-invocable: false"
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


# --------------------------------------------------------------------------- #
# check_cursor_marketplace
# --------------------------------------------------------------------------- #


@pytest.fixture
def cursor_repo(vr, tmp_path, monkeypatch):
    """A synthetic repo with three plugin folders and a Cursor marketplace file."""
    skills_dir = tmp_path / "skills"
    plugin_dirs = {}
    for name in ("dbt", "dbt-migration", "dbt-extras"):
        d = skills_dir / name
        d.mkdir(parents=True)
        plugin_dirs[name] = d
    cursor_json = tmp_path / ".cursor-plugin" / "marketplace.json"
    monkeypatch.setattr(vr, "CURSOR_MARKETPLACE_JSON", cursor_json)
    monkeypatch.setattr(vr, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    return plugin_dirs, cursor_json


def test_cursor_accepts_listed_plugin_with_manifest(vr, cursor_repo):
    plugin_dirs, cursor_json = cursor_repo
    write_marketplace(cursor_json, ["dbt"])
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.0.0")
    assert vr.check_cursor_marketplace(plugin_dirs) == []


def test_cursor_allows_deliberate_subset(vr, cursor_repo):
    """Cursor lists only `dbt` on purpose (#93) — unlisted folders are not errors."""
    plugin_dirs, cursor_json = cursor_repo
    write_marketplace(cursor_json, ["dbt"])
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.0.0")
    # dbt-migration and dbt-extras have no Cursor manifest and are not listed
    assert vr.check_cursor_marketplace(plugin_dirs) == []


def test_cursor_rejects_listing_without_manifest(vr, cursor_repo):
    """The failure mode of adding a plugin to the marketplace but not shipping a manifest."""
    plugin_dirs, cursor_json = cursor_repo
    write_marketplace(cursor_json, ["dbt", "dbt-migration"])
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.0.0")
    errors = vr.check_cursor_marketplace(plugin_dirs)
    assert len(errors) == 1
    assert "dbt-migration" in errors[0] and "is missing" in errors[0]


def test_cursor_rejects_listing_without_folder(vr, cursor_repo):
    plugin_dirs, cursor_json = cursor_repo
    write_marketplace(cursor_json, ["dbt", "ghost-plugin"])
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.0.0")
    errors = vr.check_cursor_marketplace(plugin_dirs)
    assert len(errors) == 1
    assert "ghost-plugin" in errors[0] and "no folder" in errors[0]


def test_cursor_rejects_orphaned_manifest(vr, cursor_repo):
    plugin_dirs, cursor_json = cursor_repo
    write_marketplace(cursor_json, ["dbt"])
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.0.0")
    write_manifest(vr, plugin_dirs["dbt-extras"], "cursor", "dbt-extras", "1.0.0")
    errors = vr.check_cursor_marketplace(plugin_dirs)
    assert len(errors) == 1
    assert "dbt-extras" in errors[0] and "not listed" in errors[0]


def test_cursor_reports_missing_marketplace_file(vr, cursor_repo):
    plugin_dirs, _ = cursor_repo
    errors = vr.check_cursor_marketplace(plugin_dirs)
    assert errors == [".cursor-plugin/marketplace.json not found"]


# --------------------------------------------------------------------------- #
# check_manifest_coherence
# --------------------------------------------------------------------------- #


@pytest.fixture
def coherence_repo(vr, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    plugin_dir = skills_dir / "dbt"
    plugin_dir.mkdir(parents=True)
    claude_json = tmp_path / ".claude-plugin" / "marketplace.json"
    cursor_json = tmp_path / ".cursor-plugin" / "marketplace.json"
    monkeypatch.setattr(vr, "MARKETPLACE_JSON", claude_json)
    monkeypatch.setattr(vr, "CURSOR_MARKETPLACE_JSON", cursor_json)
    write_marketplace(claude_json, ["dbt"])
    write_marketplace(cursor_json, ["dbt"])
    return {"dbt": plugin_dir}, claude_json, cursor_json


def test_coherence_accepts_matching_versions(vr, coherence_repo):
    plugin_dirs, _, _ = coherence_repo
    write_manifest(vr, plugin_dirs["dbt"], "claude", "dbt", "1.5.1")
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.5.1")
    assert vr.check_manifest_coherence(plugin_dirs) == []


def test_coherence_rejects_version_drift(vr, coherence_repo):
    """The live bug this check was written for: cursor lagging claude."""
    plugin_dirs, _, _ = coherence_repo
    write_manifest(vr, plugin_dirs["dbt"], "claude", "dbt", "1.5.0")
    write_manifest(vr, plugin_dirs["dbt"], "cursor", "dbt", "1.4.0")
    errors = vr.check_manifest_coherence(plugin_dirs)
    assert len(errors) == 1
    assert "claude=1.5.0" in errors[0] and "cursor=1.4.0" in errors[0]


def test_coherence_ignores_plugins_with_a_single_manifest(vr, coherence_repo):
    plugin_dirs, _, _ = coherence_repo
    write_manifest(vr, plugin_dirs["dbt"], "claude", "dbt", "1.5.0")
    assert vr.check_manifest_coherence(plugin_dirs) == []


def test_coherence_rejects_manifest_name_mismatch(vr, coherence_repo):
    plugin_dirs, _, _ = coherence_repo
    write_manifest(vr, plugin_dirs["dbt"], "claude", "dbt-renamed", "1.5.0")
    errors = vr.check_manifest_coherence(plugin_dirs)
    assert any("declares name 'dbt-renamed'" in e for e in errors)


def test_coherence_rejects_marketplace_entry_name_mismatch(vr, coherence_repo):
    plugin_dirs, claude_json, _ = coherence_repo
    write_marketplace(claude_json, ["dbt"], names={"dbt": "dbt-typo"})
    write_manifest(vr, plugin_dirs["dbt"], "claude", "dbt", "1.5.0")
    errors = vr.check_manifest_coherence(plugin_dirs)
    assert any("named 'dbt-typo'" in e for e in errors)


# --------------------------------------------------------------------------- #
# check_tile_version_increment
# --------------------------------------------------------------------------- #


@pytest.fixture
def tile_repo(vr, tmp_path, monkeypatch):
    """Synthetic repo plus stubbed git helpers, so no real history is needed."""
    tile_json = tmp_path / "tile.json"
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(vr, "TILE_JSON", tile_json)
    monkeypatch.setattr(vr, "git_current_branch", lambda: "feature")
    monkeypatch.setattr(vr, "git_branch_exists", lambda branch: True)

    def configure(head_version, base_version, changed):
        tile_json.write_text(json.dumps({"version": head_version}))
        monkeypatch.setattr(vr, "git_changed_files", lambda base: set(changed))
        monkeypatch.setattr(
            vr, "git_file_at_ref", lambda ref, path: json.dumps({"version": base_version})
        )

    return configure


def test_tile_rejects_skill_change_without_bump(vr, tile_repo):
    tile_repo("1.5.1", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    errors = vr.check_tile_version_increment("main")
    assert len(errors) == 1
    assert "was not incremented" in errors[0]


def test_tile_accepts_skill_change_with_bump(vr, tile_repo):
    tile_repo("1.5.2", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    assert vr.check_tile_version_increment("main") == []


def test_tile_ignores_changes_outside_skills(vr, tile_repo):
    tile_repo("1.5.1", "1.5.1", ["README.md", "scripts/validate_repo.py"])
    assert vr.check_tile_version_increment("main") == []


def test_tile_skips_on_the_base_branch(vr, tile_repo, monkeypatch):
    tile_repo("1.5.1", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    monkeypatch.setattr(vr, "git_current_branch", lambda: "main")
    assert vr.check_tile_version_increment("main") == []


def test_tile_skips_when_base_branch_is_absent(vr, tile_repo, monkeypatch):
    """The plugin version check already reports this; don't double-report."""
    tile_repo("1.5.1", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    monkeypatch.setattr(vr, "git_branch_exists", lambda branch: False)
    assert vr.check_tile_version_increment("main") == []


# --------------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------------- #


def test_real_repo_passes_layout_checks(vr):
    """Guards the checks against the repo as it actually stands.

    Version-increment checks are excluded: they diff against a base branch and
    are exercised by CI on a real PR, not here.
    """
    skills = vr.find_all_skills()
    plugin_dirs = vr.find_all_plugin_dirs()
    assert vr.check_tile_json(skills) == []
    assert vr.check_marketplace(plugin_dirs) == []
    assert vr.check_cursor_marketplace(plugin_dirs) == []
    assert vr.check_manifest_coherence(plugin_dirs) == []
    assert vr.check_file_references(skills) == []
    assert vr.check_frontmatter(skills) == []
