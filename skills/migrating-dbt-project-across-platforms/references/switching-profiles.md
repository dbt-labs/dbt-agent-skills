# Switching Profiles to the Target Platform

## PROBLEM

After generating unit tests on the source platform, the dbt project needs to be pointed at the target platform. This involves updating the profile configuration, source definitions, and removing any platform-specific configuration keys.

## SOLUTION

### Step 1: Configure the target profile in profiles.yml

Add a profile for the target platform in `~/.dbt/profiles.yml`. Examples:

**Snowflake profile**:
```yaml
snowflake_profile:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: TRANSFORMER
      database: ANALYTICS
      warehouse: COMPUTE_WH
      schema: DEV
      threads: 4
```

**Databricks profile**:
```yaml
databricks_profile:
  target: dev
  outputs:
    dev:
      type: databricks
      catalog: main
      schema: dev
      host: "{{ env_var('DATABRICKS_HOST') }}"
      http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
      token: "{{ env_var('DATABRICKS_TOKEN') }}"
      threads: 4
```

**BigQuery profile**:
```yaml
bigquery_profile:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: my-gcp-project
      dataset: dev
      threads: 4
      location: US
```

### Step 2: Update dbt_project.yml

Change the `profile` key in `dbt_project.yml` to reference the target profile:

```yaml
# Before
profile: snowflake_demo

# After
profile: databricks_demo
```

### Step 3: Update source definitions

Source definitions in `_sources.yml` or `tpch_sources.yml` may reference platform-specific database and schema names. Update them to match the target platform:

```yaml
# Snowflake source
sources:
  - name: tpch
    database: snowflake_sample_data
    schema: tpch_sf1
    tables:
      - name: orders
      - name: lineitem

# Databricks equivalent (using catalog)
sources:
  - name: tpch
    database: samples    # catalog name in Databricks
    schema: tpch
    tables:
      - name: orders
      - name: lineitem
```

**Key differences by platform**:
- **Snowflake**: Uses `database.schema` hierarchy
- **Databricks**: Uses `catalog.schema` hierarchy (Unity Catalog) — the `database` key in dbt maps to the catalog
- **BigQuery**: Uses `project.dataset` hierarchy — the `database` key maps to the GCP project

### Step 4: Remove platform-specific configurations

Search for and update platform-specific config keys in `dbt_project.yml` and model files:

**Snowflake-specific configs to remove/update**:
- `+snowflake_warehouse` — Remove or replace with target equivalent
- `+query_tag` — Snowflake-specific, remove
- `+copy_grants` — Snowflake-specific, remove
- `cluster_by` — Snowflake cluster keys need conversion to target platform equivalent

**Databricks-specific configs to remove/update**:
- `+file_format: delta` — Remove (delta is default on Databricks, not applicable elsewhere)
- `+location_root` — Databricks-specific, remove
- `tblproperties` — Databricks-specific, remove or convert

**General config considerations**:
- `+materialized` values are generally consistent across platforms
- `+tags` are platform-agnostic and can be left as-is
- `+persist_docs` behavior may vary — check target platform support

### Step 5: Verify connectivity

Run `dbtf debug` to confirm the target platform connection works:

```bash
dbtf debug
```

## CHALLENGES

### Source data doesn't exist on target platform

If the source data (e.g., `snowflake_sample_data.tpch_sf1`) doesn't exist on the target platform:
- Check if equivalent sample data is available (e.g., Databricks has `samples.tpch` in Unity Catalog)
- If not, consider using dbt seeds to load a subset of the data
- Update source definitions to point to wherever the data lives on the target

### Accessing sample TPCH data across platforms

TPCH sample data is commonly available:
- **Snowflake**: `snowflake_sample_data.tpch_sf1`
- **Databricks**: `samples.tpch` (Unity Catalog)
- **BigQuery**: Available as public dataset `bigquery-public-data.tpch_sf1`

Column names and types are generally consistent across platforms for TPCH data, but verify with a quick query.

### Multiple environments

If the project uses multiple targets (dev, staging, prod), you only need to configure one target for migration testing. Use `dev` or a dedicated `migration` target. Production configuration can be finalized after the migration is validated.
