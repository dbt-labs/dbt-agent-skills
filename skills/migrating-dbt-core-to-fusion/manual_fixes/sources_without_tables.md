# sources defined in YAML without tables defined

## PROBLEM
if there's a dbt YAML file that has a source defined but the source has no models defined, you'll see this error

```
warning: dbt0102: No tables defined for source 'my_source' in file 'models/staging/my_source/_my_source__sources.yml'
```

## SOLUTION

1. you can delete it if there's no config on the source
2. if there is config for the source (e.g. freshness) you have to move the config to `dbt_project.yml` under the `sources:` key. after that you can delete that source definition in YAML.
