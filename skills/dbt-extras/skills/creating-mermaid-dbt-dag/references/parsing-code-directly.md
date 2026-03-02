# Parsing Code Directly for Lineage Retrieval

This is the **last resort method** when all other approaches fail (no MCP tools available, manifest.json too large or missing). Directly parse the model's SQL/Python code to extract dependencies.

## How to use

1. Locate the model file:
   - Use Glob to find the model file: `models/**/{model_name}.sql` or `models/**/{model_name}.py`
   - Check common locations: `models/staging/`, `models/marts/`, etc.

2. Read the model file and extract dependencies:

   **For SQL models:**
   - Look for `{{ ref('model_name') }}` calls - these are model dependencies
   - Look for `{{ source('source_name', 'table_name') }}` calls - these are source dependencies
   - Parse both single and double quoted strings

   **For Python models:**
   - Look for `dbt.ref('model_name')` calls - these are model dependencies
   - Look for `dbt.source('source_name', 'table_name')` calls - these are source dependencies

3. Find downstream dependencies (children):
   - Use Grep to search for references to this model in other files
   - Search for `{{ ref('current_model_name') }}` across the project
   - Search in common model directories: `models/staging/`, `models/intermediate/`, `models/marts/`

4. Determine node types (best effort):
   - **Models**: Files in `models/` directory with `.sql` or `.py` extension
   - **Sources**: References found in `{{ source() }}` calls (you may need to check `models/sources.yml` or similar)
   - **Seeds**: Files in `seeds/` directory with `.csv` extension
   - **Exposures**: Check `models/**/*.yml` for exposure definitions

5. Build limited lineage graph:
   - Only direct parents (1 level up) and children (1 level down) may be available
   - File paths can be constructed from found references

## Example Grep patterns

```bash
# Find all refs to a model
grep -r "ref('customers')" models/

# Find all source calls
grep -r "source(" models/staging/

# Find model file
find models/ -name "customers.sql"
```

## Benefits

- ✅ Always works as long as you have file access
- ✅ Doesn't require manifest or MCP tools
- ✅ Can handle very large projects
- ✅ Shows current state of code (including uncommitted changes)

## Limitations

- ❌ Labor intensive - requires multiple file reads and searches
- ❌ May miss indirect dependencies
- ❌ Limited to immediate parents/children (1 level deep)
- ❌ Cannot easily determine full graph depth
- ❌ May not capture all node types (tests, snapshots, etc.)
- ❌ Doesn't capture metadata like column lineage
- ❌ Won't catch dynamic references

## When to use

Use this method **only** when:
- All MCP lineage tools are unavailable
- manifest.json is too large (>10MB) or doesn't exist
- You just need a basic lineage view
- You're willing to accept incomplete lineage information

## Important notes

⚠️ This method provides **best-effort lineage** and may be incomplete. If possible, try to:
1. Generate a fresh manifest with `dbt parse` and use the manifest.json method instead
2. Enable the dbt MCP server to use the tool-based approaches
3. Warn the user that the lineage may be incomplete
