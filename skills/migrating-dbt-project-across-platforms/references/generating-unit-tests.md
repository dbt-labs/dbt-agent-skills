# Generating Unit Tests for Cross-Platform Migration

## PROBLEM

Before migrating to a target platform, we need to capture the expected data outputs from the source platform. dbt unit tests serve as a "golden dataset" that proves data consistency after migration — if the same inputs produce the same outputs on both platforms, the migration preserves business logic.

## SOLUTION

### Which models to test

The primary criterion is **DAG position**, not naming convention. Focus on:

1. **Leaf nodes** — Models at the very end of the DAG that no other **model** depends on (exposures, metrics, and semantic models don't count — only model-to-model `ref()` dependencies matter). These are the final outputs consumed by BI tools, reverse ETL, exports, and downstream systems. **Every leaf node must have a unit test** — no exceptions. See the "Identifying leaf nodes" section below for reliable methods.
2. **Models with significant transformation logic** — Even if mid-DAG, any model with complex joins, calculations, or case statements should be tested. The more business logic a model contains, the more important it is to verify.

**Skip**:
- **Staging models** — Simple 1:1 source mappings; if sources are correct, staging will be correct
- **Pass-through models** — Models that just rename columns or filter rows without business logic

**If leaf nodes have common naming conventions** (e.g., `fct_*`, `dim_*`, `agg_*`), that's a helpful heuristic — but don't rely on it exclusively. A model named `customer_summary` at the end of the DAG is just as important to test as one named `dim_customers`.

### Identifying leaf nodes

**Do not guess leaf nodes from naming conventions.** You must programmatically derive them. A leaf node is an enabled model that is not referenced via `ref()` by any other enabled model. Exposures, metrics, and semantic models referencing a model do NOT disqualify it as a leaf node.

**Method 1: Set difference with `dbt ls` (recommended)**

```bash
# Step 1: Get all enabled model unique IDs
dbt ls --resource-type model --output json | jq -r '.unique_id' | sort > /tmp/all_models.txt

# Step 2: Get all model unique IDs that appear as a dependency of another model
dbt ls --resource-type model --output json | jq -r '.depends_on.nodes[]?' | grep '^model\.' | sort -u > /tmp/parent_models.txt

# Step 3: Leaf nodes = all models minus those that are parents
comm -23 /tmp/all_models.txt /tmp/parent_models.txt
```

**Method 2: Read the model SQL files directly**

If `dbt ls` is unavailable or impractical, scan all `.sql` files under `models/` and build the ref graph manually:

1. List all enabled model file names (check `dbt_project.yml` for `+enabled: false` to exclude disabled models)
2. For each model, extract all `ref('model_name')` calls
3. Build a set of "referenced models" — any model name that appears inside a `ref()` in another model's SQL
4. Leaf nodes = all enabled models whose name does NOT appear in the "referenced models" set

**Method 3: dbt MCP tools (if available)**

Use `get_model_children` for each model. Models with no children (or children that are only exposures/metrics/semantic models) are leaf nodes.

**Important**: After identifying leaf nodes, list them all explicitly and confirm the count before proceeding to write unit tests. Do not assume 2-3 leaf nodes just because only `fct_*` and `dim_*` names are visible — utility models, aggregates, incremental variants, and unconventionally named models are all potential leaf nodes.

### How to select test rows

Use `dbt show` to preview model outputs on the source platform:

```bash
dbt show --select fct_orders --limit 10
```

**Select rows that exercise key logic**:
- Rows that hit different branches of `CASE WHEN` statements
- Rows with NULL values in columns that have COALESCE/NVL logic
- Rows with edge case values (zero quantities, negative amounts, boundary dates)
- At minimum, 2-3 rows per model

### Writing unit tests

Place unit tests in the model's YAML file or a dedicated `_unit_tests.yml` file in the same directory. Use the `dict` format for readability:

```yaml
unit_tests:
  - name: test_fct_orders_basic
    description: "Verify core order calculations"
    model: fct_orders
    given:
      - input: ref('stg_orders')
        rows:
          - {order_key: 1, customer_key: 100, order_date: '1998-01-01', status_code: 'F', total_price: 150.00}
          - {order_key: 2, customer_key: 200, order_date: '1998-06-15', status_code: 'O', total_price: 0.00}
      - input: ref('stg_line_items')
        rows:
          - {order_key: 1, line_number: 1, extended_price: 100.00, discount: 0.05, tax: 0.08}
          - {order_key: 1, line_number: 2, extended_price: 50.00, discount: 0.00, tax: 0.08}
          - {order_key: 2, line_number: 1, extended_price: 0.00, discount: 0.00, tax: 0.00}
    expect:
      rows:
        - {order_key: 1, customer_key: 100, order_status: 'fulfilled', gross_amount: 150.00}
        - {order_key: 2, customer_key: 200, order_status: 'open', gross_amount: 0.00}
```

For detailed unit test authoring guidance, refer to the `adding-dbt-unit-test` skill if you have access to it.

### Verify tests pass on source platform

Before starting migration, confirm all unit tests pass on the source:

```bash
dbt test --select test_type:unit
```

All tests must pass. If any fail, fix them before proceeding — failed tests on the source platform indicate a test authoring issue, not a migration issue.

## CHALLENGES

### Large or complex models

For models with many input sources or complex joins:
- Start with a minimal test covering the primary join path
- Add additional tests for specific business logic branches
- You don't need to test every column — focus on calculated/derived columns

### Handling platform-specific functions in test data

If the source model uses platform-specific functions that produce specific data types:
- Use literal values in test expectations rather than function calls
- Focus on the business-meaningful output values, not intermediate representations

### Models with many columns

You don't need to include every column in the `expect` block. Include only the columns that have business logic applied — columns that are simple pass-throughs from inputs don't need explicit verification.

### Incremental models

For incremental models, unit tests should test the transformation logic, not the incremental behavior. Provide input rows and verify the output — the incremental strategy is a materialization concern, not a logic concern.

### Using dbt show for quick validation

Before writing formal unit tests, use `dbt show` to understand what a model outputs:

```bash
# Preview output
dbt show --select model_name --limit 5

# Preview with inline filter for specific scenarios
dbt show --inline "select * from {{ ref('model_name') }} where status = 'returned'" --limit 5
```

This helps you pick representative test rows and understand the expected output format.
