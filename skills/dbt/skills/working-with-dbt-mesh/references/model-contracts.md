# Model Contracts

Model contracts guarantee the shape of a model by enforcing column names, data types, and constraints at build time. If the model's SQL output doesn't match the contract, the build fails — the model is never materialized.

## When to Use Contracts

- The model is `access: public` and consumed by other teams or projects
- The model feeds an exposure (dashboard, ML pipeline, reverse ETL)
- External consumers (other dbt projects, BI dashboards, reverse ETL) query the table directly and would break from column renames or removals
- You need build-time schema guarantees, not just post-build test assertions

## When NOT to Use Contracts

Do NOT add a contract — and advise against it even if the user asks — when:

- **Staging models** (`stg_*`): Internal implementation details, not consumer-facing APIs. Suggest data tests instead.
- **Models still under active development**: If the user says they are iterating on columns or just created the model, advise waiting until the schema stabilizes.
- **No external consumers**: In a single-project setup with no cross-project refs, no BI tools depending on the schema, and no exposures, contracts add maintenance overhead without benefit. Ask about consumers first.
- **Dynamic/pivot columns**: Models using `pivot()`, `unpivot()`, or dynamically generated columns are poor candidates — the column list changes with the data, so the contract will break whenever the dynamic values change.
- **Ephemeral models**: Contracts are not supported on ephemeral materializations.

## Basic Configuration

**Important:** `contract` is a config property and must be nested under `config:` in YAML property files. Placing it as a top-level model property breaks the Fusion engine.

```yaml
models:
  - name: fct_orders
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: int
        constraints:
          - type: not_null
      - name: customer_id
        data_type: int
      - name: order_total
        data_type: numeric(38, 6)
      - name: ordered_at
        data_type: timestamp_ntz
```

**Every column must be declared.** Unlike regular YAML documentation where you can list a subset of columns, a contract requires that all columns in the model's output be listed with their `data_type`.

## Supported Materializations

Contracts work with:
- `table`
- `view` (names and types enforced, but constraints are not)
- `incremental` (requires `on_schema_change: append_new_columns` or `on_schema_change: fail`)

Contracts do **NOT** work with:
- `ephemeral` models
- `materialized_view`
- Python models

## Constraints

Constraints provide pre-build data quality enforcement. They differ from tests:

| Aspect | Constraints | Tests |
|--------|-------------|-------|
| Timing | Build-time (pre-flight) | Post-build (post-flight) |
| Effect on failure | Model is not materialized | Model exists but test fails |
| Scope | Shape and nullability | Data quality and business rules |

### Available Constraint Types

```yaml
columns:
  - name: order_id
    data_type: int
    constraints:
      - type: not_null
      - type: unique
      - type: primary_key
      - type: foreign_key
        expression: "other_table (id)"
      - type: check
        expression: "order_total >= 0"
```

**Platform support varies.** Not all warehouses enforce all constraint types:

| Constraint | PostgreSQL | Snowflake | BigQuery | Redshift | Databricks |
|------------|-----------|-----------|----------|----------|------------|
| `not_null` | Enforced | Enforced | Enforced | Enforced | Enforced |
| `unique` | Enforced | Not enforced | Not enforced | Not enforced | Not enforced |
| `primary_key` | Enforced | Not enforced | Not enforced | Not enforced | Not enforced |
| `check` | Enforced | Not enforced | Not supported | Not enforced | Not supported |

Even when not enforced by the warehouse, constraints serve as documentation and are surfaced in dbt's metadata.

## Data Type Aliasing

dbt automatically aliases generic types to platform-specific types. For example, `string` becomes:
- `text` on PostgreSQL
- `varchar` on Snowflake and Redshift
- `string` on BigQuery and Databricks

To disable aliasing and use platform-specific types directly:

```yaml
models:
  - name: my_model
    config:
      contract:
        enforced: true
        alias_types: false
```

**Tip:** When specifying numeric types, always include precision and scale (e.g. `numeric(38, 6)`) to avoid implicit coercion issues.

## Breaking Changes

dbt flags these as contract-breaking changes:
- Removing an existing column
- Changing a column's data type
- Removing or modifying a constraint
- Removing a contracted model entirely (dbt v1.9+)

When a breaking change is needed, create a **new model version** instead of modifying the contract in place. See [model-versions.md](model-versions.md).

## Incremental Models with Contracts

When using contracts with incremental models, you **must** set `on_schema_change`:

```yaml
models:
  - name: fct_events
    config:
      materialized: incremental
      on_schema_change: append_new_columns  # or 'fail'
      contract:
        enforced: true
```

Without `on_schema_change`, schema drift between the YAML contract and the database table can cause silent inconsistencies.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Listing only some columns | Declare every column — contracts require completeness |
| Omitting `data_type` | Every column must have a `data_type` |
| Using contracts on ephemeral models | Switch to `table`, `view`, or `incremental` |
| Assuming constraints are enforced everywhere | Check your warehouse's constraint enforcement — many are informational only |
| Changing contracted columns without versioning | Create a new model version for breaking changes |
| Placing `contract` as a top-level model property in YAML | Nest under `config:` — top-level placement breaks Fusion |
| Adding a contract to a staging model | Staging models are internal — use data tests instead |
| Adding a contract to a model with dynamic/pivot columns | The column list changes with data, breaking the contract |
| Adding a contract without asking about external consumers | Ask who depends on this model's schema before adding a contract |
