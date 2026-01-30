---
name: migrating-dbt-core-to-fusion
description: Use when migrating a dbt project from dbt Core to run on the Fusion engine.
compatibility: Designed for dbt Core v1.10+
metadata:
  author: dbt-labs
---

## Goals

1. Make a pre-existing dbt project compatible with dbt Fusion, so it can parse and compile successfully on the Fusion engine.  
2. Preserve existing functionality as much as possible.
3. Flag when the dbt project is using functionality that's not yet supported in Fusion, and ask users so they can choose whether to wait for feature support or remove use of unsupported features. 


## Migrating to the new authoring layer and the dbt Fusion engine

if a user says "migrate my dbt project to the new authoring layer" or "make my dbt project compatible with the Fusion engine" do the following steps and the migration is only successfully completed once `dbtf compile` finishes with 0 errors. Create a changes_made.md file documenting and summarizing all of the code changes made in the user's dbt project, including what the error was, the fix applied, and a summary of why the fix was chosen.

Before you begin, please read and understand the resources section below. You should strictly use the resources below to update the project.

1. Run `dbtf debug` in the terminal to check their data platform connections. Proceed to step 2 if there are no errors. If there are errors, please summarize the error succinctly so the user knows how to debug on their own.
2. Run `dbtf parse --show-all-deprecations` in the terminal to check for compatibility errors in their current project. Summarize the log output by specifying how many errors were found and group the errors in a way that's easily understandable.
3. Install [dbt-autofix](https://github.com/dbt-labs/dbt-autofix) and run autofix to try to fix errors. Prefer uv/uvx to install (`uv tool install dbt-autofix`) and run the package (`uvx dbt-autofix deprecations`), but fall back to pip and other methods if needed. Summarize the results of the autofix run and include how many errors were resolved. Run `dbtf parse` again to check for remaining errors and summarize with how many errors were found and a brief summary of the types of errors.
4. For remaining errors, please ONLY use the resources below to attempt to resolve them. If you can't figure out a fix from the resources below, notify the user and break out of the flow. Attempt the fixes error by error, grouping similar errors based on the error code and message. You should also summarize which error you're working on in the chat to give users context. 

   **Special handling for common unsupported features:**
   - **Python model errors**: Disable with `{{ config(enabled=false) }}` at the top of the file.
   
   Run `dbtf parse` throughout this step to check for progress towards completing the migration. Once `dbtf parse` finishes successfully with 0 errors, proceed to step 5. 
5. Run `dbtf compile` in the terminal and check if it finishes with 0 errors. If it finishes with 0 errors, you have successfully completed the migration. If there are unresolved errors, try step 4 again. Except this time, use `dbtf compile` to check for progress towards completing the migration.

## Don't Do These Things
1. At any point, if you run into a feature that's not yet supported on Fusion (not a deprecation!), please let the user know instead of trying to resolve it. Give the user the choice of removing the feature or manually addressing it themselves.

## Handling Unsupported Features

When you encounter unsupported features in Fusion, follow this decision tree:

### For Unsupported Model Types (Python models, etc.)
- **Python models**: Disable with `{{ config(enabled=false) }}` at the top of the file
- **Materialized views/Dynamic tables**: Disable with `{{ config(enabled=false) }}` at the top of the file

### For Unsupported Config Keys
- **Custom configs**: Move to `meta` block in model files (see /manual_fixes/custom_configuration.md)
- **Deprecated configs**: Follow /manual_fixes/misspelled_config_keys.md guidance

### For Dependency Issues
- If a model depends on an unsupported feature, disable the dependent model as well
- Update exposure dependencies to remove references to disabled models

## Resources

### Common problems that cannot be addressed with deterministic dbt-autofix
Use the files in the `/manual_fixes/` directory as the context for resolving these common problems:
- Each file outlines one problem and the solution you should use.
- Only follow what's specified in the file. If you need more context, use the dbt docs section below as a resource.

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

https://docs.getdbt.com/reference/deprecations#list-of-deprecation-warnings
https://github.com/dbt-labs/dbt-fusion/discussions/401
https://docs.getdbt.com/docs/fusion/supported-features
https://docs.getdbt.com/docs/fusion/new-concepts