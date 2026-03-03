# Error Patterns Reference

Complete catalog of dbt-core to Fusion migration error patterns, organized by type.

## YAML Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1013` | "YAML mapping values not allowed" | Fix YAML syntax (quotes, indentation, remove extra colons) |
| `dbt1060` | "Unexpected key in config" | Move custom keys to `meta:` section |
| — | Empty `data_type:` value | Provide a value or remove the key |

### Example: Unexpected config key

```yaml
# Before (dbt1060)
models:
  - name: my_model
    config:
      my_custom_key: value

# After
models:
  - name: my_model
    config:
      meta:
        my_custom_key: value
```

## Package Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1005` | "Package not in lookup map" | Update package version in `packages.yml` |
| `dbt8999` | "Cannot combine non-exact versions" | Use exact pins (e.g., `"==1.0.0"`) |
| — | `require-dbt-version` error | Update version constraint |

### Example: Package version pinning

```yaml
# Before (dbt8999)
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.0.0"

# After
packages:
  - package: dbt-labs/dbt_utils
    version: "==1.3.0"
```

**Note**: After changing package versions, delete `package-lock.yml` and the `dbt_packages/` directory, then run `dbt deps`.

## Config/API Changes

| Error Code | Signal | Pattern | Fix |
|------------|--------|---------|-----|
| `dbt1501` | "Argument must be a string or a list. Received: (empty)" | `config.require('meta').key_name` | `config.meta_require('key_name')` |
| `dbt1501` | "unknown method: map has no method named meta_get" | `some_dict.meta_get('key', default)` | `some_dict.get('key', default)` |
| `dbt1501` | "Duplicate doc block" | Duplicate doc block names | Rename or delete conflicting doc blocks |

### Example: Config API migration

```sql
-- Before (dbt1501)
{% set keys = config.require('meta').logical_key %}
{% set owner = config.require('meta').owner %}

-- After
{% set keys = config.meta_require('logical_key') %}
{% set owner = config.meta_require('owner') %}
```

### Example: Plain dict meta_get fix

```sql
-- Before (dbt1501)
{% set val = some_dict.meta_get('key', 'default') %}

-- After
{% set val = some_dict.get('key', 'default') %}
```

**Important**: Only `config` objects have `meta_get()` and `meta_require()`. Plain dicts use `.get()`.

## SQL/Jinja Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt0404` | "SELECT with no columns" | Add `SELECT 1` or actual column list |
| `dbt0214` | "Permission denied" | Check credentials or use `{{ ref() }}` / `{{ source() }}` |
| `dbt1502` | Missing `{% endif %}` | Balance if/endif pairs |
| `dbt1000` | "syntax error: unexpected identifier" with nested quotes | Use single quotes outside: `warn_if='{{ "text" }}'` |
| — | Dangling identifiers (hardcoded `database.schema.table`) | Replace with `{{ ref() }}` or `{{ source() }}` |

### Example: Quote nesting fix

```yaml
# Before (dbt1000)
tests:
  - accepted_values:
      values: [1, 2, 3]
      config:
        warn_if: "{{ 'count' == 0 }}"

# After
tests:
  - accepted_values:
      values: [1, 2, 3]
      config:
        warn_if: '{{ "count" == 0 }}'
```

## Static Analysis Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt0209` | "Function not found in static analysis" | Add function to project or disable static analysis |
| `dbt02xx` (in `analyses/`) | Static analysis errors in analyses directory | Add `{{ config(static_analysis='off') }}` at top of file |

### Example: Disable static analysis

```sql
-- Add at top of analyses/explore_data.sql
{{ config(static_analysis='off') }}

SELECT *
FROM {{ ref('my_model') }}
```

## Source Name Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1005` | "Source 'Close CRM' not found" | Align `source()` references with YAML definitions |

Fusion requires exact name matching. dbt-core was lenient with spaces vs underscores.

```sql
-- If YAML defines source as 'close_crm'
-- Before
{{ source('Close CRM', 'contacts') }}

-- After
{{ source('close_crm', 'contacts') }}
```

## Schema/Model Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1005` | "Unused schema.yml entry for model 'ModelName'" | Remove orphaned YAML entry (model SQL doesn't exist) |
| `dbt1021` | "Seed cast error" | Clean CSV (ISO dates, lowercase `null`, consistent columns) |
| — | "--models flag deprecated" | Replace `--models/-m` with `--select/-s` |

## Fusion Engine Gaps (Category D)

These are NOT fixable in user code. They require Fusion engine updates.

| Signal | Meaning | Action |
|--------|---------|--------|
| MiniJinja filter differences (e.g. `truncate()` argument mismatch) | Fusion's MiniJinja engine doesn't support the same filter signatures as Jinja2 | Search GitHub issues, link if found |
| Parser gaps / missing implementations | Feature not yet implemented in Fusion | Search GitHub issues |
| Unsupported macro patterns | Macro works in dbt-core but not in Fusion | Document, check for tracked issue |
| Adapter-specific functionality gaps | Adapter feature not available in Fusion | Document, check for tracked issue |
