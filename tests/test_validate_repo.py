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


def test_coherence_requires_a_claude_manifest(vr, coherence_repo):
    """Every plugin needs one (RELEASING.md); nothing else caught its absence.

    check_marketplace only compares folder names, and the lockstep check
    finds manifests by glob, so it cannot notice one that is absent.
    """
    plugin_dirs, _, _ = coherence_repo
    errors = vr.check_manifest_coherence(plugin_dirs)
    assert any(".claude-plugin/plugin.json is missing" in e for e in errors)


def test_coherence_treats_a_cursor_manifest_as_optional(vr, coherence_repo):
    """Cursor lists a deliberate subset of plugins (#93), so absence is normal."""
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
# diff_context — the skip rules for the changelog-entry check
# --------------------------------------------------------------------------- #


@pytest.fixture
def stub_git(vr, monkeypatch):
    """Stub the git primitives so no real history is needed."""

    def configure(current="feature", base_exists=True, changed=("a.md",), added=()):
        monkeypatch.setattr(vr, "git_current_branch", lambda: current)
        monkeypatch.setattr(vr, "git_branch_exists", lambda b: base_exists)
        monkeypatch.setattr(
            vr,
            "git_changed_files",
            lambda b, diff_filter=None: set(added) if diff_filter == "A" else set(changed),
        )

    return configure


def test_diff_context_resolves_the_diff(vr, stub_git):
    stub_git(
        changed=("skills/dbt/skills/a-skill/SKILL.md", ".changes/unreleased/x.yaml"),
        added=(".changes/unreleased/x.yaml",),
    )
    diff = vr.diff_context("main")
    assert diff.base_branch == "main"
    assert diff.changed == {"skills/dbt/skills/a-skill/SKILL.md", ".changes/unreleased/x.yaml"}
    assert diff.added == {".changes/unreleased/x.yaml"}
    assert diff.errors == []


def test_diff_context_skips_silently_on_the_base_branch(vr, stub_git):
    stub_git(current="main")
    diff = vr.diff_context("main")
    assert diff.changed is None and diff.added is None
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


# --------------------------------------------------------------------------- #
# check_lockstep_versions
# --------------------------------------------------------------------------- #


@pytest.fixture
def lockstep_repo(vr, tmp_path, monkeypatch):
    """A synthetic repo with every kind of versioned file, all at one version."""
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "CHANGES_DIR", tmp_path / ".changes")
    (tmp_path / ".changes").mkdir()
    write_manifest(vr, tmp_path / "skills" / "dbt", "claude", "dbt", "2.0.0")
    write_manifest(vr, tmp_path / "skills" / "dbt", "cursor", "dbt", "2.0.0")
    write_manifest(vr, tmp_path / "skills" / "dbt-extras", "claude", "dbt-extras", "2.0.0")
    for plugin in ("dbt", "dbt-extras"):
        (tmp_path / "skills" / plugin / "dbt_project.yml").write_text(
            f'name: {plugin.replace("-", "_")}\nversion: "2.0.0"\n'
        )
    (tmp_path / "tile.json").write_text(json.dumps({"name": "t", "version": "2.0.0"}))

    def release(*versions):
        for v in versions:
            (tmp_path / ".changes" / f"{v}.md").write_text(f"## {v}\n")

    return tmp_path, release


def test_lockstep_accepts_files_at_the_latest_release(vr, lockstep_repo):
    _, release = lockstep_repo
    release("v1.0.0", "v2.0.0")
    assert vr.check_lockstep_versions() == []


def test_lockstep_finds_every_kind_of_versioned_file(vr, lockstep_repo):
    """Both marketplaces, the dbt packages and the tile — across every plugin."""
    root, _ = lockstep_repo
    found = {str(p.relative_to(root)) for p in vr.find_versioned_files()}
    assert found == {
        "skills/dbt/.claude-plugin/plugin.json",
        "skills/dbt/.cursor-plugin/plugin.json",
        "skills/dbt-extras/.claude-plugin/plugin.json",
        "skills/dbt/dbt_project.yml",
        "skills/dbt-extras/dbt_project.yml",
        "tile.json",
    }


def test_lockstep_rejects_a_hand_bumped_file(vr, lockstep_repo):
    """The old per-PR habit: one plugin bumped ahead of the release."""
    root, release = lockstep_repo
    release("v2.0.0")
    write_manifest(vr, root / "skills" / "dbt-extras", "claude", "dbt-extras", "2.0.1")
    errors = vr.check_lockstep_versions()
    assert len(errors) == 1
    assert "dbt-extras/.claude-plugin/plugin.json" in errors[0]
    assert "'2.0.1'" in errors[0] and "'2.0.0'" in errors[0]


def test_lockstep_rejects_a_file_left_behind_by_a_release(vr, lockstep_repo):
    """A versioned file the .changie.yaml replacements missed."""
    _, release = lockstep_repo
    release("v2.0.0", "v2.1.0")
    errors = vr.check_lockstep_versions()
    assert len(errors) == 6
    assert all("latest release is '2.1.0'" in e for e in errors)


def test_lockstep_compares_releases_numerically(vr, lockstep_repo):
    _, release = lockstep_repo
    release("v2.0.0", "v2.10.0", "v2.9.0")
    assert vr.latest_release() == "2.10.0"


def test_lockstep_ignores_files_that_are_not_releases(vr, lockstep_repo):
    """changie keeps its header template next to the release files."""
    root, release = lockstep_repo
    release("v2.0.0")
    (root / ".changes" / "header.tpl.md").write_text("# Changelog\n")
    (root / ".changes" / "vnext.md").write_text("")
    assert vr.latest_release() == "2.0.0"


def test_lockstep_reports_a_missing_version(vr, lockstep_repo):
    root, release = lockstep_repo
    release("v2.0.0")
    (root / "skills" / "dbt" / "dbt_project.yml").write_text("name: dbt_agent_skills\n")
    errors = vr.check_lockstep_versions()
    assert errors == ["skills/dbt/dbt_project.yml has no top-level 'version'"]


def test_lockstep_requires_a_release(vr, lockstep_repo):
    errors = vr.check_lockstep_versions()
    assert len(errors) == 1 and "No release found" in errors[0]


# --------------------------------------------------------------------------- #
# check_marketplace_sources
# --------------------------------------------------------------------------- #


@pytest.fixture
def sources_repo(vr, tmp_path, monkeypatch):
    claude_json = tmp_path / ".claude-plugin" / "marketplace.json"
    claude_json.parent.mkdir()
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "MARKETPLACE_JSON", claude_json)

    def write(*sources):
        claude_json.write_text(
            json.dumps(
                {"plugins": [{"name": f"p{i}", "source": s} for i, s in enumerate(sources)]}
            )
        )

    return write


def on_stable(ref="stable", **overrides):
    return {
        "source": "git-subdir",
        "url": "https://github.com/dbt-labs/dbt-agent-skills.git",
        "path": "skills/dbt",
        "ref": ref,
        **overrides,
    }


def test_sources_accept_entries_on_the_release_branch(vr, sources_repo):
    sources_repo(on_stable(), on_stable(path="skills/dbt-extras"))
    assert vr.check_marketplace_sources() == []


def test_sources_reject_a_relative_path_source(vr, sources_repo):
    """A relative path serves main, unreleased changes included."""
    sources_repo("./skills/dbt")
    errors = vr.check_marketplace_sources()
    assert len(errors) == 1 and "must use a 'git-subdir' source" in errors[0]


@pytest.mark.parametrize("ref", ["main", "v2.0.0", None])
def test_sources_reject_any_other_ref(vr, sources_repo, ref):
    """main serves unreleased changes; a tag on main can name a tag not yet created."""
    sources_repo(on_stable(ref=ref))
    errors = vr.check_marketplace_sources()
    assert len(errors) == 1 and f"not ref {ref!r}" in errors[0]


def test_sources_reject_a_sha_override(vr, sources_repo):
    """Claude Code checks out `sha` over `ref`, so a sha would silently win."""
    sources_repo(on_stable(sha="a" * 40))
    errors = vr.check_marketplace_sources()
    assert len(errors) == 1 and "and sha 'aaaa" in errors[0]


def test_sources_reject_another_repository(vr, sources_repo):
    sources_repo(on_stable(url="https://github.com/someone/fork.git"))
    errors = vr.check_marketplace_sources()
    assert len(errors) == 1 and "fork.git" in errors[0]


def test_sources_skip_a_missing_marketplace(vr, tmp_path, monkeypatch):
    monkeypatch.setattr(vr, "MARKETPLACE_JSON", tmp_path / "marketplace.json")
    assert vr.check_marketplace_sources() == []


@pytest.mark.parametrize(
    "source,folder",
    [
        ("./skills/dbt", "dbt"),
        ({"source": "git-subdir", "path": "skills/dbt-migration"}, "dbt-migration"),
        ({"source": "git-subdir"}, ""),
        (None, ""),
    ],
)
def test_entry_folder(vr, source, folder):
    assert vr.entry_folder(source) == folder


# --------------------------------------------------------------------------- #
# check_changelog_entries
# --------------------------------------------------------------------------- #


@pytest.fixture
def entries_repo(vr, tmp_path, monkeypatch):
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(vr, "CHANGES_DIR", tmp_path / ".changes")
    monkeypatch.setattr(vr, "CHANGELOG_MD", tmp_path / "CHANGELOG.md")

    def configure(changed, added=()):
        return vr.DiffContext("main", set(changed) | set(added), set(added), [])

    return configure


SKILL_FILE = "skills/dbt/skills/a-skill/SKILL.md"
FRAGMENT = ".changes/unreleased/Fixes-20261021-120000.yaml"


def test_entries_accept_a_skill_change_with_a_new_fragment(vr, entries_repo):
    diff = entries_repo([SKILL_FILE], added=[FRAGMENT])
    assert vr.check_changelog_entries(diff) == []


def test_entries_reject_a_skill_change_without_a_fragment(vr, entries_repo):
    diff = entries_repo([SKILL_FILE])
    errors = vr.check_changelog_entries(diff)
    assert len(errors) == 1
    assert "no changelog fragment" in errors[0] and SKILL_FILE in errors[0]


def test_entries_do_not_count_an_edited_old_fragment(vr, entries_repo):
    """Touching someone else's fragment is not a changelog entry for this PR."""
    diff = entries_repo([SKILL_FILE, FRAGMENT])
    assert len(vr.check_changelog_entries(diff)) == 1


def test_entries_cover_plugin_manifests_and_packages(vr, entries_repo):
    """Everything under skills/ ships, not only skill content."""
    diff = entries_repo(["skills/dbt/dbt_project.yml"])
    assert len(vr.check_changelog_entries(diff)) == 1


def test_entries_ignore_changes_that_do_not_ship(vr, entries_repo):
    diff = entries_repo(["README.md", "scripts/validate_repo.py", "evals/x.py"])
    assert vr.check_changelog_entries(diff) == []


def test_entries_reject_a_hand_edited_changelog(vr, entries_repo):
    diff = entries_repo(["CHANGELOG.md"], added=[FRAGMENT])
    errors = vr.check_changelog_entries(diff)
    assert len(errors) == 1 and "changed outside a release" in errors[0]


def test_entries_accept_a_release(vr, entries_repo):
    """A release PR rewrites CHANGELOG.md and versioned files and deletes fragments."""
    diff = entries_repo(
        ["CHANGELOG.md", "skills/dbt/.claude-plugin/plugin.json", FRAGMENT],
        added=[".changes/v2.1.0.md"],
    )
    assert vr.check_changelog_entries(diff) == []


def test_entries_do_not_treat_an_edited_release_file_as_a_release(vr, entries_repo):
    diff = entries_repo(["CHANGELOG.md", ".changes/v2.0.0.md"])
    assert len(vr.check_changelog_entries(diff)) == 1


def test_entries_report_context_errors(vr):
    diff = vr.DiffContext("main", None, None, ["Base branch 'main' not found"])
    assert vr.check_changelog_entries(diff) == ["Base branch 'main' not found"]


def test_entries_skip_when_there_is_nothing_to_compare(vr):
    assert vr.check_changelog_entries(vr.DiffContext("main", None, None, [])) == []


# --------------------------------------------------------------------------- #
# check_changelog_fragments
# --------------------------------------------------------------------------- #


CHANGIE_CONFIG = """\
components:
  - dbt
  - repo
kinds:
  - label: Features
    auto: minor
  - label: Fixes
    auto: patch
"""


@pytest.fixture
def fragments_repo(vr, tmp_path, monkeypatch):
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vr, "CHANGES_DIR", tmp_path / ".changes")
    monkeypatch.setattr(vr, "CHANGIE_YAML", tmp_path / ".changie.yaml")
    (tmp_path / ".changie.yaml").write_text(CHANGIE_CONFIG)
    unreleased = tmp_path / ".changes" / "unreleased"
    unreleased.mkdir(parents=True)

    def write(name, text):
        (unreleased / name).write_text(text)

    return write


def test_fragments_accept_a_valid_fragment(vr, fragments_repo):
    fragments_repo("a.yaml", "component: dbt\nkind: Fixes\nbody: Fix a thing\n")
    assert vr.check_changelog_fragments() == []


def test_fragments_reject_invalid_yaml(vr, fragments_repo):
    """The live bug: an unquoted `key: value` inside a body broke `changie batch`."""
    fragments_repo(
        "a.yaml",
        "component: dbt\nkind: Fixes\nbody: Fix gaps —\n    extend `static_analysis: off` guidance\n",
    )
    errors = vr.check_changelog_fragments()
    assert len(errors) == 1 and "is not valid YAML" in errors[0]


def test_fragments_reject_a_missing_component(vr, fragments_repo):
    """changie files these under an empty heading instead of failing."""
    fragments_repo("a.yaml", "kind: Fixes\nbody: Fix a thing\n")
    errors = vr.check_changelog_fragments()
    assert len(errors) == 1 and "component None" in errors[0]


def test_fragments_reject_an_unknown_component(vr, fragments_repo):
    fragments_repo("a.yaml", "component: dbt-typo\nkind: Fixes\nbody: Fix a thing\n")
    errors = vr.check_changelog_fragments()
    assert len(errors) == 1 and "'dbt-typo'" in errors[0]


def test_fragments_reject_an_unknown_kind(vr, fragments_repo):
    fragments_repo("a.yaml", "component: dbt\nkind: Bug Fix\nbody: Fix a thing\n")
    errors = vr.check_changelog_fragments()
    assert len(errors) == 1 and "'Bug Fix'" in errors[0]


def test_fragments_reject_an_empty_body(vr, fragments_repo):
    fragments_repo("a.yaml", "component: dbt\nkind: Fixes\nbody: ''\n")
    errors = vr.check_changelog_fragments()
    assert errors and "empty body" in errors[0]


# --------------------------------------------------------------------------- #
# Integration
# --------------------------------------------------------------------------- #


def test_real_repo_passes_layout_checks(vr):
    """Guards the checks against the repo as it actually stands.

    The changelog-entry check is excluded: it diffs against a base branch and
    is exercised by CI on a real PR, not here.
    """
    skills = vr.find_all_skills()
    plugin_dirs = vr.find_all_plugin_dirs()
    assert vr.check_tile_json(skills) == []
    assert vr.check_marketplace(plugin_dirs) == []
    assert vr.check_cursor_marketplace(plugin_dirs) == []
    assert vr.check_manifest_coherence(plugin_dirs) == []
    assert vr.check_file_references(skills) == []
    assert vr.check_frontmatter(skills) == []
    assert vr.check_lockstep_versions() == []
    assert vr.check_marketplace_sources() == []
    assert vr.check_changelog_fragments() == []
