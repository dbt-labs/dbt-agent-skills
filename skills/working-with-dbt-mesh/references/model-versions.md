# Model Versions

Model versioning lets you introduce breaking changes to a contracted model while giving downstream consumers a migration window. Multiple versions coexist in the same codebase and data environment simultaneously — similar to API versioning.

## When to Version

Version a model **only** for breaking changes to a contract:
- Removing a column
- Renaming a column
- Changing a column's data type
- Changing nullability constraints

Do **NOT** version for:
- Adding new columns (non-breaking)
- Bug fixes (fix in place)
- Performance optimizations (transparent to consumers)
- Preemptive "just in case" versioning

## Basic Configuration

```yaml
models:
  - name: fct_orders
    latest_version: 1
    access: public
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: varchar
      - name: customer_id
        data_type: varchar
      - name: order_total
        data_type: number
      - name: tax_paid
        data_type: number
      - name: ordered_at
        data_type: timestamp_ntz
    versions:
      - v: 1
        config:
          alias: fct_orders  # Without this, resolves to fct_orders_v1
```

## Adding a New Version with Breaking Changes

When you need to rename `order_total` to `order_amount` and change a data type:

```yaml
models:
  - name: fct_orders
    latest_version: 1  # Keep pointing to v1 until consumers migrate
    access: public
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: varchar
      - name: customer_id
        data_type: varchar
      - name: order_total
        data_type: number
      - name: tax_paid
        data_type: number
      - name: ordered_at
        data_type: timestamp_ntz
    versions:
      - v: 1
        config:
          alias: fct_orders
      - v: 2
        columns:
          - include: all
            exclude: [order_total]  # Remove old column name
          - name: order_amount      # Add new column name
            data_type: number
          - name: ordered_at        # Change data type
            data_type: date
```

### Version Column Syntax

Within a version's `columns` key:

- **`include: all`** — inherit all columns from the parent model definition
- **`exclude: [col1, col2]`** — remove specific columns from the inherited set
- **New column entries** — add or override columns for this version

## SQL Files for Versions

Each version needs its own SQL file:

| Version | SQL File |
|---------|----------|
| v1 (latest) | `fct_orders.sql` or `fct_orders_v1.sql` |
| v2 (prerelease) | `fct_orders_v2.sql` |
| Old version | `fct_orders_v1.sql` |

Use `defined_in` to specify a custom file name:

```yaml
versions:
  - v: 1
    defined_in: fct_orders_v1  # Points to fct_orders_v1.sql
    config:
      alias: fct_orders
  - v: 2
```

## Database Naming

| Version State | Default Relation Name |
|---------------|----------------------|
| Latest version | `fct_orders` (via `alias`) or `fct_orders_v{N}` |
| Non-latest version | `fct_orders_v{N}` |

Use `config.alias` on the latest version to maintain the original table name for backward compatibility.

## Referencing Versioned Models

```sql
-- Reference the latest version (resolves to latest_version)
select * from {{ ref('fct_orders') }}

-- Reference a specific version explicitly
select * from {{ ref('fct_orders', v=2) }}

-- Cross-project reference with version
select * from {{ ref('upstream_project', 'fct_orders', v=1) }}
```

Unpinned `ref()` calls resolve to `latest_version`. When you bump `latest_version`, all unpinned refs automatically point to the new version.

## Running Versioned Models

```bash
# Run all versions of a model
dbt run --select fct_orders

# Run a specific version
dbt run --select fct_orders_v2

# Run only the latest version
dbt run -s fct_orders,version:latest
```

## Migration Workflow

1. **Add the new version** with `columns` changes but keep `latest_version` pointing to the old version
2. **Create the SQL file** for the new version
3. **Deploy** — both versions now exist in the warehouse
4. **Notify consumers** to migrate their `ref()` calls to the new version (or pin to the old one)
5. **Bump `latest_version`** to the new version once consumers have migrated
6. **Set deprecation date** on the old version (optional):
   ```yaml
   versions:
     - v: 1
       deprecation_date: 2025-06-01 00:00:00.00+00:00
   ```
7. **Remove the old version** after the deprecation window has passed

## Unit Tests and Versions

By default, unit tests run against **all versions** of a model. To target a specific version:

```yaml
unit_tests:
  - name: test_order_amount_calculation
    model: fct_orders
    versions:
      include:
        - 2  # Only test v2
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Versioning for additive changes | New columns are non-breaking — just add them to the contract |
| Bumping `latest_version` before consumers migrate | Keep `latest_version` on the old version until migration is complete |
| Forgetting `config.alias` on latest version | Without alias, the relation name includes the version suffix |
| Not creating a SQL file for the new version | Each version needs its own SQL file (or a `defined_in` reference) |
| Removing old version too quickly | Set a deprecation date and give consumers a migration window |
