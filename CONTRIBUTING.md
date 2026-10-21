# Contributing to dbt Agent Skills

Thank you for your interest in contributing to dbt Agent Skills! This guide will help you create, improve, and submit skills that help AI agents work effectively with dbt.

## Table of Contents

1. [About this Repository](#about-this-repository)
2. [How to Contribute](#how-to-contribute)
3. [Creating a New dbt Skill](#creating-a-new-dbt-skill)
4. [Adding a CHANGELOG Entry](#adding-a-changelog-entry)
5. [Style Guide](#style-guide)
6. [dbt Skill Ideas](#dbt-skill-ideas)
7. [Resources](#resources)
8. [Questions or Issues?](#questions-or-issues)
9. [License](#license)

## About this Repository

This repository contains Agent Skills for working with dbt. Skills follow the [Agent Skills specification](https://agentskills.io/specification) and help AI agents build models, create semantic layers, troubleshoot platform issues, and more.

## How to Contribute

There are several ways to contribute:

- **Add a new dbt skill**: Create skills for commands, workflows, or patterns you use frequently
- **Improve existing skills**: Enhance command examples, add selector patterns, or clarify instructions
- **Fix issues**: Help resolve incorrect commands or unclear documentation
- **Share dbt patterns**: Document your team's best practices or optimization techniques

## Creating a New dbt Skill

### 1. Create the Skill Folder

Create a new folder with a descriptive name using **gerund form** (verb + -ing):

```bash
mkdir -p skills/running-incremental-models
```

### 2. Create SKILL.md

Every skill must have a `SKILL.md` file following the Agent Skills specification:

```markdown
---
name: running-incremental-models
description: Use when running incremental dbt models or deciding between incremental and full refresh strategies
user-invocable: false
metadata:
  author: dbt-labs
---

# Running Incremental Models

This skill helps agents execute incremental dbt models effectively, understanding when to use full refresh and how to handle incremental logic.

## When to Use

- Running specific incremental models
- Forcing a full refresh of incremental models
- Testing incremental logic after changes
- Rebuilding corrupted incremental tables

## Commands

### Run All Incremental Models
\`\`\`bash
dbt run --select config.materialized:incremental
\`\`\`

### Full Refresh Incremental Models
\`\`\`bash
dbt run --select config.materialized:incremental --full-refresh
\`\`\`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running full refresh on large tables without need | Only use `--full-refresh` when data issues require it |
| Not testing incremental logic in dev first | Always validate in development before production |
```

### 3. Add Supporting Resources (Optional)

Include examples or helper content if needed:

```
running-incremental-models/
├── SKILL.md
└── examples/
    ├── incremental_model_example.sql
    └── selector_patterns.txt
```

## Adding a CHANGELOG Entry

Changes are released in batches, not one PR at a time (see [RELEASING.md](RELEASING.md)). Each PR records what it changed in a [changie](https://changie.dev) fragment, and the next release collects all fragments into `CHANGELOG.md`.

Any PR that changes a file under `skills/` must add a fragment, and CI checks for one. For PRs that change only CI, scripts or docs, a fragment is optional; use the `repo` component when you add one.

```bash
changie new
```

changie prompts for:

| Prompt | What to choose |
|--------|----------------|
| Component | The plugin you changed: `dbt`, `dbt-migration` or `dbt-extras`. Use `repo` for anything that does not ship in a plugin. If a PR changes two plugins, run `changie new` once per plugin. |
| Kind | `Breaking Changes` (renamed or removed skill, changed install path), `Features` (new skill or capability), `Fixes`, `Docs`, `Under the Hood`, `Dependencies` or `Security`. The kind sets the next version number, so a breaking change triggers a major release. |
| Body | One or two sentences for the user, written in the present tense. |
| Author / Issue | Your GitHub username, and the issue number (or `N/A`). |

Commit the generated `.changes/unreleased/*.yaml` file with your change.

To try your changes in Claude Code before they are released, run `claude --plugin-dir skills/<plugin>`. The marketplace serves the latest release, not `main`.

**Do not** bump any `version` field or edit `CHANGELOG.md` by hand. Every versioned file (plugin manifests, `tile.json`, `dbt_project.yml`) carries the same repo version, which changes only in a release PR. CI rejects a hand bump.

## Style Guide

### Naming Conventions

- **Folders**: Use gerund form (verb + -ing) with kebab-case (e.g., `adding-dbt-unit-test`, `building-dbt-semantic-layer`)
- **Files**: `SKILL.md` (uppercase), supporting files lowercase
- **Skill names**: Must match folder name exactly - lowercase with hyphens

### Command Examples

Always use code blocks with bash syntax highlighting:

```bash
dbt run --select model_name
```

Include inline comments for complex commands:

```bash
# Run changed models and downstream dependencies
dbt run --select state:modified+ --state ./target
```

### dbt-Specific Guidelines

- Always specify relevant flags (`--select`, `--exclude`, `--full-refresh`, etc.)
- Explain selector syntax when using graph operators (`+`, `@`, etc.)
- Include both simple and complex examples
- Mention version requirements for newer features
- Warn about potentially destructive operations

### Writing Style

- Use clear, concise language familiar to dbt users
- Reference official dbt terminology (models, sources, tests, macros, etc.)
- Write in imperative mood for instructions
- Include "When to Use" and "Prerequisites" sections
- Add "Common Issues" or "Troubleshooting" when relevant

### Metadata

Required frontmatter in `SKILL.md`:

```yaml
---
name: adding-something-useful
description: Use when [specific trigger or use case]
user-invocable: false
metadata:
  author: dbt-labs
---
```

**Important**:

- The `name` field must be lowercase and use only letters, digits, and hyphens
- The `name` must match the directory name exactly
- Use gerund form for names (e.g., `adding-`, `building-`, `configuring-`)
- Start descriptions with "Use when..." to help agents know when to trigger the skill
- Set `user-invocable: false` unless the skill should appear as a slash command
- Only these fields are allowed: `name`, `description`, `user-invocable`, `allowed-tools`, `compatibility`, `license`, `metadata`

## dbt Skill Ideas

Need inspiration? Consider creating skills for:

- **Adapters**: Warehouse-specific patterns for Snowflake, BigQuery, Databricks, Redshift
- **CI/CD**: Slim CI patterns, deployment workflows, PR automation
- **Performance**: Query optimization, profiling slow models, warehouse cost management
- **Packages**: Working with popular dbt packages (dbt-utils, dbt-expectations, etc.)
- **Advanced patterns**: Incremental models, snapshots, custom materializations

## Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [Agent Skills Specification](https://agentskills.io/specification)

## Questions or Issues?

- Open an issue for questions or discussions
- Check existing skills and issues before creating new ones
- Abide by the [dbt Community Code of Conduct](https://docs.getdbt.com/community/resources/code-of-conduct)

## License

By contributing, you agree that your contributions will be licensed under the same license as this repository.
