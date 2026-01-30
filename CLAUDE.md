# dbt Skills Repository

This repository contains skills for AI agents working with dbt projects.

## Creating and Modifying Skills

This repo uses the [superpowers](https://github.com/obra/superpowers) skill framework. When creating or modifying skills:

1. **Use the superpowers:writing-skills skill** - It provides TDD-based methodology for skill creation including pressure testing
2. **Follow the Iron Rule** - Test skills with pressure scenarios before deploying

The superpowers marketplace is configured in `.claude/settings.json` and will be auto-installed when you trust this repo.

## Using the skills-ref Validation Tool

**IMPORTANT**: When creating or editing skills, validate that your work conforms to the Agent Skills specification.

### Validation Workflow

1. **When creating or editing a SKILL.md file**, fetch relevant information using the MCP server:
   - Use `mcp_Agent_Skills_SearchAgentSkills` to look up specification requirements
   - Validate the skill structure and frontmatter against the spec
   - Check that the skill name and directory structure are correct

2. **After making changes**, use the local `skills-ref` validation tool:
   ```bash
   # From the repository root, with venv activated
   uv sync  # First time only
   source .venv/bin/activate
   skills-ref validate path/to/skill
   ```

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

## Skill Requirements

Every `SKILL.md` must have valid frontmatter:

```yaml
---
name: skill-name-in-lowercase
description: Brief one-sentence description starting with "Use when..."
---
```

**Critical Rules**:
- `name` MUST be lowercase with hyphens only (letters, digits, hyphens)
- `name` MUST match the directory name exactly
- Only allowed fields: `name`, `description`, `allowed-tools`, `compatibility`, `license`, `metadata`
- NO `version`, `author`, or `tags` fields (these will cause validation errors)

## Common Validation Errors

| Error | Fix |
|-------|-----|
| "Unexpected fields in frontmatter" | Remove `version`, `author`, `tags` or other non-allowed fields |
| "Skill name must be lowercase" | Change `Run Incremental Models` to `run-incremental-models` |
| "Directory name must match skill name" | If skill name is `run-models`, directory must be `run-models/` |
| "Contains invalid characters" | Use only lowercase letters, digits, and hyphens in skill name |

## Before Committing

1. Validate the skill using `skills-ref validate`
2. Test with pressure scenarios using superpowers:writing-skills methodology
3. Check naming: Skill name matches directory, lowercase with hyphens only
4. Verify frontmatter: Only allowed fields, no extra metadata
5. Regenerate marketplace: `python3 scripts/generate_marketplace.py`
