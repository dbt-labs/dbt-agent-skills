# Using get_lineage for Lineage Retrieval

This is the **fallback method** when `get_lineage_dev` is not available. The `get_lineage` (or `mcp__dbt__get_lineage`) MCP tool reads from the production manifest in dbt Cloud.

## How to use

1. Call the `get_lineage` MCP tool with the model's unique_id
   - The unique_id follows the format: `model.{project_name}.{model_name}`
   - Must provide the full unique_id (not just the model name)

2. The tool returns a **flat list** of all nodes connected to the target resource (both upstream and downstream)

3. Each node in the list contains:
   - `uniqueId`: The resource's unique identifier
   - `name`: The resource name
   - `resourceType`: The type of resource (Model, Source, Seed, Snapshot, Exposure, Metric, Test, etc.)
   - `parentIds`: List of unique IDs that this resource directly depends on

4. To find parents and children, traverse the graph:
   - **Direct parents**: Look at the `parentIds` field of your target node
   - **Direct children**: Find all nodes where your target's `uniqueId` appears in their `parentIds` list

## Example usage

```python
# Get complete lineage (all connected nodes, all types, default depth of 5)
get_lineage(unique_id="model.jaffle_shop.customers")

# Get lineage filtered to only models and sources
get_lineage(
    unique_id="model.jaffle_shop.customers",
    types=["Model", "Source"]
)

# Get only immediate neighbors (depth=1)
get_lineage(
    unique_id="model.jaffle_shop.customers",
    depth=1
)

# Get deeper lineage for comprehensive analysis
get_lineage(
    unique_id="model.jaffle_shop.customers",
    depth=10
)
```

## Example response structure

```json
[
  {
    "uniqueId": "source.raw.users",
    "name": "users",
    "resourceType": "Source",
    "parentIds": []
  },
  {
    "uniqueId": "model.jaffle_shop.stg_customers",
    "name": "stg_customers",
    "resourceType": "Model",
    "parentIds": ["source.raw.users"]
  },
  {
    "uniqueId": "model.jaffle_shop.customers",
    "name": "customers",
    "resourceType": "Model",
    "parentIds": ["model.jaffle_shop.stg_customers"]
  }
]
```

## Traversing the graph

**Finding upstream dependencies (parents):**
```python
# What does this node depend on?
target_node = find_node_by_id(result, "model.jaffle_shop.customers")
direct_parents = target_node["parentIds"]
# Result: ["model.jaffle_shop.stg_customers"]
```

**Finding downstream dependents (children):**
```python
# What depends on this node?
target_id = "model.jaffle_shop.customers"
direct_children = [
    node for node in result
    if target_id in node.get("parentIds", [])
]
# Result: nodes that list "model.jaffle_shop.customers" in their parentIds
```

## Benefits

- ✅ Access to production lineage from dbt Cloud
- ✅ Fast - uses GraphQL API, no need to parse large JSON files
- ✅ Returns all nodes connected to the target (no disconnected nodes)
- ✅ Respects depth parameter for controlling graph traversal depth
- ✅ Can filter by resource types to reduce payload size
- ✅ Automatically filters out macros (which have large dependency graphs)

## Limitations

- ❌ Only shows production state (not local uncommitted changes)
- ❌ Requires dbt Cloud connection and Discovery API access
- ❌ Must provide full unique_id (can't use just model name)
- ❌ Does NOT include file paths (only uniqueId, name, resourceType, parentIds)

## Understanding the results

- The target node is always included in the response
- All returned nodes are connected to the target (directly or indirectly)
- To get full lineage, omit the `types` parameter
- To reduce payload size, specify relevant `types` like `["Model", "Source"]`
- The `depth` parameter controls traversal:
  - `depth=0`: infinite (entire connected graph)
  - `depth=1`: immediate neighbors only
  - `depth=5`: default, goes 5 levels deep in both directions

## When to use

Use this method when:
- The `get_lineage` MCP tool is available
- `get_lineage_dev` is NOT available
- You want to see the production lineage (not local changes)
- You have dbt Cloud with Discovery API enabled
