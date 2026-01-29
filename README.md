# dbt Agent Skills

A curated collection of [Agent Skills](https://agentskills.io/home) for working with dbt. These skills help AI agents understand and execute dbt workflows more effectively.

## What are Agent Skills?

Agent Skills are folders of instructions, scripts, and resources that agents can discover and use to do things more accurately and efficiently.

## What's Included

- **Analytics engineering**: Build and modify dbt models, write tests, explore data sources
- **Semantic layer**: Create metrics, dimensions, and semantic models with MetricFlow
- **Platform operations**: Troubleshoot job failures, configure the dbt MCP server
- **Migration**: Move projects from dbt Core to the Fusion engine

## Installation

### Claude Code (recommended)

Add the dbt skills marketplace:

```bash
/plugin marketplace add dbt-labs/dbt-agent-skills
```

Skills are fetched from this repository and **automatically stay up to date** as we publish improvements.

### Other AI Clients

Use the [Vercel Skills CLI](https://github.com/vercel-labs/skills) to install skills from this repository.

> **Note:** This method copies skills into your project. To get updates, you'll need to re-run the install command.

```bash
# Preview available skills
npx skills add dbt-labs/dbt-agent-skills --list

# Install all skills
npx skills add dbt-labs/dbt-agent-skills

# Install a specific skill
npx skills add dbt-labs/dbt-agent-skills --skill using-dbt-for-analytics-engineering

# Install globally (across all projects)
npx skills add dbt-labs/dbt-agent-skills --global
```

The Vercel Skills CLI supports 30+ AI agents including Cursor, Cline, GitHub Copilot, and others.

### Compatible Agents

These skills work with AI agents that support the [Agent Skills](https://agentskills.io/home) format.

## Available Skills

## Prerequisites

These skills assume:

- dbt is installed and configured
- A dbt project with `dbt_project.yml` exists
- Database connections are properly set up in `profiles.yml`
- Basic familiarity with dbt concepts (models, tests, sources)

## Contributing

We welcome contributions! Whether you want to add a new dbt skill, improve existing ones, or fix issues, please see our [Contributing Guide](CONTRIBUTING.md).

### Development Tools

This repository uses the [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) library (installed from GitHub) for validating and testing skills. Requires Python 3.11+. See the [Contributing Guide](CONTRIBUTING.md) for setup and usage instructions.

Common skill additions needed:

## Format Specification

All skills in this repository follow the [Agent Skills specification](https://agentskills.io/specification) to ensure compatibility across different agent products.

## Examples

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
