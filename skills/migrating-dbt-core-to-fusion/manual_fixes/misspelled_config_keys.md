# Misspelled config keys

## PROBLEM

If the error message says "Ignored unexpected key", it could be that the user misspelled a config key that should be expected by the dbt authoring layer ((e.g. `materailized:` instead of `materialized:`). Here's an example JSON schema file with config keys that Fusion should recognize: https://public.cdn.getdbt.com/fs/schemas/fs-schema-dbt-yaml-files-v2.0.0-beta.34.json

## SOLUTION
You can find the latest schema file using this template: `https://public.cdn.getdbt.com/fs/schemas/fs-schema-{RESOURCE}-{VERSION}.json`
- `RESOURCE` is either `dbt-yaml-files` or `dbt-project`
- `VERSION` is the fusion version
- e.g. `v2.0.0-beta.34`, but `https://public.cdn.getdbt.com/fs/latest.json` gives you the latest version


1. Check whether an unexpected key is likely to be a misspelling of the supported config keys in the JSON schema file.
2. If it's likely to be a misspelling, correct the spelling and let users know what you did and why. Users are most likely to misspell a real config key alphabetically, so give less weight to misspelling that may have inserted a special character (e.g. `materialized` instead of `+materialized`). 
3. If it's unlikely to be a misspelling, unsupported config keys need to be moved under a `meta:` block or Fusion will fail to parse the user's project. If the unsupported config key is in `dbt_projects.yml` it needs to be moved under a `+meta:` block.
