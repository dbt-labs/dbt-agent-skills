# dbt Agent Skills

A curated collection of [Agent Skills](https://agentskills.io/home) for working with dbt. These skills help AI agents understand and execute dbt workflows more effectively.

## What are Agent Skills?

Agent Skills are folders of instructions, scripts, and resources that agents can discover and use to do things more accurately and efficiently.

## How They Work

These skills are **not** slash commands or user-invoked actions. Once installed, the agent automatically loads the relevant skill when your prompt matches its use case. Just describe what you need in natural language and the agent handles the rest. See [skill invocation control](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill) for more details.

## What's Included

- **Analytics engineering**: Build and modify dbt models, write tests, explore data sources
- **Semantic layer**: Create metrics, dimensions, and semantic models with MetricFlow
- **Platform operations**: Troubleshoot job failures, configure the dbt MCP server
- **Migration**: Move projects from dbt Core to the Fusion engine

## Installation

### Claude Code

Add the dbt skills marketplace and install the plugins:

```bash
# Add the marketplace
/plugin marketplace add dbt-labs/dbt-agent-skills

# Install the dbt skills (analytics engineering, semantic layer, testing, etc.)
/plugin install dbt@dbt-agent-marketplace

# Install the migration skills (typically a one-off — not needed for every session)
/plugin install dbt-migration@dbt-agent-marketplace
```

### Other AI Clients

#### Vercel Skills CLI

Use the [Vercel Skills CLI](https://github.com/vercel-labs/skills) to install skills from this repository. Supports 30+ AI agents including Cursor, Cline, GitHub Copilot, and others.

```bash
# Preview available skills
npx skills add dbt-labs/dbt-agent-skills --list

# Install all skills
npx skills add dbt-labs/dbt-agent-skills

# Install only the dbt skills (analytics engineering, semantic layer, etc.)
npx skills add dbt-labs/dbt-agent-skills/skills/dbt

# Install only the migration skills
npx skills add dbt-labs/dbt-agent-skills/skills/dbt-migration

# Install a specific skill
npx skills add dbt-labs/dbt-agent-skills --skill using-dbt-for-analytics-engineering

# Install globally (available in all projects, stored in ~/.<agent>/skills/)
npx skills add dbt-labs/dbt-agent-skills --global

# Check for updates
npx skills check

# Update installed skills
npx skills update
```

#### Tessl

Install skills using [Tessl](https://tessl.io/), a package manager for agent skills:

```bash
# Install all skills
tessl install dbt-labs/dbt-agent-skills

# Install a specific skill
tessl install dbt-labs/dbt-agent-skills --skill using-dbt-for-analytics-engineering

# Install from GitHub directly
tessl install github:dbt-labs/dbt-agent-skills
```

Browse the tile on the [Tessl registry](https://tessl.io/registry/dbt-labs/dbt-agent-skills).

### Compatible Agents

These skills work with AI agents that support the [Agent Skills](https://agentskills.io/home) format.

## Available Skills

### dbt (analytics engineering)

| Skill | Description |
|-------|-------------|
| `using-dbt-for-analytics-engineering` | Build and modify dbt models, debug errors, explore data sources, write tests |
| `adding-dbt-unit-test` | Add unit tests for dbt models, practice test-driven development |
| `building-dbt-semantic-layer` | Create semantic models, metrics, and dimensions with MetricFlow |
| `answering-natural-language-questions-with-dbt` | Answer business questions by querying the semantic layer |
| `troubleshooting-dbt-job-errors` | Diagnose and resolve dbt platform job failures |
| `configuring-dbt-mcp-server` | Set up the dbt MCP server for Claude, Cursor, or VS Code |
| `fetching-dbt-docs` | Look up dbt documentation efficiently |
| `running-dbt-commands` | Run dbt CLI commands with correct flags, selectors, and parameter formats |

### dbt-migration (one-off use)

These skills are typically used once during a migration project rather than in every agent session.

| Skill | Description |
|-------|-------------|
| `migrating-dbt-core-to-fusion` | Migrate dbt projects from dbt Core to the Fusion engine |
| `migrating-dbt-project-across-platforms` | Migrate dbt projects across data platforms |

## Prerequisites

Most skills assume:

- dbt is installed and configured
- A dbt project with `dbt_project.yml` exists
- Basic familiarity with dbt concepts (models, tests, sources)

Some skills like `fetching-dbt-docs` and `configuring-dbt-mcp-server` can be used without an existing project.

## Contributing

We welcome contributions! Whether you want to add a new dbt skill, improve existing ones, or fix issues, please see our [Contributing Guide](CONTRIBUTING.md).

## Format Specification

All skills in this repository follow the [Agent Skills specification](https://agentskills.io/specification) to ensure compatibility across different agent products.

## Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt CLI Reference](https://docs.getdbt.com/reference/dbt-commands)
- [Agent Skills Documentation](https://agentskills.io/home)
- [Agent Skills Specification](https://agentskills.io/specification)

## Community

- **Issues**: Report problems or suggest new skills
- **Discussions**: Share use cases and patterns
- **Pull Requests**: Contribute new skills or improvements
- **Star** this repository if you find it useful!

## License

See [LICENSE](LICENSE) for details.

## Skill Evaluation

See [evals/README.md](evals/README.md) for the A/B testing tool to compare skill variations.


## Kiro Implementation

This repository supports both the vendor-agnostic [Agent Skills specification](https://agentskills.io/specification) and the Kiro Power format, enabling use across multiple AI development platforms.

### Dual Format Approach

The repository maintains two parallel distribution formats:

1. **Agent Skills format** (primary) - Individual `SKILL.md` files in `skills/` directories
   - Works with Claude Code, Cursor, Cline, GitHub Copilot, and 30+ other AI agents
   - Installed via Vercel Skills CLI (`npx skills add`) or Tessl
   - Follows the [Agent Skills specification](https://agentskills.io/specification)

2. **Kiro Power format** - `POWER.md` file at repository root
   - Optimized for Kiro's keyword-based activation system
   - Includes metadata (logo, description, keywords) for Kiro's Power browser
   - References the same underlying skill content

### Why This Approach?

This dual format strategy ensures:

- **Vendor neutrality** - The core skills remain platform-agnostic and work everywhere
- **Kiro optimization** - Power-specific metadata improves discoverability and user experience in Kiro
- **Single source of truth** - All platforms reference the same skill content; no duplication
- **Easy maintenance** - Updates to skills automatically benefit all platforms

### For Kiro Users

Install this power through the Kiro Powers panel or by adding it from GitHub. The power will automatically activate when you work with dbt projects or mention dbt-related keywords.

### For Other Platform Users

Follow the installation instructions in the main sections above using the Vercel Skills CLI, Tessl, or your platform's native skill installation method.

### Technical Details

- **Agent Skills**: Located in `skills/dbt/skills/` with individual `SKILL.md` files
- **Kiro Power**: `POWER.md` at root aggregates and references the individual skills
- **Logo**: `dbt_logo.svg` provides branding in Kiro's Power browser
- **Compatibility**: Both formats coexist without conflicts; changes to skills benefit both distributions
