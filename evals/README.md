# Skill Evaluation Tool

A/B testing tool for comparing LLM skill variations against recorded scenarios.

## Setup

```bash
cd evals
uv sync
```

## Usage

```bash
# Run a scenario
uv run skill-eval run <scenario-name>

# Run all scenarios
uv run skill-eval run --all

# Grade outputs from a run
uv run skill-eval grade <run-id>

# Generate comparison report
uv run skill-eval report <run-id>
```

## Directory Structure

```
evals/
├── scenarios/              # Test scenarios
│   └── example-yaml-error/
│       ├── scenario.md         # Description and grading criteria
│       ├── prompt.txt          # User message to send
│       ├── skill-sets.yaml     # Skills, MCP servers, allowed tools
│       ├── context/            # Files Claude needs (copied to temp env)
│       └── .env                # Environment variables for MCP servers
├── runs/                   # Output from runs (timestamped, gitignored)
│   └── 2026-01-15-153633/
│       └── example-yaml-error/
│           └── debug-baseline/
│               ├── output.md       # Full conversation text
│               ├── metadata.yaml   # Run metrics and tool usage
│               ├── raw.jsonl       # Complete NDJSON stream
│               └── context/        # Modified files after run
├── reports/                # Generated comparison reports
└── src/skill_eval/         # CLI source code
```

## Scenario Configuration

### skill-sets.yaml

Define skill combinations, MCP servers, and tool permissions:

```yaml
sets:
  # Baseline with no skills
  - name: no-skills
    skills: []

  # With specific allowed tools (safer than allowing all)
  - name: restricted-tools
    skills:
      - dbt-commands/debugging-dbt-errors/SKILL.md
    allowed_tools:
      - Read
      - Glob
      - Grep
      - Edit
      - Bash(dbt:*)
      - Skill

  # With MCP server
  - name: with-mcp
    skills:
      - dbt-operations/troubleshooting-dbt-job-errors/SKILL.md
    mcp_servers:
      dbt:
        command: uvx
        args:
          - --env-file
          - .env
          - dbt-mcp@latest
    allowed_tools:
      - Read
      - Glob
      - mcp__dbt__*
      - Skill

  # Allow all tools (uses --dangerously-skip-permissions)
  - name: all-tools
    skills:
      - dbt-docs/fetching-dbt-docs/SKILL.md
    # No allowed_tools = allows everything
```

### Skills

Skills are referenced by path relative to the repo root:

```yaml
skills:
  - dbt-commands/debugging-dbt-errors/SKILL.md
  - dbt-docs/fetching-dbt-docs/SKILL.md
```

### MCP Servers

MCP servers use the standard `mcpServers` format. Environment variables are loaded from `.env` in the scenario directory:

```yaml
mcp_servers:
  dbt:
    command: uvx
    args:
      - --env-file
      - .env
      - dbt-mcp@latest
```

Create a `.env` file in your scenario directory (gitignored):

```bash
# scenarios/dbt-job-failure/.env
DBT_HOST=https://cloud.getdbt.com
DBT_TOKEN=your_token_here
```

### Allowed Tools

Restrict which tools Claude can use (instead of `--dangerously-skip-permissions`):

```yaml
allowed_tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Bash(dbt:*)      # Only dbt commands in bash
  - Skill            # Allow skill invocation
  - mcp__dbt__*      # All tools from dbt MCP server
```

If `allowed_tools` is omitted, all tools are allowed.

## Run Output

Each run produces:

### output.md

Full conversation text from all assistant messages (not just the final result).

### metadata.yaml

```yaml
success: true
skills_invoked:
  - debugging-dbt-errors
skills_available:
  - debugging-dbt-errors
tools_used:
  - Read
  - Edit
  - Glob
  - Skill
mcp_servers: []
model: claude-opus-4-5-20251101
duration_ms: 31476
num_turns: 10
total_cost_usd: 0.1425935
input_tokens: 125241
output_tokens: 1177
```

### context/

The modified working directory after the run (excluding `.claude/`). Useful for verifying what changes Claude made to files.

### raw.jsonl

Complete NDJSON (newline-delimited JSON) stream from Claude for debugging.

## Workflow

1. **Create a scenario** - Define prompt, context files, and expected behavior
2. **Configure skill sets** - Specify skills, MCP servers, and tool permissions
3. **Run evaluation** - `skill-eval run <scenario>` executes Claude with each configuration
4. **Compare outputs** - Review output.md, metadata.yaml, and modified context
5. **Grade outputs** - `skill-eval grade <run-id>` creates grades.yaml for human review
6. **Generate report** - `skill-eval report <run-id>` shows comparison summary

## Examples

### Testing skill effectiveness

```yaml
# Does the skill help Claude solve the problem better?
sets:
  - name: without-skill
    skills: []
    allowed_tools: [Read, Glob, Grep, Edit, Bash(dbt:*)]

  - name: with-skill
    skills:
      - dbt-commands/debugging-dbt-errors/SKILL.md
    allowed_tools: [Read, Glob, Grep, Edit, Bash(dbt:*), Skill]
```

### Testing MCP server value

```yaml
# Does the MCP server provide better results?
sets:
  - name: skill-only
    skills:
      - dbt-operations/troubleshooting-dbt-job-errors/SKILL.md
    allowed_tools: [Read, Glob, Grep, Skill]

  - name: skill-plus-mcp
    skills:
      - dbt-operations/troubleshooting-dbt-job-errors/SKILL.md
    mcp_servers:
      dbt:
        command: uvx
        args: [--env-file, .env, dbt-mcp@latest]
    allowed_tools: [Read, Glob, Grep, Skill, mcp__dbt__*]
```
