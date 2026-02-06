---
name: migrating-dbt-core-to-fusion
description: Guides migration of dbt projects from dbt Core to the Fusion engine. Use when making a project compatible with Fusion, addressing deprecations, or running dbtf commands.
compatibility: Designed for dbt Core v1.10+
metadata:
  author: dbt-labs
---

# Migrating a dbt Core Project to Fusion

dbt Fusion is dbt Labs' next-generation engine for parsing, compiling, and running dbt projects.

**Success criteria**: Migration is complete when `dbtf compile` finishes with 0 errors.

## Additional Resources

- [Custom Configuration](references/custom_configuration.md) - Moving custom config keys to `meta` block
- [Dynamic SQL Patterns](references/dynamic_sql.md) - Resolving dynamic SQL compatibility issues
- [Misspelled Config Keys](references/misspelled_config_keys.md) - Fixing misspelled config keys

## Migration Workflow

### Progress Checklist

Copy this checklist to track migration progress:

```
Migration Progress:
- [ ] Step 1: Run dbtf debug (verify connection)
- [ ] Step 2: Run dbtf parse --show-all-deprecations (identify errors)
- [ ] Step 3: Install and run dbt-autofix for package updates and deprecations
- [ ] Step 4: Fix remaining errors manually using resources
- [ ] Step 5: Run dbtf compile (0 errors = success)
```

### Instructions

If a user says "migrate my dbt project to the new authoring layer" or "make my dbt project compatible with the Fusion engine" follow these steps. Create a `changes_made.md` file documenting all code changes (see template below).

**Important**: Only apply fixes described in the provided Resources. Do not attempt undocumented fixes—if a solution isn't in these resources, inform the user and stop.

1. Run `dbtf debug` in the terminal to check their data platform connections. Proceed to step 2 if there are no errors. If there are errors, please summarize the error succinctly so the user knows how to debug on their own.
2. Run `dbtf parse --show-all-deprecations` in the terminal to check for compatibility errors in their current project. Summarize the log output by specifying how many errors were found and group the errors in a way that's easily understandable.
3. Install [dbt-autofix](https://github.com/dbt-labs/dbt-autofix) and run autofix in two parts to try to fix errors. Prefer uv/uvx to install (`uv tool install dbt-autofix`) and run but fall back to pip and other methods if needed. First, run autofix to update packages (`uvx dbt-autofix packages`) which updates all package versions to the next lowest Fusion compatible version. Then, run autofix to fix deprecations (`uvx dbt-autofix deprecations`). Summarize the results of the autofix run and include how many errors were resolved. Run `dbtf parse` again to check for remaining errors and summarize with how many errors were found and a brief summary of the types of errors.
4. For remaining errors, please ONLY use the resources below to attempt to resolve them. If you can't figure out a fix from the resources below, notify the user and break out of the flow. Attempt the fixes error by error, grouping similar errors based on the error code and message. You should also summarize which error you're working on in the chat to give users context. 

   **Special handling for common unsupported features:**
   - **Python model errors**: Disable with `{{ config(enabled=false) }}` at the top of the file.
   
   Run `dbtf parse` throughout this step to check for progress towards completing the migration. Once `dbtf parse` finishes successfully with 0 errors, proceed to step 5. 
5. Run `dbtf compile` in the terminal and check if it finishes with 0 errors. If it finishes with 0 errors, you have successfully completed the migration. If there are unresolved errors, try step 4 again. Except this time, use `dbtf compile` to check for progress towards completing the migration.

### Output Template for changes_made.md

Use this structure when documenting migration changes:

```markdown
# Migration Changes Summary

## Migration Status
- **Final parse errors**: 0
- **Final compile errors**: 0

## Errors Fixed

### [Error Code]: [Brief Description]
- **File(s)**: `path/to/file.sql`
- **Error**: [Original error message]
- **Fix Applied**: [What was changed]
- **Rationale**: [Why this fix was chosen]

## Unsupported Features Encountered

| Feature | File(s) | Action Taken |
|---------|---------|--------------|
| Python models | `models/python/*.py` | Disabled static analysis |

## Notes for User
- [Any manual follow-up needed]
```

## Don't Do These Things
1. At any point, if you run into a feature that's not yet supported on Fusion (not a deprecation!), please let the user know instead of trying to resolve it. Give the user the choice of removing the feature or manually addressing it themselves.

## Handling Unsupported Features

When you encounter unsupported features in Fusion, follow this decision tree:

### For Unsupported Model Types (Python models, etc.)
- **Python models**: Python models are supported, but you need to first disable static analysis with `{{ config(static_analysis=off) }}` at the top of the file
- **Materialized views/Dynamic tables**: We support some of these, but if you get an error, you can disable with `{{ config(enabled=false) }}` at the top of the file

### For Unsupported Config Keys
- **Custom configs**: Move to `meta` block in model files (see [references/custom_configuration.md](references/custom_configuration.md))
- **Deprecated configs**: Follow [references/misspelled_config_keys.md](references/misspelled_config_keys.md) guidance

### For Dependency Issues
- If a model depends on an unsupported feature, disable the dependent model as well
- Update exposure dependencies to remove references to disabled models

## Example Error Fixes

**Example 1: Custom config key error**

Error:
```
Ignored unexpected key 'my_custom_key' in model 'orders'
```

Fix:
```sql
-- Before
{{ config(my_custom_key='value') }}

-- After
{{ config(meta={'my_custom_key': 'value'}) }}
```

**Example 2: Python model with static analysis error**

Error:
```
Static analysis failed for Python model 'my_python_model'
```

Fix: Add at top of file:
```python
{{ config(static_analysis='off') }}
```

**Example 3: Macro referencing moved config**

Error:
```
unknown method: none has no method named get
```

Fix:
```sql
-- Before
{% set val = config.get('custom_key') %}

-- After
{% set val = config.meta_get('custom_key') %}
```

## Resources

### Common problems that cannot be addressed with deterministic dbt-autofix
Use the files in the `references/` directory as the context for resolving these common problems. Each file outlines one problem and the solution you should use:

- [references/README.md](references/README.md) - Overview of manual fixes
- [references/custom_configuration.md](references/custom_configuration.md) - Custom config handling
- [references/dynamic_sql.md](references/dynamic_sql.md) - Dynamic SQL patterns
- [references/misspelled_config_keys.md](references/misspelled_config_keys.md) - Deprecated/misspelled configs

Only follow what's specified in the file. If you need more context, use the dbt docs section below as a resource.

Unsupported features and blockers to Fusion compatibility. These pages outline the supported and unsupported features of the Fusion engine: 
- https://docs.getdbt.com/docs/fusion/supported-features
- Unsupported features on Fusion: https://docs.getdbt.com/docs/fusion/supported-features#limitations
- https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-fusion
- If a model type is unsupported on Fusion (e.g. python models), you can disable it with this jinja macro `{{ config(enabled=false) }}` at the top of the file to disable the model.

Config keys that Fusion should recognize: 
You can find the latest schema file using this template: `https://public.cdn.getdbt.com/fs/schemas/fs-schema-{RESOURCE}-{VERSION}.json`
- `RESOURCE` is either `dbt-yaml-files` or `dbt-project`
- `VERSION` is the fusion version (e.g. `v2.0.0-beta.34`, but `https://public.cdn.getdbt.com/fs/latest.json` gives you the latest version)
- Example file: https://public.cdn.getdbt.com/fs/schemas/fs-schema-dbt-yaml-files-v2.0.0-beta.34.json

### dbt docs

- https://docs.getdbt.com/reference/deprecations#list-of-deprecation-warnings
- https://github.com/dbt-labs/dbt-fusion/discussions/401
- https://docs.getdbt.com/docs/fusion/supported-features
- https://docs.getdbt.com/docs/fusion/new-concepts

---

**Maintenance note**: External URLs in this skill may change as dbt documentation evolves. Verify links against current dbt documentation if they return 404 errors.
