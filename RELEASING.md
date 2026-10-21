# Releasing

This document covers how changes in this repository are released and published to plugin marketplaces.

## How versioning works

The repo has **one version**, shared by everything that carries one:

| What | Files |
|------|-------|
| Claude plugins | `skills/*/.claude-plugin/plugin.json` |
| Cursor plugin | `skills/*/.cursor-plugin/plugin.json` |
| dbt packages | `skills/*/dbt_project.yml` |
| Tessl tile | `tile.json` |

Every release moves all of them to the same new version, even if a release only changed one plugin. You never edit these by hand: `changie merge` rewrites them through the `replacements` in [`.changie.yaml`](.changie.yaml). `scripts/validate_repo.py` fails CI if any of them disagrees with the latest release in `.changes/`.

If you add a new kind of versioned file, add it to both the `replacements` in `.changie.yaml` and `VERSIONED_FILE_GLOBS` in `scripts/validate_repo.py`.

`CHANGELOG.md` has one section per release. Inside each release, entries are grouped by **component**: one per plugin (`dbt`, `dbt-migration`, `dbt-extras`), plus `repo` for CI, scripts and docs. This is how you read the changelog for a single plugin.

## Between releases

Feature PRs add a changie fragment (`changie new`, see [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-changelog-entry)) and nothing else release-related. Fragments pile up in `.changes/unreleased/` until the next release. CI requires a new fragment on any PR that changes `skills/`, and rejects a PR that bumps a version or edits `CHANGELOG.md`.

## Cutting a release

1. Go to **Actions → Create release PR → Run workflow** on `main`.
   - **bump**: leave it on `auto` to derive the next version from the fragments' kinds. Any `Breaking Changes` makes it a major release, any `Features` a minor one, and anything else a patch. You can also force `major`, `minor` or `patch`.
   - **version**: optionally set an exact version such as `v2.1.0`. This overrides `bump`.
2. The workflow runs `changie batch` and `changie merge`, checks that every versioned file was bumped, and opens a `version: vX.Y.Z` PR from `release/vX.Y.Z`. The PR body contains the release notes.
3. Review the PR. You can edit the notes in `.changes/vX.Y.Z.md` and `CHANGELOG.md` on the release branch before you merge it.
4. Merge it. [`release.yml`](.github/workflows/release.yml) then:
   - tags the merge commit `vX.Y.Z` and creates a GitHub release from `.changes/vX.Y.Z.md`
   - moves the `stable` branch to the tag, which releases it to Claude Code users
   - publishes the Tessl tile at that tag
5. Do the manual marketplace step below (Cursor).

`release.yml` releases whatever `changie latest` reports and has no tag yet. If it fails part-way, re-run it from the Actions tab (it has a `workflow_dispatch` trigger) and it picks up where it stopped.

To cut a release by hand instead, run `changie batch <auto|vX.Y.Z> && changie merge` on a branch and open a PR from it. CI recognises any PR that adds a `.changes/v*.md` file as a release.

### One-time setup

- **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests** must be enabled for the release PR workflow.
- Protect the `stable` branch with a ruleset that blocks deletion and force pushes, and lets only GitHub Actions push to it. `release.yml` only ever fast-forwards it.
- A release PR opened with the default `GITHUB_TOKEN` does **not** trigger the Validate workflow. If Validate is a required check, add a `RELEASE_PR_TOKEN` secret: a GitHub App or fine-grained token with `contents: write` and `pull-requests: write`. The workflow uses it when it is present.

## Where releases go

### GitHub releases and dbt packages

Each release is a tag (`vX.Y.Z`) and a GitHub release. The dbt packages can be pinned to a tag:

```yaml
packages:
  - git: "https://github.com/dbt-labs/dbt-agent-skills.git"
    subdirectory: "skills/dbt"
    revision: vX.Y.Z
```

The packages are not on [dbt Hub](https://hub.getdbt.com). Hub lists one package per repository and reads `dbt_project.yml` from the repo root, while ours live in subdirectories.

### Claude Marketplace

Claude Code reads `.claude-plugin/marketplace.json` from `main`, but each entry fetches its plugin with a `git-subdir` source from the `stable` branch:

```json
"source": {
  "source": "git-subdir",
  "url": "https://github.com/dbt-labs/dbt-agent-skills.git",
  "path": "skills/dbt",
  "ref": "stable"
}
```

With a relative-path source (`"./skills/dbt"`), Claude Code would serve the plugin straight from `main`. Merged but unreleased changes would reach users, and a fresh install would get them under the previous version number. `stable` only ever points at a release tag, so Claude Code users only ever get released content.

`release.yml` moves `stable` to the new tag once it has created it. Until then, users keep getting the previous release, and if the workflow fails they keep getting it until a re-run finishes the job. The marketplace never points at a tag that doesn't exist yet, which is why the entries use a branch rather than the tag itself. This is the release-channel setup the [Claude Code docs](https://code.claude.com/docs/en/plugins/host-marketplace#run-release-channels) describe, and the one [Dagster's skills marketplace](https://github.com/dagster-io/skills) uses.

The `ref` never changes, so `marketplace.json` is not touched on release. Users get offered an update because the release changes the plugin's `version` in `plugin.json`, which is how Claude Code detects updates. `scripts/validate_repo.py` fails if any entry is not a `git-subdir` source on `stable`. The command users run to add the marketplace stays the same.

To test unreleased plugin changes locally, load the plugin directly. Adding this repo as a marketplace installs the released version, not your working copy:

```bash
claude --plugin-dir skills/dbt
```

### Cursor Plugin Marketplace

The dbt plugin is listed in the [Cursor plugin marketplace](https://www.cursor.com/plugins). After a release, notify the Cursor marketplace team so they can sync the listing:

- Email: marketplace-publishing@cursor.com

### Tessl

[Tessl](https://tessl.io) is published by `release.yml` at each release tag. It no longer publishes on every push to `main`. Skills are evaluated against Tessl's quality standards and added to their open registry.

**Troubleshooting:**

- `401 Unauthorized`: the `TESSL_API_TOKEN` secret has expired. Doug Beatty or Benoit Perigaud can generate a new token at tessl.io and update the secret in the repo settings. Then re-run the Release workflow.
- Eval parse errors: the `evals/` directory does not contain Tessl-format evals, so the workflow passes `--skip-evals` to skip them.

### skills.sh

[skills.sh](https://skills.sh) automatically scans this repository, so no manual action is needed.
