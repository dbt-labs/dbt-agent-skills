# Skill Evaluation Tool

A/B testing tool for comparing LLM skill variations against recorded scenarios.

## Installation

### Local development (from repo)

```bash
cd evals
uv sync
```

### Install from GitHub (use anywhere)

```bash
# One-time install
uv tool install 'skill-eval @ git+https://github.com/dbt-labs/dbt-agent-skills.git#subdirectory=evals'

# Then use from any directory
skill-eval run --all
skill-eval new my-scenario
```

### Quick run without installing

```bash
uvx --from 'skill-eval @ git+https://github.com/dbt-labs/dbt-agent-skills.git#subdirectory=evals' skill-eval --help
```

## Usage

```bash
# Create a new scenario
skill-eval new my-scenario

# Create with context files
skill-eval new my-scenario --context models/ --context seeds/data.csv

# Create in a specific directory
skill-eval new my-scenario --base-dir /path/to/evals

# Run a scenario
uv run skill-eval run <scenario-name>

# Run all scenarios
uv run skill-eval run --all

# Run in parallel (runs all skill-sets concurrently)
uv run skill-eval run <scenario-name> --parallel      # single scenario, parallel skill-sets
uv run skill-eval run --all --parallel                # all scenarios, all skill-sets in parallel
uv run skill-eval run --all --parallel --workers 8    # custom worker count (default: 4)

# Verbose mode (shows tool calls and skill invocations)
uv run skill-eval run <scenario-name> --verbose       # or -v

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
│       └── .env                # Environment variables (setup commands + MCP servers)
├── runs/                   # Output from runs (timestamped, gitignored)
│   └── 2026-01-15-153633/
│       └── example-yaml-error/
│           └── debug-baseline/
│               ├── output.md       # Full conversation text
│               ├── metadata.yaml   # Run metrics and tool usage
│               ├── raw.jsonl       # Complete NDJSON stream
│               ├── changes/        # Files modified during the run
│               └── transcript/     # HTML conversation viewer
├── reports/                # Generated comparison reports
└── src/skill_eval/         # CLI source code
```

## Scenario Configuration

### skill-sets.yaml

Define skill combinations, MCP servers, tool permissions, and prompt variations:

```yaml
sets:
  # Baseline with no skills
  - name: no-skills
    model: sonnet
    skills: []

  # With specific allowed tools (safer than allowing all)
  - name: restricted-tools
    model: sonnet
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
    model: sonnet
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
    model: sonnet
    skills:
      - skills/fetching-dbt-docs
    # No allowed_tools = allows everything

  # With extra instructions appended to the prompt
  - name: with-skill-hint
    model: sonnet
    skills:
      - skills/debugging-dbt-errors
    extra_prompt: Check if any skill can help with this task.
    allowed_tools:
      - Read
      - Glob
      - Skill

  # Comparing a stronger model on the same setup
  - name: with-mcp-opus
    model: opus
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
```

### Model

`model` is **required** on every set — `skill-eval` raises an error if it's missing, rather than silently
falling back to whatever the `claude` CLI's built-in default happens to be. This keeps runs reproducible
and cost/latency comparable across skill sets and across time.

Pass an alias (`sonnet`, `opus`, `fable`) or a full model ID, exactly as accepted by `claude --model`:

```yaml
sets:
  - name: baseline
    model: sonnet
    skills: []
```

### MCP Isolation (`strict_mcp_config`)

By default, every run adds `--strict-mcp-config` to the `claude` invocation, so only the MCP servers
declared in that set's `mcp_servers` are available — MCP servers configured in Claude Desktop, your
user-level `~/.claude.json`, or a project's `.mcp.json` are ignored. Without this, runs can silently pick
up unrelated MCP servers from your local machine (extra tools, auth prompts, noisy `mcp_servers` metadata)
that have nothing to do with the scenario and won't be present on another machine or in CI.

Set `strict_mcp_config: false` on a set to opt out and allow those external MCP servers to load:

```yaml
sets:
  - name: with-desktop-mcp-servers
    model: sonnet
    strict_mcp_config: false
    skills: []
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

### Environment Variables (.env)

Each scenario gets a `.env` file (created by `skill-eval new`, gitignored). Variables are loaded automatically for setup commands and passed to Claude:

```bash
# scenarios/dbt-job-failure/.env
DO_NOT_TRACK=1
DBT_HOST=https://cloud.getdbt.com
DBT_TOKEN=your_token_here
```

### MCP Servers

MCP servers use the standard `mcpServers` format:

```yaml
mcp_servers:
  dbt:
    command: uvx
    args:
      - --env-file
      - .env
      - dbt-mcp@latest
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

### Extra Prompt

Append additional instructions to the base prompt for specific skill sets:

```yaml
sets:
  # Baseline - just the prompt.txt content
  - name: no-hint
    model: sonnet
    skills:
      - skills/debugging-dbt-errors
    allowed_tools: [Read, Glob, Skill]

  # With hint - prompt.txt + extra_prompt
  - name: with-hint
    model: sonnet
    skills:
      - skills/debugging-dbt-errors
    extra_prompt: Check if any skill can help with this task.
    allowed_tools: [Read, Glob, Skill]
```

Use this to test whether additional instructions affect skill invocation or behavior. For example:
- "Check if any skill can help with this task."
- "Use the MCP server to investigate this issue."
- "Think step by step before making changes."

Multiline prompts are supported using YAML block scalars:

```yaml
extra_prompt: |
  Before starting:
  1. Check if any skill can help
  2. Use the MCP server if available
```

### Setup Commands

Run commands before Claude starts (e.g., installing skills via CLI):

```yaml
sets:
  - name: with-remote-skill
    model: sonnet
    setup:
      - npx skills add https://github.com/dbt-labs/dbt-agent-skills -a claude-code -y
    skills: []
    allowed_tools: [Read, Glob, Grep, Skill]
```

Setup commands run in the isolated temp environment with `.env` variables loaded. If any command fails, the run stops immediately with an error.

Use cases:
- Installing skills via `npx skills add <url> -a claude-code -y`
- Running project setup scripts
- Seeding test data

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
skills_available_other:
  - some-globally-installed-plugin-skill
tools_used:
  - Read
  - Edit
  - Glob
  - Skill
tool_call_count: 12
subagents_used: false
subagent_count: 0
subagent_tools_used: []
subagent_tool_call_count: 0
mcp_servers: []
model: claude-opus-4-5-20251101
duration_ms: 31476
num_turns: 10
total_cost_usd: 0.1425935
input_tokens: 125241
output_tokens: 1177
```

`skills_available` is scoped to only the skills this set's `skills:` list actually added — it's what
grading and reporting use for skill-usage percentages. `claude` may also report other skills that happen
to be installed globally (plugins, marketplace skills) that have nothing to do with the scenario; those
are recorded separately as `skills_available_other` for visibility but excluded from grading.

#### Subagents

When Claude uses the `Task` tool, the spawned subagent's own turns stream inline as a "sidechain"
alongside the main conversation. These fields keep that separate from the main thread:

- `output.md` / `output_text` only ever contains the main thread's own text — a subagent's narration
  never leaks into what gets graded as "the answer".
- `tools_used` / `tool_call_count` count only main-thread tool calls. `subagent_tools_used` /
  `subagent_tool_call_count` cover everything called from inside subagents.
- `skills_invoked` is **not** split — a Skill invoked from inside a subagent still counts as the skill
  having been used for this task.
- `subagents_used` / `subagent_count` flag whether (and how many times) a set delegated to a subagent
  at all, since that changes how to read the other numbers below.

`duration_ms` and `total_cost_usd`/token counts come straight from `claude`'s own `result` message and
are **not** split — `duration_ms` is wall-clock time for the whole process, so it inherently includes
however long any subagents took. Whether `total_cost_usd`/token counts include subagent API calls wasn't
verified here (the raw per-message `usage` fields don't reconcile cleanly enough to derive it
independently — see `subagent_tool_call_count` as the closest available proxy for "how much subagent
work happened"). `num_turns` empirically only counts main-thread turns, not subagent turns, but this is
observed behavior, not documented by `claude` itself.

### changes/

Files that were modified or created during the run. Only includes files that differ from the original context (excluding `.claude/`). Useful for verifying what changes Claude made.

### raw.jsonl

Complete NDJSON (newline-delimited JSON) stream from Claude for debugging.

### transcript/

HTML files for viewing the conversation in a browser. Open `index.html` to view, with paginated content in `page-XXX.html` files. In VS Code, you can use the [Live Preview](https://marketplace.visualstudio.com/items?itemName=ms-vscode.live-server) extension to view these directly in the editor.

## Timeouts and Stall Detection

Each run has built-in safeguards:

- **Total timeout**: 10 minutes maximum per skill-set run
- **Stall detection**: Kills the run if no output for 60 seconds (e.g., waiting for permission approval)

Stall detection helps catch runs that get stuck waiting for tool approval when using `allowed_tools` restrictions.

## Workflow

1. **Create a scenario** - `skill-eval new <name>` scaffolds the directory structure
2. **Configure skill sets** - Edit `skill-sets.yaml` to specify skills, MCP servers, and tool permissions
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
- Modified files (`changes/`)

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
    model: sonnet
    skills: []
    allowed_tools: [Read, Glob, Grep, Edit, Bash(dbt:*)]

  - name: with-skill
    model: sonnet
    skills:
      - skills/debugging-dbt-errors
    allowed_tools: [Read, Glob, Grep, Edit, Bash(dbt:*), Skill]
```

### Testing MCP server value

```yaml
# Does the MCP server provide better results?
sets:
  - name: skill-only
    model: sonnet
    skills:
      - skills/troubleshooting-dbt-job-errors
    allowed_tools: [Read, Glob, Grep, Skill]

  - name: skill-plus-mcp
    model: sonnet
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
    model: sonnet
    skills:
      - skills/debugging-dbt-errors
    allowed_tools: [Read, Glob, Grep, Edit, Skill]

  - name: remote-skill
    model: sonnet
    skills:
      # GitHub blob URL - automatically converted to raw
      - https://github.com/org/repo/blob/main/skills/debugging-dbt-errors/SKILL.md
    allowed_tools: [Read, Glob, Grep, Edit, Skill]
```

## Troubleshooting

### "Please log in" errors

If run logs mention needing to log in, authenticate Claude Code first:

```bash
claude
/login
```

Then exit and re-run the evaluation.
