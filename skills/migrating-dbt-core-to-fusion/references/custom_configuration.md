# Custom configurations

## PROBLEM

Any config key that's not a part of the new authoring layer will cause Fusion to fail to parse. This error will show up as "Ignored unexpected key" in the parse logs. Unexpected config key could fall into one of two categories:
1. It's a misspelling of a supported config key (see misspelled_config_keys.md)
2. It's a custom config key (addressed in this file)


## SOLUTION
1. First check whether it's a misspelled config key. Follow misspelled_config_keys.md
2. If it's not a misspelled config key, move the custom config key under a `meta:` block. If the unsupported config key is in `dbt_projects.yml` it needs to be moved under a `+meta:` block. 


However, often a user project depends on these keys existing, especially in the case of:
- custom materializations
- custom incremental strategies

For example, it's easy enough to move these cold storage keys into `meta:` like below. However, it doesn't completely solve the issue.

```sql
{{
    config(
        materialized = 'incremental',
        unique_key = 'event_id',
        cold_storage = true,
        cold_storage_date_type = 'relative',
        cold_storage_period = var('cold_storage_default_period'),
        cold_storage_value = var('cold_storage_default_value')
    )
}}
```


```sql
{{
    config(
        materialized = 'incremental',
        unique_key = 'event_id',
        meta = {
            'cold_storage': true,
            'cold_storage_date_type': 'relative',
            'cold_storage_period': var('cold_storage_default_period'),
            'cold_storage_value': var('cold_storage_default_value')
        }
    )
}}
```

In these instances, not only do the unsupported config keys need to be moved under a new `meta:` key, but also any macro, or materialization that references those configs in jinja, need to be updated.

there are new wrapper functions that make this convenient:

- [`config.meta_get()`](https://docs.getdbt.com/reference/dbt-jinja-functions/config#configmeta_get)
- [`config.meta_require()`](https://docs.getdbt.com/reference/dbt-jinja-functions/config#configmeta_require)

for example:

this code
```sql
{% if config.get('cold_storage_date_type') == 'date' %}
```

needs to be changed to be this
```sql
{% if config.meta_get('cold_storage_date_type') == 'date' %}
```

the above just wraps the below behavior
```sql
{% if config.get('meta', {}).get('cold_storage_date_type') == 'date' %}
```

When you have many files (50+) with the same custom config pattern, use systematic approaches:

1. **Search for all affected files**: Use `grep` or similar to find all files with the custom config pattern
2. **Use Agent tools**: For bulk operations, use automation tools to apply the same transformation pattern across many files
3. **Verify the pattern**: Test the transformation on a few files first to ensure the pattern works
4. **Common patterns to move to meta:**
   - Any custom materialization configs
   - Custom incremental strategy configs


## CHALLENGES

### `config.get('user_custom_config)` returns `None`

When referencing custom configs that have been moved to `meta`, you may encounter Jinja errors like:
```
unknown method: none has no method named get
```

This happens when `config.get('meta')` returns `None` instead of an empty dictionary for models that don't have a `meta` section.

Update macro references to be null-safe:

Instead of:
```sql
{% set config_value = config.get('meta', {}).get('custom_key') %}
```

Use:
```sql
{% set config_value = config.get('meta', {}).get('custom_key', false) if config.get('meta') else false %}
```

Or set a local variable for cleaner code:
```sql
{% set meta_config = config.get('meta', {}) %}
{% if meta_config and meta_config.get('custom_key') %}
    -- do something
{% endif %}
```

## RESOURCES
- https://docs.getdbt.com/reference/deprecations#customkeyinconfigdeprecation
