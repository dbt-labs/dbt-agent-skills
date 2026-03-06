# Error Patterns Reference

Complete catalog of dbt-core to Fusion migration error patterns, organized by type.

## Contents
- [YAML Issues](#yaml-issues)
- [Package Issues](#package-issues)
- [Config/API Changes](#configapi-changes)
- [SQL/Jinja Issues](#sqljinja-issues)
- [Static Analysis Issues](#static-analysis-issues)
- [Source Name Issues](#source-name-issues)
- [Schema/Model Issues](#schemamodel-issues)
- [Connection/Credential Errors](#connectioncredential-errors)
- [Fusion Engine Gaps (Category D)](#fusion-engine-gaps-category-d)

## YAML Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1013` | "YAML mapping values not allowed" | Fix YAML syntax (quotes, indentation, remove extra colons) |
| `dbt1060` | "Unexpected key in config" | Move custom keys to `meta:` section (but check if it's a misspelling first — see below) |
| `dbt0102` | "No tables defined for source" | Delete empty source definition, or move config to `dbt_project.yml` |
| — | Empty `data_type:` value | Provide a value or remove the key |

### Misspelled config keys after autofix

dbt-autofix moves unrecognized config keys into `meta:`. But some may be misspelled versions of real config keys (e.g. `materailized` instead of `materialized`). Check if any key inside `meta:` is a near-match for a known Fusion config key. If it's a typo: move it back out of `meta:` with the correct spelling. If it's truly custom: leave it in `meta:` and update macro references to use `config.meta_get('key')`.

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
| `dbt1001` | "Failed to parse package-lock.yml" or malformed lockfile | Delete `package-lock.yml` (it will regenerate on `dbt deps`) |
| `dbt1005` | "Package not in lookup map" | Update package version in `packages.yml` |
| `dbt8999` | "Cannot combine non-exact versions" | Use exact pins (e.g., `"==1.0.0"`) |
| — | `require-dbt-version` error | Update version constraint |
| — | "package incompatible", "failed to resolve", "dependency conflict" | Look up latest compatible version on hub.getdbt.com, update packages.yml |

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

**Note**: After changing package versions, delete `package-lock.yml` and the `dbt_packages/` directory, then run `dbt deps`. If errors persist, run `dbt-autofix deprecations --include-packages`.

**Note**: Fivetran `_source` packages have been merged into main packages (e.g. `fivetran/microsoft_ads_source` is now `fivetran/microsoft_ads`).

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
| `dbt0214` | "Permission denied" | Check credentials or use `{{ ref() }}` / `{{ source() }}` |
| `dbt1502` | Missing `{% endif %}`, "unexpected end of template" | Balance if/endif, for/endfor, macro/endmacro pairs |
| `dbt1000` | "syntax error: unexpected identifier" with nested quotes | Use single quotes outside: `warn_if='{{ "text" }}'` |
| — | Dangling identifiers (hardcoded `database.schema.table`) | Replace with `{{ ref() }}` or `{{ source() }}` |
| — | PIVOT ... IN (ANY) unsupported by static analysis | Refactor to hard-coded values or disable static analysis |

### Example: Quote nesting fix

```yaml
# Before (dbt1000)
tests:
  - accepted_values:
      arguments:
        values: [1, 2, 3]
      config:
        warn_if: "{{ 'count' == 0 }}"

# After
tests:
  - accepted_values:
      arguments:
        values: [1, 2, 3]
      config:
        warn_if: '{{ "count" == 0 }}'
```

## Static Analysis Issues

| Error Code | Signal | Fix |
|------------|--------|-----|
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
| — | SQL parsing errors under static analysis | Suggest rewriting the logic (with user approval), or set `static_analysis: off` for the model |
| — | "--models flag deprecated" | If the repro command uses `--models/-m`, replace with `--select/-s` |

## Connection/Credential Errors

| Error Code | Signal | Fix |
|------------|--------|-----|
| `dbt1308` | "constructing client", "connection", "authentication", "credentials" | Check `profiles.yml` and data platform credentials — not a migration issue |

> **Tip**: These errors can often be caught early by running `dbt debug` (see Step 0).

## Fusion Engine Gaps (Category D)

These require Fusion engine updates. Alternatives can be suggested with caveats about risks and fragility.

| Signal | Meaning | Action |
|--------|---------|--------|
| MiniJinja filter differences (e.g. `truncate()` argument mismatch) | Fusion's MiniJinja engine doesn't support the same filter signatures as Jinja2 | Search GitHub issues, link if found. Some have clean workarounds (e.g. string slicing) |
| Parser gaps / missing implementations | Feature not yet implemented in Fusion | Search GitHub issues |
| Wrong materialization dispatched (e.g. seeds dispatched to table macro) | Internal dispatch bug | No user workaround — requires Fusion fix |
| Unsupported macro patterns | Macro works in dbt-core but not in Fusion | Document, check for tracked issue |
| Adapter-specific functionality gaps (e.g. `not yet implemented: Adapter::method`) | Adapter feature not available in Fusion | Document, check for tracked issue |
| `panic!` / `internal error` / `RUST_BACKTRACE` | Fusion engine crash | Search GitHub issues, report if not found |
