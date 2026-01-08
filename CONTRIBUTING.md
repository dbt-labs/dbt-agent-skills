# Contributing to dbt CLI Skills

Thank you for your interest in contributing dbt CLI skills! This guide will help you create, improve, and submit skills that help AI agents work effectively with dbt.

## Table of Contents

1. [About this Repository](#about-this-repository)
2. [How to Contribute](#how-to-contribute)
3. [Setup](#setup)
4. [Using skills-ref](#using-skills-ref)
5. [Creating a New dbt Skill](#creating-a-new-dbt-skill)
6. [Skill Quality Guidelines](#skill-quality-guidelines)
7. [Testing Your Skill](#testing-your-skill)
8. [Submitting a Pull Request](#submitting-a-pull-request)
9. [Style Guide](#style-guide)
10. [Troubleshooting](#troubleshooting)

## About this Repository

This repository contains Agent Skills specifically for dbt CLI operations. Skills follow the [Agent Skills specification](https://agentskills.io/specification) and help AI agents execute dbt commands, understand workflows, and troubleshoot issues.

## How to Contribute

There are several ways to contribute:

- **Add a new dbt skill**: Create skills for commands, workflows, or patterns you use frequently
- **Improve existing skills**: Enhance command examples, add selector patterns, or clarify instructions
- **Fix issues**: Help resolve incorrect commands or unclear documentation
- **Share dbt patterns**: Document your team's best practices or optimization techniques

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) - Fast Python package installer
- Python 3.11+ (required by skills-ref)
- Git

### Installing skills-ref

The `skills-ref` library provides tools to validate skills and generate prompt XML. It's installed directly from GitHub using uv.

1. From the repository root, install development dependencies:

   ```bash
   uv sync
   ```

2. Activate the virtual environment:

   ```bash
   source .venv/bin/activate
   ```

3. Verify installation:

   ```bash
   skills-ref --help
   ```

The `skills-ref` package is installed from the [agentskills repository](https://github.com/agentskills/agentskills/tree/main/skills-ref) without checking all the code into this repository.

## Using skills-ref

### Validate a Skill

Before submitting a skill, validate it follows the specification:

```bash
# With venv activated from the repository root
skills-ref validate path/to/your-skill

# Example:
skills-ref validate dbt-commands/run-models
```

The validator checks:

- Required SKILL.md file exists
- Valid YAML frontmatter
- Required metadata fields (name, description)
- Proper file structure

### Quick Reference

```bash
# Setup (one-time)
uv sync
source .venv/bin/activate

# Validate skill
skills-ref validate path/to/skill

# Read properties
skills-ref read-properties path/to/skill

# Generate prompt
skills-ref to-prompt path/to/skill

# Deactivate venv when done
deactivate
```

## Creating a New dbt Skill

### 1. Create the Skill Folder

Create a new folder with a descriptive name using kebab-case:

```bash
mkdir -p dbt-commands/run-incremental-models
```

### 2. Create SKILL.md

Every skill must have a `SKILL.md` file following the Agent Skills specification:

```markdown
---
name: run-incremental-models
description: Execute dbt incremental models with proper refresh strategies
---

# Run Incremental Models

This skill helps agents execute incremental dbt models effectively, understanding when to use full refresh and how to handle incremental logic.

## When to Use

Use this skill when:
- Running specific incremental models
- Forcing a full refresh of incremental models
- Testing incremental logic after changes
- Rebuilding corrupted incremental tables

## Prerequisites

- dbt Core or dbt Cloud CLI installed
- Active dbt project with `dbt_project.yml`
- Configured database connection in `profiles.yml`
- At least one incremental model in the project

## Commands

### Run All Incremental Models
\`\`\`bash
dbt run --select config.materialized:incremental
\`\`\`

### Full Refresh Incremental Models
\`\`\`bash
dbt run --select config.materialized:incremental --full-refresh
\`\`\`

### Run Specific Incremental Model
\`\`\`bash
dbt run --select model_name --full-refresh
\`\`\`

## Examples

### Scenario 1: Daily Incremental Run
\`\`\`bash
# Run only incremental models for daily refresh
dbt run --select config.materialized:incremental
\`\`\`

### Scenario 2: Fix Corrupted Incremental Table
\`\`\`bash
# Full refresh a specific model to rebuild from scratch
dbt run --select my_incremental_model --full-refresh
\`\`\`

### Scenario 3: Test Incremental Logic
\`\`\`bash
# Run with full refresh on a subset
dbt run --select my_incremental_model+ --full-refresh
\`\`\`

## Common Issues

- **Incremental logic not working**: Use `--full-refresh` to rebuild
- **Performance issues**: Check incremental predicates and unique keys
- **Missing records**: Verify the incremental strategy matches your use case

## Related Commands

- `dbt build --select config.materialized:incremental` - Build with tests
- `dbt run --select state:modified+ --state ./target` - Run changed incrementals
- `dbt compile --select model_name` - Check compiled SQL

## Notes

- Full refresh can be expensive on large tables
- Always test incremental logic in development first
- Consider using `--full-refresh` when data quality issues are detected
```

### 3. Add Supporting Resources (Optional)

Include examples or helper content if needed:

```
run-incremental-models/
├── SKILL.md
└── examples/
    ├── incremental_model_example.sql
    └── selector_patterns.txt
```

### 4. Validate the Skill

```bash
source .venv/bin/activate
skills-ref validate dbt-commands/your-skill-name
```

## Style Guide

### Naming Conventions

- **Folders**: Use kebab-case with dbt context (e.g., `dbt-run-models`, `dbt-test-selection`)
- **Files**: `SKILL.md` (uppercase), supporting files lowercase
- **Skill names**: Must match folder name exactly - lowercase with hyphens (e.g., `run-models-with-selectors`)

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
name: skill-name-in-lowercase-with-hyphens
description: One-sentence summary of functionality
---
```

**Important**:

- The `name` field must be lowercase and use only letters, digits, and hyphens
- The `name` must match the directory name exactly
- Only these fields are allowed: `name`, `description`, `allowed-tools`, `compatibility`, `license`, `metadata`

## Troubleshooting

### "Command not found: skills-ref"

Make sure you've installed dependencies and activated the virtual environment:

```bash
uv sync
source .venv/bin/activate
```

## dbt Skill Ideas

Need inspiration? Consider creating skills for:

- **Commands**: run, test, build, seed, snapshot, compile, parse, docs, source
- **Selectors**: tag:, config:, source:, exposure:, path:, package:
- **Graph operators**: +model, model+, +model+, @model
- **State comparison**: state:modified, state:new
- **Testing strategies**: schema tests, data tests, unit tests
- **Debugging**: Compilation errors, adapter issues, macro problems
- **Performance**: Optimization, profiling, troubleshooting slow models
- **CI/CD**: Slim CI patterns, deployment workflows
- **dbt Cloud**: CLI-specific commands and features

## Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [Agent Skills Specification](https://agentskills.io/specification)
- [skills-ref GitHub](https://github.com/agentskills/agentskills/tree/main/skills-ref)

## Questions or Issues?

- Open an issue for questions or discussions
- Check existing skills and issues before creating new ones
- Abide by the [dbt Community Code of Conduct](https://docs.getdbt.com/community/resources/code-of-conduct)

## License

By contributing, you agree that your contributions will be licensed under the same license as this repository.
