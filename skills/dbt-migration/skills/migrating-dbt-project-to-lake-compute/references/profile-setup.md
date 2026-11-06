# Setting Up the Profile for Lake Compute

Switched models build on Lake Compute through a `lakecompute` output in the
same profile target as the Snowflake one. The target becomes a list of
outputs, with Snowflake as the default.

## Adding the output

Add the output yourself: edit the profile the project uses (`profiles.yml`
in `DBT_PROFILES_DIR`, the project, or `~/.dbt`), with the user's yes. Read
only its structure (target and output names, types): don't print credential
values. Keep the existing Snowflake output (and any other outputs), make the
target a list, and add a `lakecompute` output whose token comes from an
environment variable, never written into the file:

```yaml
my_project:
  target: dev
  outputs:
    dev:
      - name: snowflake
        default: true
        type: snowflake
        # ... the existing Snowflake settings
      - name: lakecompute
        type: lakecompute
        method: fivetran
        fivetran_credential: "{{ env_var('DBT_LAKE_COMPUTE_TOKEN', '') }}"
```

Then ask the user, in words, to put their Lake Compute token in
`DBT_LAKE_COMPUTE_TOKEN` where dbt runs (their shell profile, or the job's
environment), and to tell you when it's there. Never ask them to paste it to
you.

Until the output exists, the report says "Switched models build on Lake
Compute once you add a lakecompute output", and building switched models
fails.

## The Snowflake login

With both outputs, Lake Compute gets its access to Snowflake's catalog from
the Snowflake output's login. It must have an explicit `method`: `sso`
(`authenticator: externalbrowser`), `keypair`, `self_signed_jwt` or
`workload_identity`. A password or a Snowflake programmatic access token
login fails the build with "LakeCompute credential minting requires an
explicit Snowflake 'method'". Logins other than `keypair` with a JWT also
need Lake Compute's IP addresses in the account's network policy. The steps
are in [dbt's Lake Compute onboarding guide](https://docs.getdbt.com/docs/lake-compute/compute-onboarding?version=2#supported-authentication-methods).

## Linking the catalogs

A model staying on Snowflake can read a switched one when the catalogs are
linked: Lake Compute writes the table to its own Iceberg catalog, then
propagates it to Snowflake, where readers `ref` it as before. `--validate`
reads the rebuilt tables the same way. Linking needs, on Snowflake (an
`ACCOUNTADMIN` sets it up, so tell the user what to ask their admin for):

1. A catalog integration for Lake Compute's catalog. Fivetran's UI generates
   its SQL (Catalog integration > Snowflake).
2. `grant usage on integration <name> to role <role>` for each role dbt runs
   as.

`dbt debug` checks it: it writes a table on Lake Compute and looks for it on
Snowflake. Without the link, readers on Snowflake fail (`Database ... does not
exist or not authorized`), and so does `--validate`. Point the user to
[creating the catalog integration](https://docs.getdbt.com/docs/lake-compute/compute-onboarding?version=2#create-a-snowflake-catalog-integration-for-mdls).

## Build gates

While Lake Compute features are experimental in a dbt release, a build of
switched models needs environment variables turned on. The switch prints the
exact build command, with the variables this dbt needs: use it as printed.
Today those can include:

- `DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true`: models that pick their adapter.
- `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`: only on dbt releases where lakecompute
  is still an experimental adapter; later ones don't need it.

Once models are switched, every dbt command that compiles the project needs
`DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true`: `dbt build`, `run`, `compile`,
`show`, `test`. Set it on each one you run. Without it,
dbt stops with "Selecting a node's adapter with `adapter: lakecompute` is
experimental". That includes the check:
`DBT_ENGINE_EXPERIMENTAL_MULTI_ADAPTER=true dbt init lakecompute --json --quiet --dry-run ...`.

## Never

- Don't write tokens, passwords or keys into `profiles.yml`, or into any file.
  Use `env_var()`.
- Don't print the values of credential environment variables.
