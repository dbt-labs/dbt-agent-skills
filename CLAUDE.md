# Agent Skills for dbt - Development Guide for AI Assistants

This repository contains [Agent Skills](https://agentskills.io/home) specifically for working with dbt. When creating or modifying skills in this repository, follow these guidelines to ensure compliance with the Agent Skills specification.

## Using the Agent Skills MCP Server

**IMPORTANT**: When creating or editing skills, use the Agent Skills MCP server to validate that your work conforms to the specification. This ensures skills will work correctly with skills-compatible AI agents.

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

## Agent Skills Specification Requirements

### Frontmatter Format

Every `SKILL.md` file MUST have frontmatter with these exact requirements:

```yaml
---
name: skill-name-in-lowercase
description: Brief one-sentence description
---
```

**Critical Rules**:
- `name` MUST be lowercase with hyphens only (letters, digits, hyphens)
- `name` MUST match the directory name exactly
- Only allowed fields: `name`, `description`, `allowed-tools`, `compatibility`, `license`, `metadata`
- NO `version`, `author`, or `tags` fields (these will cause validation errors)

### Directory Structure

Skills should be organized by category:

```
dbt-commands/
├── run-incremental-models/
│   └── SKILL.md
├── test-with-selectors/
│   └── SKILL.md
└── build-models/
    └── SKILL.md
```

### Skill Content

After the frontmatter, include:

1. **Clear title and purpose**: What this skill does and when to use it
2. **Prerequisites**: Required setup (dbt installation, project structure, etc.)
3. **Instructions**: Step-by-step commands and explanations
4. **Examples**: Real-world scenarios with actual dbt commands
5. **Common issues**: Troubleshooting guidance
6. **Related commands**: Links to related skills or dbt commands

## dbt-Specific Guidelines

When creating dbt skills:

- Use actual dbt CLI syntax (e.g., `dbt run --select model_name`)
- Include relevant flags (`--select`, `--exclude`, `--full-refresh`, `--state`, etc.)
- Explain selector syntax when using graph operators (`+`, `@`, etc.)
- Warn about destructive operations (full refresh, etc.)
- Reference official dbt documentation when appropriate
- Include both simple and complex examples
- Consider different dbt versions if features are version-specific

### Example Commands

```bash
# Good: Clear, specific, with context
dbt run --select config.materialized:incremental --full-refresh

# Good: With comments explaining the selector
# Run changed models and their downstream dependencies
dbt run --select state:modified+ --state ./target
```

## Before Submitting

1. ✅ **Validate the skill** using the skills-ref tool
2. ✅ **Test commands** in an actual dbt project
3. ✅ **Check naming**: Skill name matches directory, lowercase with hyphens only
4. ✅ **Verify frontmatter**: Only allowed fields, no extra metadata
5. ✅ **Review examples**: All commands use correct dbt syntax
6. ✅ **Check links**: References to dbt docs are accurate

## Common Validation Errors

❌ **"Unexpected fields in frontmatter"**
- Remove `version`, `author`, `tags` or other non-allowed fields
- Only use: `name`, `description`, `allowed-tools`, `compatibility`, `license`, `metadata`

❌ **"Skill name must be lowercase"**
- Change `Run Incremental Models` to `run-incremental-models`

❌ **"Directory name must match skill name"**
- If skill name is `run-models`, directory must be `run-models/`

❌ **"Contains invalid characters"**
- Use only lowercase letters, digits, and hyphens in skill name
- No spaces, underscores, or special characters

## Resources

- [Agent Skills Specification](https://agentskills.io/specification)
- [dbt CLI Reference](https://docs.getdbt.com/reference/dbt-commands)
- [Contributing Guide](CONTRIBUTING.md)

## Remember

Always use the Agent Skills MCP server or validation tools before committing. This ensures your skills will work correctly with all skills-compatible AI agents and maintains the quality of this repository.
