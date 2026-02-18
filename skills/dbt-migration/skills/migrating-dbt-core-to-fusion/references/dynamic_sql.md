# Limitations of Dynamic SQL

## PROBLEM

Some SQL patterns that work in legacy dbt may not be supported by Fusion's static analysis, such as:
```sql
PIVOT(...) FOR column_name IN (ANY)
```

## SOLUTION

The first option is always preferred and should be attempted first, if possible. 

### option 1: refactor

refactor away any instances of `PIVOT(...) FOR column_name IN (ANY)` to have hard-coded values.

### option 2: disable static analysis

For models with unsupported dynamic SQL:
1. Add `static_analysis = 'off'` to the model config:
```sql
{{
    config(
        materialized = 'table',
        meta = {
            'static_analysis': 'off'
        }
    )
}}
```

2. Or disable static analysis globally for the model in `dbt_project.yml`