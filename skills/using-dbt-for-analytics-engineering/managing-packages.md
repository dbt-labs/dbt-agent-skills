# Managing dbt Packages

dbt packages extend functionality with reusable macros and tests. Check what's installed before writing tests or models that depend on package functionality.

## Checking Installed Packages

```bash
# List installed packages
cat package-lock.yml
```

## Discovering Packages

Browse available packages at [hub.getdbt.com](https://hub.getdbt.com).

To discover packages programmatically:

1. **List all packages**: `https://hub.getdbt.com/api/v1/index.json`
2. **Get package details**: `https://hub.getdbt.com/api/v1/{org}/{package}.json`

For example: `https://hub.getdbt.com/api/v1/dbt-labs/dbt_utils.json`

### Version Boundaries

Use semantic versioning boundaries when installing:

| Package Version | Install Boundary | Example |
|-----------------|------------------|---------|
| 1.x or greater | Any minor version | `>=1.0.0,<2.0.0` |
| 0.x.y | Any patch version | `>=0.9.0,<0.10.0` |

## Common Packages

### Testing

- **dbt-utils**: `expression_is_true`, `recency`, `at_least_one`, `unique_combination_of_columns`, `accepted_range`
- **dbt-expectations**: `expect_column_values_to_be_between`, `expect_column_values_to_match_regex`, statistical tests
- **elementary**: Anomaly detection, schema change monitoring

### Data Loaders

If transforming raw data from these vendors, use their packages rather than writing models from scratch:

- **fivetran**: Pre-built staging and mart models for Fivetran-loaded sources
- **dlt-hub**: Models for dlt pipeline outputs
- **saras-daton**: Transformations for Daton-ingested data
- **snowplow**: Event modeling for Snowplow behavioral data

## Installing Packages

```bash
dbt deps --add-package dbt-labs/dbt_utils@">=1.0.0,<2.0.0"
```

After adding packages, run `dbt deps` to install them before use.
