---
name: dbt
displayName: dbt Analytics Engineering
description: Agent Skills for analytics engineering best practice with dbt — build, tests, and deploy data pipelines; querying the semantic layer, troubleshooting jobs, migrate projects and more.
version: 1.1.1
author: dbt Labs
homepage: https://docs.getdbt.com/
repository: https://github.com/dbt-labs/dbt-agent-skills
license: Apache-2.0
keywords:
  - dbt
  - analytics-engineering
  - data-modeling
  - semantic-layer
  - testing
  - sql
  - data-transformation
  - etl
  - analytics
  - data-pipelines
---

# dbt Analytics Engineering Power

This power provides comprehensive skills for working with dbt (data build tool), enabling AI agents to assist with analytics engineering workflows, data modeling, testing, and semantic layer development.

## What This Power Provides

When you mention dbt-related keywords or work on dbt projects, Kiro automatically activates the relevant skills to help you:

- **Build and modify dbt models** - Write SQL transformations, use ref() and source() functions, create modular data pipelines
- **Write and run tests** - Create unit tests, schema tests, and validate data quality
- **Develop the semantic layer** - Define metrics, dimensions, entities, and semantic models with MetricFlow
- **Query business data** - Answer natural language questions using the dbt Semantic Layer
- **Troubleshoot issues** - Diagnose dbt Cloud/platform job failures and resolve errors
- **Configure tooling** - Set up the dbt MCP server for AI-assisted development
- **Access documentation** - Efficiently fetch dbt docs for features and best practices
- **Execute commands** - Run dbt CLI commands with correct syntax and parameters
- **Migrate dbt projects** - Migrate dbt projects to dbt Fusion

## Available Skills

This power includes the following specialized skills that activate automatically based on your work context:

### Core Analytics Engineering

**using-dbt-for-analytics-engineering**
- Build and modify dbt models, debug errors, explore data sources
- Write SQL transformations using ref() and source()
- Create tests and validate results with dbt show
- Apply software engineering discipline to data transformation work

### Testing & Quality

**adding-dbt-unit-test**
- Create unit test YAML definitions with mocked inputs
- Validate expected outputs before production materialization
- Practice test-driven development (TDD) in dbt
- Handle special cases: incremental models, ephemeral dependencies, versioned models
- Warehouse-specific guidance for BigQuery, Postgres, Redshift, Snowflake, Spark

### Semantic Layer Development and Use

**building-dbt-semantic-layer**
- Create semantic models, metrics, dimensions, and entities
- Configure MetricFlow for business intelligence
- Support for both latest (1.12+) and legacy (1.6-1.11) YAML specs
- Define metric types: simple, derived, cumulative, ratio, conversion
- Set up time spines for time-based aggregations

**answering-natural-language-questions-with-dbt**
- Query the semantic layer to answer business questions
- Translate natural language to semantic layer queries
- Access metrics and dimensions without writing SQL

### Operations & Troubleshooting

**troubleshooting-dbt-job-errors**
- Diagnose dbt Cloud/platform job failures
- Resolve unclear or intermittent error messages
- Identify root causes in production environments

**configuring-dbt-mcp-server**
- Set up the dbt MCP server for Claude Desktop, Claude Code, Cursor, or VS Code
- Configure environment variables and credentials
- Troubleshoot connection issues

### Documentation & Commands

**fetching-dbt-docs**
- Look up dbt documentation efficiently
- Access information about dbt Cloud, dbt Core, and the Semantic Layer
- Find feature references and best practices

**running-dbt-commands**
- Execute dbt CLI commands with correct syntax
- Use proper flags, selectors, and parameter formats
- Determine which dbt executable to use (dbt vs dbtf)

### dbt Migration

**migrating-dbt-core-to-fusion**
- Resolves Fusion compatability errors and applies dbt-autofix commands
- Outputs dbt projects which will compile and run on dbt Fusion
- Unlocks next generation of dbt features and functionality

**migrating-dbt-project-across-platforms**
- Uses dbt Fusion engine for real-time compilation of pipelines from one data platform to another
- Geneartes unit tests to ensure output of migrated pipelines is equivalent
- Resolves any errors generated in Fusion engine by toggling dbt target data platform

## Prerequisites

Most skills assume:

- dbt is installed and configured in your environment
- A dbt project with `dbt_project.yml` exists
- Basic familiarity with dbt concepts (models, tests, sources)

Some skills like `fetching-dbt-docs` and `configuring-dbt-mcp-server` can be used without an existing project.

## How Skills Activate

Skills in this power use **automatic activation** based on your work context:

- When you mention dbt-related keywords in your prompts
- When you're working in files within a dbt project structure
- When you ask questions about analytics engineering, data modeling, or metrics

You don't need to explicitly invoke skills - Kiro loads the appropriate skill automatically when it detects relevant context.

## Getting Started

1. **Install the power** - Add this power through the Kiro Powers panel
2. **Open a dbt project** - Navigate to your dbt project directory
3. **Start working** - Ask Kiro to help with dbt tasks using natural language

Example prompts:
- "Add a new staging model for the users table"
- "Create a unit test for the orders model"
- "Define a revenue metric in the semantic layer"
- "Why is my dbt Platform job failing?"
- "Show me the compiled SQL for this model"
- "Can you help me migrate my project to dbt Fusion?"


## Compatibility

This power maintains compatibility with the vendor-agnostic [Agent Skills specification](https://agentskills.io/specification), ensuring it works across multiple AI development platforms including Claude Code, Cursor, Cline, and others.

## Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt CLI Reference](https://docs.getdbt.com/reference/dbt-commands)
- [dbt Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-semantic-layer)
- [Agent Skills Specification](https://agentskills.io/specification)

## Support

For issues, questions, or contributions:
- **GitHub Issues**: Report problems or suggest new skills
- **Repository**: [dbt-labs/dbt-agent-skills](https://github.com/dbt-labs/dbt-agent-skills)
- **dbt Community**: [community.getdbt.com](https://community.getdbt.com)

## License

Apache-2.0 - See [LICENSE](LICENSE) for details.
