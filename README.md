# dbt Skills

A curated collection of [Agent Skills](https://agentskills.io/home) for working with dbt. These skills help AI agents understand and execute dbt workflows more effectively.

## What are Agent Skills?

Agent Skills are folders of instructions, scripts, and resources that agents can discover and use to do things more accurately and efficiently. This repository focuses specifically on dbt CLI operations and workflows.

## About dbt CLI Skills

This repository contains skills that enable AI agents to:

- **Execute dbt commands**: Run models, tests, snapshots, and seeds with proper syntax and options
- **Understand dbt workflows**: Navigate common dbt development patterns and best practices
- **Debug dbt issues**: Troubleshoot compilation errors, test failures, and performance problems
- **Manage dbt projects**: Handle dependencies, configuration, and project structure
- **Optimize dbt operations**: Use selectors, incremental models, and efficient testing strategies

## Repository Structure

## Using These Skills

Skills-compatible AI agents can automatically discover and use skills from this repository when working with dbt projects.

### Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/dbt-labs/llm-skills.git
   ```

2. Point your skills-compatible agent to the repository location

3. The agent will automatically load relevant dbt skills based on your tasks

### Compatible Agents

These skills work with AI agents that support the Agent Skills format. Check [agentskills.io](https://agentskills.io/home) for the latest list of compatible tools.

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
