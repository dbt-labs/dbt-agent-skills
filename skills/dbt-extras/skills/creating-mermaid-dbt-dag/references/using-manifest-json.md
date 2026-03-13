# Using manifest.json for Lineage Retrieval

This is the **second fallback method** when MCP lineage tools are not available. Read and parse the `manifest.json` file directly to extract lineage information.

## How to use

1. Locate the manifest.json file:
   - Usually in `target/manifest.json` in the dbt project root
   - May also be in project root as `manifest.json`

2. Read the manifest.json file:
   - First check the file size - if it's very large (>10MB), you may need to use streaming or partial reads
   - Look for the target model in the `nodes` section

3. Extract lineage from the manifest structure:
   ```json
   {
     "nodes": {
       "model.project.model_name": {
         "unique_id": "model.project.model_name",
         "resource_type": "model",
         "depends_on": {
           "nodes": ["model.project.upstream_model", "source.project.source_name"]
         },
         "original_file_path": "models/path/to/model.sql"
       }
     }
   }
   ```

4. Build the lineage graph:
   - **Parents**: Found in the `depends_on.nodes` array
   - **Children**: Search all nodes for ones that have this model in their `depends_on.nodes`

5. For each node in the lineage, extract:
   - `unique_id`
   - `resource_type` (model, source, seed, snapshot, exposure, test)
   - `original_file_path` or `path`
   - Any other relevant metadata

## Benefits

- ✅ Works offline
- ✅ No MCP server required
- ✅ Contains complete lineage information
- ✅ Includes all metadata

## Limitations

- ❌ Manifest can be very large (100MB+)
- ❌ May be slow to parse
- ❌ May not exist if `dbt parse` hasn't been run
- ❌ Only reflects last parse, not current uncommitted changes

## When to use

Use this method when:
- Both `get_lineage_dev` and `get_lineage` MCP tools are NOT available
- The manifest.json file exists and is reasonably sized (<10MB)
- You need complete lineage information

## Tips

- If the manifest is very large, consider reading it in chunks or using grep/search instead
- If you only need a specific model's lineage, you can use Grep to find just that section
- Check the manifest file size before attempting to read the entire file
