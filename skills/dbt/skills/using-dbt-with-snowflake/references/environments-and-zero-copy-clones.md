# Environments and Zero-Copy Clones on Snowflake

## Layout: environments differ by database

```
RAW_DB.<SOURCE>                          data as delivered, written by the loader; dbt only reads it
TEST_DB.SRC                              zero-copy clones of the raw tables: the test data sets
TEST_DB.{STAGING,INTERMEDIATE,MARTS}     dbt target `test` - the default target
PROD_DB.{STAGING,INTERMEDIATE,MARTS}     dbt target `prod` - built from the main branch only, reads RAW_DB directly
```

With one database per environment, the schema name can simply be the layer name in every environment. Override `generate_schema_name` so dbt does not prefix it with the target schema:

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%} {{ target.schema }}
    {%- else -%} {{ custom_schema_name | trim | upper }}
    {%- endif -%}
{%- endmacro %}
```

This only works when each environment, or each developer, has its own database. Two developers sharing one database would overwrite each other's `STAGING` schema.

## Sources that follow the target

Name the targets that read clones in one variable, an allow-list, so that any other target - production under any name - reads raw data:

```yaml
# dbt_project.yml
vars:
  clone_targets: [test]
```

```yaml
# models/sources.yml
sources:
  - name: raw_sales
    database: "{{ target.database if target.name in var('clone_targets') else 'RAW_DB' }}"
    schema:   "{{ 'SRC' if target.name in var('clone_targets') else 'SALES' }}"
    tables:
      - name: orders
        identifier: "{{ 'SRC_ORDERS' if target.name in var('clone_targets') else 'ORDERS' }}"
```

## Refreshing the test data with zero-copy clones

A clone shares storage with its source until either one changes, so refreshing test data is fast and cheap. A `run-operation` macro creates the clones:

```sql
-- macros/refresh_src.sql
-- Destructive: replaces the SRC schema of the target database. Nothing else may live in that schema.
{% macro refresh_src() %}
  {% if target.name not in var('clone_targets') %}
    {{ exceptions.raise_compiler_error("refresh_src runs only on the targets in var clone_targets") }}
  {% endif %}
  {% set clones = {'SRC_ORDERS': 'ORDERS', 'SRC_CUSTOMERS': 'CUSTOMERS'} %}
  {% set src = target.database ~ '.SRC' %}
  {% do run_query('create or replace schema ' ~ src) %}
  {% for clone_name, raw_name in clones.items() %}
    {% do run_query('create table ' ~ src ~ '.' ~ clone_name ~ ' clone RAW_DB.SALES.' ~ raw_name) %}
  {% endfor %}
{% endmacro %}
```

```bash
# fresh test data, then build and test on it
dbt run-operation refresh_src
dbt build
```

- **Guard by allow-list.** Checking for a single production name (`target.name == 'prod'`) would let a target called `production` wipe a schema in the production database.
- **Clone table by table.** A clone is created and owned by the current primary role, so the dbt role can later replace it. A schema or database clone carries over the grants of its child objects, so its tables can stay owned by their original role and dbt may not be able to replace them.
- **A clone is a point-in-time copy.** Refresh it explicitly; it does not follow raw data.
- **`dbt clone` is a different tool:** it clones *dbt-built* relations from another environment's state (for deferral and CI). `refresh_src` clones *raw* tables as test data.

## Recovery with Time Travel

If a table was dropped, an administrator or the loader restores it, after approval, because it changes raw data:

```sql
undrop table RAW_DB.SALES.ORDERS;
```

Rows deleted or changed by mistake: restore a copy from Time Travel into a **separate** schema, compare, then put the rows back:

```sql
create table TEST_DB.SCRATCH.ORDERS_RESTORED
  clone RAW_DB.SALES.ORDERS at (offset => -3600);          -- the table as of one hour ago
-- or: at (timestamp => '<ts>'::timestamp_tz)  /  before (statement => '<query_id>')
```

1. Stop the process that writes.
2. Find the query id of the bad statement in `snowflake.account_usage.query_history`.
3. Restore into the scratch schema, compare row counts and keys.
4. Insert back or swap, with approval.

Check the retention first: `show parameters like 'DATA_RETENTION_TIME_IN_DAYS' in table <table>`. Standard edition keeps up to 1 day of Time Travel; longer retention needs Enterprise edition or higher. Tables built by dbt are `transient` by default: they have no Fail-safe period and at most 1 day of Time Travel (`+transient: false` to change it).
