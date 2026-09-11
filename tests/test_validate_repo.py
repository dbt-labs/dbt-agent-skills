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


def test_frontmatter_allows_block_scalar_mentioning_user_invocable(vr, tmp_path):
    """A block scalar's body is free text, not structure.

    `description: |` followed by an indented line that merely looks like
    `user-invocable: ...` must not be read as a nested field.
    """
    # Deliberately NO top-level user-invocable: otherwise the nested-key check
    # short-circuits and the test cannot detect a scanner that misreads the
    # block scalar's body as structure.
    frontmatter = (
        "name: doing-a-thing\n"
        "description: |\n"
        "  Use when doing a thing. Configuration note:\n"
        "  user-invocable: false belongs at the top level, never in metadata."
    )
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_allows_block_scalar_nested_under_metadata(vr, tmp_path):
    """A block scalar's body is text at any depth, not just at the top level.

    `metadata:` -> `notes: |` -> indented text mentioning `user-invocable:`
    must not be read as a nested field.
    """
    frontmatter = (
        "name: doing-a-thing\n"
        "description: Use when doing a thing.\n"
        "metadata:\n"
        "  notes: |\n"
        "    user-invocable: false is only honoured at the top level.\n"
        "  author: dbt-labs"
    )
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_still_sees_keys_after_a_block_scalar_ends(vr, tmp_path):
    """Exiting the scalar must resume parsing, or real nested keys get missed."""
    frontmatter = (
        "name: doing-a-thing\n"
        "description: |\n"
        "  Use when doing a thing.\n"
        "metadata:\n"
        "  user-invocable: false"
    )
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


def test_frontmatter_ignores_inline_comment_after_name(vr, tmp_path):
    skill = make_skill(
        tmp_path, "doing-a-thing", "name: doing-a-thing  # keep in sync with the dir\ndescription: d"
    )
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_accepts_quoted_name(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", 'name: "doing-a-thing"\ndescription: d')
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


@pytest.mark.parametrize(
    "frontmatter,field",
    [
        ("name:\ndescription: d", "name"),
        ('name: ""\ndescription: d', "name"),
        ("name: doing-a-thing\ndescription:", "description"),
        ("name: doing-a-thing\ndescription: '  '", "description"),
    ],
)
def test_frontmatter_rejects_empty_required_values(vr, tmp_path, frontmatter, field):
    """An empty value is not a present value.

    An empty name also used to skip the kebab-case and directory-match checks
    entirely, so malformed frontmatter passed clean.
    """
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any(f"'{field}' is empty" in e for e in errors)


@pytest.mark.parametrize("marker", ["|", ">", "|-", ">-", "|+"])
def test_frontmatter_rejects_an_empty_block_scalar(vr, tmp_path, marker):
    """YAML decodes a body-less block scalar to an empty string.

    The scanner used to store the `|` marker as the value, which is truthy, so
    a required field with no content passed.
    """
    skill = make_skill(tmp_path, "doing-a-thing", f"name: doing-a-thing\ndescription: {marker}")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("'description' is empty" in e for e in errors)


def test_frontmatter_accepts_a_block_scalar_with_a_body(vr, tmp_path):
    skill = make_skill(
        tmp_path,
        "doing-a-thing",
        "name: doing-a-thing\ndescription: |\n  Use when doing a thing.\n  More detail.",
    )
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


def test_frontmatter_rejects_a_quoted_disallowed_key(vr, tmp_path):
    """`"author": me` is the same field as `author: me` and must not slip past."""
    skill = make_skill(
        tmp_path, "doing-a-thing", 'name: doing-a-thing\ndescription: d\n"author": me'
    )
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("unexpected frontmatter field(s) ['author']" in e for e in errors)


def test_frontmatter_accepts_a_quoted_allowed_key(vr, tmp_path):
    skill = make_skill(
        tmp_path, "doing-a-thing", '"name": doing-a-thing\n"description": Use when doing.'
    )
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


@pytest.mark.parametrize(
    "value,kind",
    [("false", "bool"), ("true", "bool"), ("42", "int"), ("1.5", "float")],
)
def test_frontmatter_rejects_a_non_text_description(vr, tmp_path, value, kind):
    """`description: false` is a boolean, not a description.

    The previous line scanner read every unquoted scalar as text and could not
    tell; YAML type resolution is what a real parser is for.
    """
    skill = make_skill(tmp_path, "doing-a-thing", f"name: doing-a-thing\ndescription: {value}")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any(f"'description' must be text, got {kind}" in e for e in errors)


def test_frontmatter_rejects_a_non_text_name(vr, tmp_path):
    skill = make_skill(tmp_path, "true", "name: true\ndescription: Use when doing.")
    errors = vr.check_frontmatter({"true": skill})
    assert any("'name' must be text" in e for e in errors)


def test_frontmatter_normalises_yaml_boolean_keys(vr, tmp_path):
    """YAML 1.1 resolves an unquoted `on:` key to True; it is still a bad field."""
    skill = make_skill(
        tmp_path, "doing-a-thing", "name: doing-a-thing\ndescription: Use when doing.\non: nope"
    )
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("unexpected frontmatter field(s) ['True']" in e for e in errors)


def test_frontmatter_reports_invalid_yaml(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", "name: doing-a-thing\n  bad: [unclosed")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert len(errors) == 1
    assert "not valid YAML" in errors[0]


def test_frontmatter_rejects_a_non_mapping(vr, tmp_path):
    skill = make_skill(tmp_path, "doing-a-thing", "- just\n- a\n- list")
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert len(errors) == 1
    assert "must be a mapping" in errors[0]


def test_frontmatter_sees_nested_key_in_a_sequence_of_mappings(vr, tmp_path):
    """nested_keys walks lists, so a mapping inside a sequence is still nested."""
    skill = make_skill(
        tmp_path,
        "doing-a-thing",
        "name: doing-a-thing\ndescription: d\nmetadata:\n  - user-invocable: false",
    )
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


def test_frontmatter_sees_nested_key_in_a_flow_mapping(vr, tmp_path):
    """Flow style is now parsed, so the placement rule applies to it properly.

    The hand-rolled scanner could not see inside `{...}` and had to reject flow
    style outright; a real parse validates it like any other mapping.
    """
    skill = make_skill(
        tmp_path,
        "doing-a-thing",
        "name: doing-a-thing\ndescription: d\nmetadata: {user-invocable: false}",
    )
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


def test_frontmatter_accepts_a_valid_flow_mapping(vr, tmp_path):
    skill = make_skill(
        tmp_path,
        "doing-a-thing",
        "name: doing-a-thing\ndescription: Use when doing.\nmetadata: {author: dbt-labs}",
    )
    assert vr.check_frontmatter({"doing-a-thing": skill}) == []


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


def test_frontmatter_rejects_nested_user_invocable_as_a_sequence_item(vr, tmp_path):
    """`metadata:` -> `- user-invocable: false` is a nested mapping in YAML.

    A key written as a sequence item does not start immediately after the
    indentation, so the scanner used to skip the line entirely.
    """
    frontmatter = "name: doing-a-thing\ndescription: d\nmetadata:\n  - user-invocable: false"
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


def test_frontmatter_rejects_nested_user_invocable_even_with_a_top_level_copy(vr, tmp_path):
    """The nested copy is dead config either way, and misleading to a reader."""
    frontmatter = (
        "name: doing-a-thing\ndescription: d\nuser-invocable: false\n"
        "metadata:\n  user-invocable: false"
    )
    skill = make_skill(tmp_path, "doing-a-thing", frontmatter)
    errors = vr.check_frontmatter({"doing-a-thing": skill})
    assert any("must be a top-level field" in e for e in errors)


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


def test_coherence_rejects_a_missing_version(vr, coherence_repo):
    """Both manifests omitting 'version' used to collapse to {None} and pass."""
    plugin_dirs, _, _ = coherence_repo
    for marketplace in ("claude", "cursor"):
        path = plugin_dirs["dbt"] / vr.PLUGIN_MANIFESTS[marketplace]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "dbt"}))
    errors = vr.check_manifest_coherence(plugin_dirs)
    assert len(errors) == 2
    assert all("no usable 'version'" in e for e in errors)


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
# diff_context — the skip rules shared by both version checks
# --------------------------------------------------------------------------- #


@pytest.fixture
def stub_git(vr, monkeypatch):
    """Stub the git primitives so no real history is needed."""

    def configure(current="feature", base_exists=True, changed=("a.md",)):
        monkeypatch.setattr(vr, "git_current_branch", lambda: current)
        monkeypatch.setattr(vr, "git_branch_exists", lambda b: base_exists)
        monkeypatch.setattr(vr, "git_changed_files", lambda b: set(changed))

    return configure


def test_diff_context_resolves_the_diff(vr, stub_git):
    stub_git(changed=("skills/dbt/skills/a-skill/SKILL.md",))
    diff = vr.diff_context("main")
    assert diff.base_branch == "main"
    assert diff.changed == {"skills/dbt/skills/a-skill/SKILL.md"}
    assert diff.errors == []


def test_diff_context_skips_silently_on_the_base_branch(vr, stub_git):
    stub_git(current="main")
    diff = vr.diff_context("main")
    assert diff.changed is None
    assert diff.errors == []  # skipping here is correct, not worth reporting


def test_diff_context_reports_a_missing_base_branch(vr, stub_git):
    stub_git(base_exists=False)
    diff = vr.diff_context("main")
    assert diff.changed is None
    assert len(diff.errors) == 1 and "not found" in diff.errors[0]


def test_diff_context_reports_an_undeterminable_branch(vr, stub_git):
    stub_git(current=None)
    diff = vr.diff_context("main")
    assert diff.changed is None
    assert diff.errors == ["Could not determine current git branch"]


def test_context_errors_are_reported_exactly_once(vr, stub_git, tile_plugin_dirs):
    """The plugin check owns these; the tile check must stay silent about them.

    Otherwise a missing base branch would be reported twice in one run.
    """
    stub_git(base_exists=False)
    diff = vr.diff_context("main")
    plugin_errors = vr.check_version_increments(tile_plugin_dirs, diff)
    tile_errors = vr.check_tile_version_increment(diff)
    assert len(plugin_errors) == 1
    assert tile_errors == []


# --------------------------------------------------------------------------- #
# check_tile_version_increment
# --------------------------------------------------------------------------- #


@pytest.fixture
def tile_plugin_dirs(tmp_path):
    return {name: tmp_path / "skills" / name for name in ("dbt", "dbt-migration")}


@pytest.fixture
def tile_repo(vr, tmp_path, monkeypatch):
    """Point the module at a synthetic repo and build a DiffContext directly.

    The check no longer resolves git state itself, so these tests need no git
    stubs — that logic is covered by the diff_context tests above.
    """
    tile_json = tmp_path / "tile.json"
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(vr, "TILE_JSON", tile_json)

    def configure(head_version, base_version, changed):
        tile_json.write_text(json.dumps({"version": head_version}))
        monkeypatch.setattr(
            vr, "git_file_at_ref", lambda ref, path: json.dumps({"version": base_version})
        )
        return vr.DiffContext("main", set(changed), [])

    return configure


def test_tile_rejects_skill_change_without_bump(vr, tile_repo):
    diff = tile_repo("1.5.1", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    errors = vr.check_tile_version_increment(diff)
    assert len(errors) == 1
    assert "is not an increase over the base" in errors[0]


def test_tile_accepts_skill_change_with_bump(vr, tile_repo):
    diff = tile_repo("1.5.2", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    assert vr.check_tile_version_increment(diff) == []


def test_tile_ignores_changes_outside_skills(vr, tile_repo):
    diff = tile_repo("1.5.1", "1.5.1", ["README.md", "scripts/validate_repo.py"])
    assert vr.check_tile_version_increment(diff) == []


def test_tile_ignores_plugin_manifest_only_changes(vr, tile_repo):
    """A manifest bump changes nothing Tessl publishes, so it must not force a bump.

    Only files under a plugin's skills/ directory count as skill content — the
    same rule the per-plugin version check applies.
    """
    diff = tile_repo(
        "1.5.1",
        "1.5.1",
        [
            "skills/dbt/.claude-plugin/plugin.json",
            "skills/dbt/.cursor-plugin/plugin.json",
            "skills/dbt-migration/.claude-plugin/plugin.json",
        ],
    )
    assert vr.check_tile_version_increment(diff) == []


def test_tile_counts_only_skill_content_in_its_message(vr, tile_repo):
    """Mixed change set: the manifest bumps must not be counted or listed."""
    diff = tile_repo(
        "1.5.1",
        "1.5.1",
        [
            "skills/dbt/.claude-plugin/plugin.json",
            "skills/dbt/skills/a-skill/SKILL.md",
            "skills/dbt-migration/skills/b-skill/SKILL.md",
        ],
    )
    errors = vr.check_tile_version_increment(diff)
    assert len(errors) == 1
    assert "2 skill file(s) changed" in errors[0]
    assert "plugin.json" not in errors[0]


def test_tile_catches_a_deleted_plugin(vr, tile_repo):
    """Deleting a whole plugin changes the tile's skill list, so it needs a bump.

    Matching on existing plugin directories missed this: the deleted plugin's
    files are in the diff but its directory is gone from the working tree.
    """
    diff = tile_repo(
        "1.5.1",
        "1.5.1",
        [
            "skills/dbt-extras/skills/removed-skill/SKILL.md",
            "skills/dbt-extras/.claude-plugin/plugin.json",
        ],
    )
    errors = vr.check_tile_version_increment(diff)
    assert len(errors) == 1
    assert "1 skill file(s) changed" in errors[0]


def test_tile_ignores_a_bare_skills_dir_path(vr, tile_repo):
    """`skills/<plugin>/skills/` itself is not skill content; it needs a file under it."""
    diff = tile_repo("1.5.1", "1.5.1", ["skills/dbt/skills/"])
    assert vr.check_tile_version_increment(diff) == []


def test_tile_skips_when_there_is_nothing_to_compare(vr, tile_repo):
    tile_repo("1.5.1", "1.5.1", [])
    assert vr.check_tile_version_increment(vr.DiffContext("main", None, [])) == []


# --------------------------------------------------------------------------- #
# check_version_increments — the per-plugin path
# --------------------------------------------------------------------------- #


@pytest.fixture
def plugin_version_repo(vr, tmp_path, monkeypatch):
    """A synthetic plugin whose manifest version can be set at both ends."""
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "SKILLS_DIR", tmp_path / "skills")
    plugin_dir = tmp_path / "skills" / "dbt"
    manifest = plugin_dir / vr.PLUGIN_MANIFESTS["claude"]
    manifest.parent.mkdir(parents=True)

    def configure(head_version, base_version, changed=("skills/dbt/skills/a/SKILL.md",)):
        manifest.write_text(json.dumps({"name": "dbt", "version": head_version}))
        monkeypatch.setattr(
            vr,
            "git_file_at_ref",
            lambda ref, path: None
            if base_version is None
            else json.dumps({"name": "dbt", "version": base_version}),
        )
        return {"dbt": plugin_dir}, vr.DiffContext("main", set(changed), [])

    return configure


def test_plugin_version_accepts_an_increase(vr, plugin_version_repo):
    dirs, diff = plugin_version_repo("1.5.1", "1.5.0")
    assert vr.check_version_increments(dirs, diff) == []


def test_plugin_version_rejects_an_unchanged_version(vr, plugin_version_repo):
    dirs, diff = plugin_version_repo("1.5.0", "1.5.0")
    errors = vr.check_version_increments(dirs, diff)
    assert len(errors) == 1
    assert "is not an increase over the base" in errors[0]


def test_plugin_version_rejects_a_downgrade(vr, plugin_version_repo):
    """Differs from the base, so an equality test would have passed it."""
    dirs, diff = plugin_version_repo("1.4.0", "1.5.0")
    errors = vr.check_version_increments(dirs, diff)
    assert len(errors) == 1
    assert "is not an increase over the base" in errors[0]


def test_plugin_version_reports_an_unparseable_version(vr, plugin_version_repo):
    dirs, diff = plugin_version_repo("nightly", "1.5.0")
    errors = vr.check_version_increments(dirs, diff)
    assert len(errors) == 1
    assert "cannot compare versions" in errors[0]


def test_plugin_version_ignores_non_skill_changes(vr, plugin_version_repo):
    dirs, diff = plugin_version_repo(
        "1.5.0", "1.5.0", changed=("skills/dbt/.claude-plugin/plugin.json", "README.md")
    )
    assert vr.check_version_increments(dirs, diff) == []


def test_plugin_version_skips_a_new_plugin(vr, plugin_version_repo):
    """No manifest at the base ref means the plugin is new; nothing to compare."""
    dirs, diff = plugin_version_repo("1.0.0", None)
    assert vr.check_version_increments(dirs, diff) == []


# --------------------------------------------------------------------------- #
# version_increased
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "current,base,expected",
    [
        ("1.5.2", "1.5.1", True),
        ("1.6.0", "1.5.9", True),
        ("2.0.0", "1.9.9", True),
        ("1.5.1", "1.5.1", False),   # unchanged
        ("1.5.1", "1.5.2", False),   # downgrade
        ("1.4.0", "1.5.0", False),   # downgrade
        ("1.10.0", "1.9.0", True),   # numeric, not lexicographic
        ("1.9.0", "1.10.0", False),
        ("1.5", "1.5.1", False),
        ("v1.5.2", "1.5.1", None),   # unparseable
        ("1.5.2-rc1", "1.5.1", None),
        (None, "1.5.1", None),
        ("1.5.2", None, None),
    ],
)
def test_version_increased(vr, current, base, expected):
    assert vr.version_increased(current, base) is expected


def test_tile_rejects_a_version_downgrade(vr, tile_repo):
    """An equality test would pass this: 1.5.1 differs from 1.5.2."""
    diff = tile_repo("1.5.1", "1.5.2", ["skills/dbt/skills/a-skill/SKILL.md"])
    errors = vr.check_tile_version_increment(diff)
    assert len(errors) == 1
    assert "is not an increase over the base" in errors[0]


def test_tile_reports_an_unparseable_version(vr, tile_repo):
    diff = tile_repo("nightly", "1.5.1", ["skills/dbt/skills/a-skill/SKILL.md"])
    errors = vr.check_tile_version_increment(diff)
    assert len(errors) == 1
    assert "Cannot compare" in errors[0]


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
