# Inputs (`fix.by: data`)

Lake Compute reads Iceberg tables only. Some fixes happen outside the dbt
project, in how the data lands. Tell the user what's needed. Don't try to fix
it in the models.

## A source that isn't Iceberg (`changes[].kind: source_iceberg`)

The source's tables have to land in Iceberg (through the user's ingestion
tool, or as Snowflake-managed Iceberg tables). Then declare it with
`catalog_name` in its `sources:` YAML, naming a catalog the project's
`catalogs.yml` declares:

```yaml
sources:
  - name: raw
    config:
      catalog_name: lake
    tables:
      - name: orders
```

## Tables read without `source()` or `ref()` (`undeclared:<DATABASE>`)

The model reads a table by its name (`from raw.orders`), or through a macro
that finds tables (for example `dbt_utils.get_relations_by_pattern`). Declare
each table as a source, use `source()` in the model, and land it in Iceberg as
above.

## Group what the user has to do

Many models usually wait on the same few sources. The report's text summary
lists them under "Inputs to change, most read first". Give the user that list,
with how many models each one unblocks.
