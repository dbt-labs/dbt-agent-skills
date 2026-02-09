---
name: creating-mermaid-dbt-dag
description: Use when visualizing dbt model lineage and dependencies as a Mermaid diagram in markdown format
user-invocable: false
allowed-tools: mcp__dbt__get_lineage_dev, mcp__dbt__get_lineage, Read, Grep, Glob, Bash
metadata:
  author: dbt-labs
---

# Create Mermaid Diagram in Markdown from DBT DAG
This skill helps you create a mermaid diagram of a dbt model and its dependencies. 
It is particularly useful for visualizing the relationships between models in a DBT project.

## How to use this skill

### Step 1: Determine the model name

1. If name is provided, use that name
2. Elif user is focused on a file, use that name
3. If you don't know the model that you want to generate a diagram for: ask immediately.
    a. Prompt the user to specify the model name.
		b. if the user needs to know what models are available, then you can query the list of models.
4. If the user doesn't specify, it's probably a good idea to ask them if they want to include tests in the diagram.


### Step 2: Fetch the DBT model lineage (hierarchical approach)

Follow this hierarchy to retrieve lineage information. Use the first available method:

1. **Primary: Use get_lineage_dev MCP tool** (if available)
   - See [using-get-lineage-dev.md](./references/using-get-lineage-dev.md) for detailed instructions
   - This is the preferred method - provides most accurate local lineage. If the user asks specifically for production lineage, this may not be suitable.

2. **Fallback 1: Use get_lineage MCP tool** (if get_lineage_dev not available)
   - See [using-get-lineage.md](./references/using-get-lineage.md) for detailed instructions
   - Provides production lineage from dbt Cloud. If the user asks specifically for local lineage, this may not be suitable.	

3. **Fallback 2: Parse manifest.json** (if no MCP tools available)
   - See [using-manifest-json.md](./references/using-manifest-json.md) for detailed instructions
   - Works offline but requires manifest file
   - Check file size first - if too large (>10MB), skip to next method

4. **Last Resort: Parse code directly** (if manifest.json too large or missing)
   - See [parsing-code-directly.md](./references/parsing-code-directly.md) for detailed instructions
   - Labor intensive but always works
   - Provides best-effort incomplete lineage

### Step 3: Generate the mermaid diagram
1. Use the formatting guidelines below to create the diagram
2. Include all nodes from the lineage (parents and children)
3. Add appropriate colors based on node types

### Step 4: Return the mermaid diagram
1. Return the mermaid diagram in markdown format
2. Include the legend
3. If using fallback methods (manifest or code parsing), note any limitations

## When to use this skill
Use this skill when you need to generate a mermaid diagram of a dbt model and its dependencies.
This will give you a visual representation of your DBT project's model dependencies.
This can help in understanding the structure of your data transformations and in documenting your DBT project.
If the user requests a specific model, focus on that model's lineage.

## Common use cases for lineage diagrams

1. **Impact Analysis**: "What will break if I change this model?"
   - Visualize downstream dependents to understand the blast radius of changes
   - Identify all models, exposures, and tests that depend on the target model

2. **Dependency Tracking**: "What does this model depend on?"
   - See upstream dependencies to understand data sources and transformations
   - Trace data lineage back to raw sources

3. **Data Lineage**: "Show the complete data flow for this entity"
   - Visualize the entire transformation pipeline from sources to final models
   - Understand how data flows through the dbt project

4. **Finding Tests**: "What tests exist for this model and its dependencies?"
   - Include tests in the diagram to see test coverage
   - Identify gaps in test coverage across the lineage

## Formatting Guidelines
When creating the mermaid diagram, follow these guidelines:
- Use the `graph LR` directive to define a left-to-right graph.
- Color these nodes as follows
	- selected node: Highlighted in Purple
	- source nodes: Blue
	- staging nodes: Bronze
	- intermediate nodes: Silver
	- mart nodes: Gold
	- seeds: Green 
	- exposures: Orange
	- tests: Yellow
	- undefined nodes: Grey
- Represent each model as a node in the graph.
- Include a legend explaining the color coding used in the diagram.
- Make sure the text contrasts well with the background colors for readability.

