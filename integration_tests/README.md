# Integration Tests

This directory contains the integration test suite for the `dbt-agent-skills` repository. These tests ensure that all plugins and skills are correctly formatted, follow the project's metadata requirements, and are compatible with the Claude CLI.

## Overview

The integration test suite performs automated validation across multiple layers of the repository:

1. **Manifest Validation**: Checking `.claude-plugin/plugin.json` for schema correctness.
2. **Skill Validation**: Enforcing strict frontmatter rules for `SKILL.md` files as defined in `CLAUDE.md`.
3. **Plugin Loading**: Verifying that the Claude CLI can successfully discover and load the plugins.
4. **Component Discovery**: Ensuring the directory structure and required components (skills, agents, etc.) are intact.

## Test Suite Components

| Script | Description |
|--------|-------------|
| `run.sh` | The main orchestrator that discovers plugins in `skills/` and runs all validation scripts against them. |
| `validate-manifest.sh` | Validates that `plugin.json` is valid JSON, contains required fields (`name`, `version`, `description`), and follows kebab-case naming. |
| `validate-skill-md.sh` | Enforces `CLAUDE.md` compliance for `SKILL.md` frontmatter (lowercase names, allowed fields, no forbidden metadata at top-level). |
| `test-plugin-loading.sh` | Uses `claude --plugin-dir <path> --help` to verify the plugin is loadable by the CLI. |
| `test-component-discovery.sh` | Checks for the existence of required directories and files (e.g., `SKILL.md` in skill folders). |

## Running Tests

### Local Execution

You can run the full suite locally using `run.sh`:

```bash
./integration_tests/run.sh [OPTIONS]
```

**Options:**

- `--skip-loading`: Skip tests that require the `claude` CLI to be installed.
- `--manifest-only`: Run only the manifest validation.
- `--verbose`, `-v`: Enable detailed output for each test step.
- `--fail-fast`: Stop the execution immediately after the first failure.

### Containerized Testing (Recommended)

To ensure environment parity with CI, use the provided Docker configuration:

```bash
docker build -f integration_tests/Dockerfile -t dbt-agent-skills-it .
```

This will build an image and run the full test suite inside a container pre-configured with the Claude CLI.

## CI/CD Integration

These tests are automatically executed on every push and pull request via the [Integration Tests workflow](../.github/workflows/integration_tests.yml).

## Troubleshooting

- **"claude not found"**: Ensure the Claude CLI is installed (`npm install -g @anthropic-ai/claude-code`) or use the `--skip-loading` flag.
- **Manifest Errors**: Check that `.claude-plugin/plugin.json` is valid JSON and follows the required naming convention (lowercase, hyphens only).
- **Skill Validation Errors**: Refer to the "Skill Requirements" section in [CLAUDE.md](../CLAUDE.md) for correct `SKILL.md` frontmatter format.
