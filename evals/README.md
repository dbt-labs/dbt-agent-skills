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

# Run in parallel (runs all skill-sets concurrently)
uv run skill-eval run <scenario-name> --parallel      # single scenario, parallel skill-sets
uv run skill-eval run --all --parallel                # all scenarios, all skill-sets in parallel
uv run skill-eval run --all --parallel --workers 8    # custom worker count (default: 4)

# Review transcripts in browser (opens HTML files)
uv run skill-eval review              # latest run
uv run skill-eval review <run-id>     # specific run

# Grade outputs from a run (creates grades.yaml for manual review)
uv run skill-eval grade <run-id>

# Auto-grade using Claude (calls Claude CLI to evaluate each output)
uv run skill-eval grade <run-id> --auto

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
│               ├── context/        # Modified files after run
│               └── transcript/     # HTML conversation viewer
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
      - skills/debugging-dbt-errors
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
      - skills/troubleshooting-dbt-job-errors
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
      - skills/fetching-dbt-docs
    # No allowed_tools = allows everything
```

### Skills

Skills can be referenced in three ways:

1. **Local file path** (relative to repo root):
   ```yaml
   skills:
     - skills/debugging-dbt-errors
   ```

2. **Local folder path** (copies entire folder including supporting files):
   ```yaml
   skills:
     - skills/add-unit-test
   ```

3. **HTTP URL** (downloads skill from remote server):
   ```yaml
   skills:
     # GitHub blob URL (automatically converted to raw)
     - https://github.com/org/repo/blob/main/skills/my-skill/SKILL.md
     # Works with branches, tags, and commit SHAs
     - https://github.com/org/repo/blob/v1.2.3/skills/my-skill/SKILL.md
     - https://github.com/org/repo/blob/abc123def/skills/my-skill/SKILL.md
     # Or use raw URL directly
     - https://raw.githubusercontent.com/org/repo/main/skills/my-skill/SKILL.md
   ```

You can mix local and remote skills in the same skill set:

```yaml
skills:
  - skills/debugging-dbt-errors
  - https://github.com/org/repo/blob/main/skills/external-skill/SKILL.md
```

**Note:** The URL must point to a `SKILL.md` file. GitHub blob URLs are automatically converted to raw URLs. Directory URLs are not supported.

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

### transcript/

HTML files for viewing the conversation in a browser. Open `index.html` to view, with paginated content in `page-XXX.html` files. In VS Code, you can use the [Live Preview](https://marketplace.visualstudio.com/items?itemName=ms-vscode.live-server) extension to view these directly in the editor.

## Workflow

1. **Create a scenario** - Define prompt, context files, and expected behavior
2. **Configure skill sets** - Specify skills, MCP servers, and tool permissions
3. **Run evaluation** - `skill-eval run <scenario>` executes Claude with each configuration
4. **Review transcripts** - `skill-eval review` opens HTML transcripts in browser
5. **Grade outputs** - `skill-eval grade <run-id>` (manual) or `--auto` (Claude-graded)
6. **Generate report** - `skill-eval report <run-id>` shows comparison summary

## Auto-Grading

Use `--auto` to have Claude grade the outputs:

```bash
uv run skill-eval grade <run-id> --auto
```

Auto-grading evaluates each output on three dimensions:

1. **Task Completion** - Did it accomplish the main task?
2. **Tool Usage** - Did it use appropriate tools? Were MCP servers/skills leveraged when available?
3. **Solution Quality** - Correctness, completeness, and clarity

The grader receives:
- Original prompt (`prompt.txt`)
- Grading criteria (`scenario.md`)
- Assistant's response (`output.md`)
- Tools used, skills available/invoked, MCP servers (`metadata.yaml`)
- Modified files (`context/`)

Output grades include:
- `success`: true/false
- `score`: 1-5
- `tool_usage`: appropriate/partial/inappropriate
- `notes`: explanation

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
      - skills/debugging-dbt-errors
    allowed_tools: [Read, Glob, Grep, Edit, Bash(dbt:*), Skill]
```

### Testing MCP server value

```yaml
# Does the MCP server provide better results?
sets:
  - name: skill-only
    skills:
      - skills/troubleshooting-dbt-job-errors
    allowed_tools: [Read, Glob, Grep, Skill]

  - name: skill-plus-mcp
    skills:
      - skills/troubleshooting-dbt-job-errors
    mcp_servers:
      dbt:
        command: uvx
        args: [--env-file, .env, dbt-mcp@latest]
    allowed_tools: [Read, Glob, Grep, Skill, mcp__dbt__*]
```

### Testing remote skills

```yaml
# Compare a local skill against a remote version
sets:
  - name: local-skill
    skills:
      - skills/debugging-dbt-errors
    allowed_tools: [Read, Glob, Grep, Edit, Skill]

  - name: remote-skill
    skills:
      # GitHub blob URL - automatically converted to raw
      - https://github.com/org/repo/blob/main/skills/debugging-dbt-errors/SKILL.md
    allowed_tools: [Read, Glob, Grep, Edit, Skill]
```
