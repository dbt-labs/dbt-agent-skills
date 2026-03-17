# Using get_lineage_dev for Lineage Retrieval

This is the **preferred method** when available. The `get_lineage_dev` (or `mcp__dbt__get_lineage_dev`) MCP tool reads from the local development manifest and provides the most accurate and up-to-date lineage information.

## How to use

1. Call the `get_lineage_dev` MCP tool with the model's unique_id
   - The unique_id follows the format: `model.{project_name}.{model_name}`
   - If you only have the model name, you can try with just the name or construct the unique_id

2. The tool returns a lineage graph with:
   - `parents`: upstream dependencies (models, sources, seeds that this model depends on)
   - `children`: downstream dependencies (models, exposures that depend on this model)

3. Parse the lineage response to extract:
   - Node unique_ids
   - Node types (model, source, seed, exposure, test, etc.)
   - File paths for each node
   - Relationships between nodes

## Example usage

```
get_lineage_dev(
    unique_id="model.jaffle_shop.customers",
    depth=5  # Controls how many levels to traverse
)
```

## Benefits

- ✅ Most accurate - reads from local development manifest
- ✅ Fast - no need to parse large JSON files
- ✅ Includes all metadata (file paths, node types, etc.)
- ✅ Respects depth parameter for controlling graph size

## When to use

Use this method when:
- The `get_lineage_dev` MCP tool is available
- You're working in a local development environment
- You want the most current lineage (including uncommitted changes)
