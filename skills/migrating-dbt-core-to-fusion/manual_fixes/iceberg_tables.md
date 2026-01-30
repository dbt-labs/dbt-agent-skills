# Iceberg Tables

## PROBLEM

Iceberg tables are not currently supported in dbt Fusion. When you encounter errors like:
- `Ignored unexpected key 'order_history_iceberg'. Try '+order_history_iceberg' instead.`
- `Ignored unexpected key '+order_history_iceberg'`

And the config key refers to a table with fields 'table_type: iceberg' or 'materialized: iceberg_table'.

This indicates that the project is trying to configure an Iceberg table, which is not supported in Fusion yet.

## SOLUTION

Since Iceberg tables are not supported in Fusion, you have two options:

### Option 1: Disable the Iceberg table model (Recommended)
Add `{{ config(enabled=false) }}` at the top of the Iceberg table model file to disable it for Fusion compatibility. Comment out references to the iceberg tables in `dbt_projects.yml` 

### Option 2: Move Iceberg configuration to meta
If you want to preserve the configuration for future use when Iceberg support is added, move the entire Iceberg table configuration under a `+meta` block in `dbt_project.yml`.

**Example transformation:**
```yaml
# Before (not supported in Fusion)
order_history_iceberg:
  +materialized: iceberg_table
  +file_format: parquet
  +table_type: iceberg
  +partition_by: ["order_date"]
  +clustered_by: ["customer_id"]

# After (Fusion compatible)
+meta:
  order_history_iceberg:
    materialized: iceberg_table
    file_format: parquet
    table_type: iceberg
    partition_by: ["order_date"]
    clustered_by: ["customer_id"]
```

## CHALLENGES

1. **Dependencies**: If other models depend on the Iceberg table, you may need to disable those models as well or provide alternative data sources.

2. **Data Access**: Disabling the model means the data won't be available in your dbt project when running with Fusion.

3. **Future Compatibility**: When Iceberg support is added to Fusion, you'll need to re-enable the model and move the configuration back from meta.

## RECOMMENDATION

For most cases, use Option 1 (disable the model) as it's cleaner and more explicit about what's not supported. Use Option 2 only if you need to preserve the configuration for documentation or future migration purposes.

## RESOURCES
- https://docs.getdbt.com/docs/fusion/supported-features#limitations
- https://docs.getdbt.com/docs/fusion/supported-features
