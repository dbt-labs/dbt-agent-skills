# Fusion Validation

## Overview

After adding SAO configs, validate them by compiling the project. This catches syntax errors, invalid YAML, and misconfigured freshness settings before they hit production.

## Validation Steps

### 1. Compile the Full Project

Run a full compile to check for syntax errors across all models:

```bash
dbt compile
```

If using dbt MCP tools, you can also compile specific models:

```bash
dbt compile --select model_name
```

**What to check:**
- No YAML parsing errors
- No Jinja compilation errors
- No warnings about invalid `freshness` config keys

### 2. Check Specific Model Configs

After compile, verify that freshness configs resolved correctly by reading the compiled manifest or checking model details:

```
Tool: get_model_details
Input: model_name: <name>
```

Confirm:
- `build_after.count` and `build_after.period` are set as expected
- `updates_on` is the intended value
- No unintended inheritance from parent configs

### 3. Validate Source Freshness

For sources with `loaded_at_field` or `loaded_at_query`:

```bash
dbt source freshness --select source:source_name
```

**What to check:**
- The query executes without error
- Returns a valid timestamp
- `warn_after` and `error_after` thresholds are reasonable

### 4. Check for Common Errors

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Unknown config key: freshness` | Older dbt version without SAO support | Ensure Fusion engine is enabled |
| `build_after requires both count and period` | Missing one of the two required fields | Add the missing field |
| YAML parse error on `freshness` block | Indentation issue or invalid YAML | Check indentation matches examples |
| `loaded_at_field and loaded_at_query are mutually exclusive` | Both defined on same source/table | Remove one |
| `updates_on must be 'any' or 'all'` | Typo or Jinja expression (not supported) | Use literal `any` or `all` |
| Model not respecting config | Config at wrong YAML nesting level | Ensure `config.freshness.build_after` path in model YAML |

### 5. Verify Config Inheritance

If you set project-level defaults plus per-model overrides, confirm the override takes effect:

1. Check the project-level default applies to a model WITHOUT an override
2. Check the per-model override applies to a model WITH an override
3. Check that `freshness: null` correctly opts out a model

## Iterative Fix Cycle

If validation fails:

1. **Read the error message** — dbt error messages for config issues are usually clear
2. **Check the YAML syntax** — most issues are indentation or nesting errors
3. **Fix the specific issue** — don't change other configs at the same time
4. **Re-compile** — verify the fix resolved the error
5. **Move on** — continue with the next model or layer

## When Validation Is Complete

SAO config is validated when:
- `dbt compile` succeeds with no errors
- Source freshness queries execute successfully (if configured)
- Each model's resolved config matches the intended classification
- No unexpected config inheritance is occurring
