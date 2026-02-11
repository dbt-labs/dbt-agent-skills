# dbt Skills Repository

This repository contains skills for AI agents working with dbt projects.

## Creating and Modifying Skills

This repo uses the [superpowers](https://github.com/obra/superpowers) skill framework. When creating or modifying skills:

1. **Use the superpowers:writing-skills skill** - It provides TDD-based methodology for skill creation including pressure testing
2. **Follow the Iron Rule** - Test skills with pressure scenarios before deploying

The superpowers marketplace is configured in `.claude/settings.json` and will be auto-installed when you trust this repo.

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
- NO `version`, `author`, or `tags` fields (these will cause validation errors if not put inside `metadata:`

## Common Validation Errors

| Error | Fix |
|-------|-----|
| "Unexpected fields in frontmatter" | Remove `version`, `author`, `tags` or other non-allowed fields |
| "Skill name must be lowercase" | Change `Run Incremental Models` to `run-incremental-models` |
| "Directory name must match skill name" | If skill name is `run-models`, directory must be `run-models/` |
| "Contains invalid characters" | Use only lowercase letters, digits, and hyphens in skill name |

## Before Committing

1. Test with pressure scenarios using superpowers:writing-skills methodology
2. Check naming: Skill name matches directory, lowercase with hyphens only
3. Verify frontmatter: Only allowed fields, no extra metadata
