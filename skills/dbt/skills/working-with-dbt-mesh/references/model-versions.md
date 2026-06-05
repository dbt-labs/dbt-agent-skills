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
    config:
      access: public
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
    config:
      access: public
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
| Latest version | `fct_orders_v{N}` (or `fct_orders` via `alias`) |
| Non-latest version | `fct_orders_v{N}` |
| Latest version pointer (opt-in) | `fct_orders` — view resolving to the latest version (built-in `latest_version_pointer` on v1.12+, currently **beta**; `create_latest_version_view` post-hook on ≤1.11) |

To keep consumers querying an **unsuffixed** name (e.g. `fct_orders`) that always resolves to the latest version, use a *latest version pointer* — see [Latest version pointer](#latest-version-pointer) below. **This is the recommended default for breaking-change migrations**, in both version ranges. (`config.alias` is a different tool: it pins *one specific version* to a fixed relation name, e.g. anchoring a non-latest version at the unsuffixed name during a migration. It is not a moving "latest" pointer, so it's a **manual fallback only** — reach for it only when neither pointer mechanism is available or the user explicitly declines.)

## Latest Version Pointer

A *latest version pointer* is an unsuffixed relation (e.g. `fct_orders`) that always resolves to the model's latest version (e.g. `fct_orders_v2`). It gives consumers querying outside dbt the same "latest unless pinned" behavior that `ref()` gives inside dbt: no suffix → latest; `_vN` suffix → that specific version. **How you create it depends on your dbt version.**

> ⚠️ **The pointer always tracks `latest_version` — it does NOT shield unsuffixed consumers from a breaking shape change.** Enabling the pointer re-points every unsuffixed consumer to the new shape the instant you bump `latest_version`. It protects against version *suffixes* changing, not against the *shape* changing. During a migration, **keep `latest_version` on the old version** so the pointer keeps serving the old shape; promote to the new version only after consumers have migrated. See "Versioning alone does NOT create the migration window" in SKILL.md.

**Three objects from two files:** a versioned model defined by two SQL files — `fct_orders_v1.sql` and `fct_orders_v2.sql` (latest) — produces **three** database relations once a pointer exists: `fct_orders_v1`, `fct_orders_v2`, and the pointer relation `fct_orders`.

### dbt Core v1.12+ / Fusion (recommended): built-in `latest_version_pointer`

> ⚠️ **Lifecycle: `latest_version_pointer` is currently `beta` in dbt's documentation.** It is the recommended mechanism on v1.12+, but confirm it's available and behaving as expected for the user's exact version before relying on it in production.

On v1.12+ (and the Fusion engine), use the built-in `latest_version_pointer` config — there is no reason to hand-roll a post-hook. After the latest version (the one whose `v` matches `latest_version:`) materializes successfully, dbt automatically creates the pointer view. The feature is **opt-in** (default off).

> The config is named "pointer" rather than "view" because future adapter-specific optimizations may use a different relation type. In v1.12 the implementation is always a view.

Enable per model:

```yaml
models:
  - name: fct_orders
    latest_version: 2
    config:
      latest_version_pointer:
        enabled: true
    versions:
      - v: 1
      - v: 2
```

Enable project-wide one of two ways (use whichever fits — they are alternatives, not both required):

```yaml
# dbt_project.yml — Option A: turn it on for the whole project
flags:
  latest_version_pointer_enabled_by_default: true
```

```yaml
# dbt_project.yml — Option B: turn it on for a directory of models (overridable per model)
models:
  my_project:
    marts:
      +latest_version_pointer:
        enabled: true
```

**Customize the pointer name.** By default the pointer uses the unsuffixed model name (`fct_orders`). Either set `alias` under `latest_version_pointer` for a single model, or override the dispatched `generate_latest_version_pointer_alias` macro for a project-wide convention (the `alias` sub-field is passed in as `custom_alias_name`):

```yaml
models:
  - name: fct_orders
    # ... latest_version: and versions: omitted for brevity (see the full example above)
    config:
      latest_version_pointer:
        enabled: true
        alias: fct_orders_current
```

```sql
-- macros/generate_latest_version_pointer_alias.sql
-- Override example. The default implementation returns node.name (the unsuffixed name);
-- this version appends a "_latest" suffix instead.
{% macro generate_latest_version_pointer_alias(custom_alias_name=none, node=none) %}
    {%- if custom_alias_name -%}
        {{ custom_alias_name | trim }}
    {%- else -%}
        {{ node.name ~ "_latest" }}
    {%- endif -%}
{% endmacro %}
```

The pointer view is created **only** when the latest version materializes successfully. If the latest version's own `alias` already equals the pointer name, dbt raises a clear collision error — pick a distinct pointer `alias`, or rely on the default unsuffixed name.

### dbt Core ≤ 1.11: `create_latest_version_view` post-hook (dbt's recommended pattern)

On ≤1.11 there is no built-in pointer. **dbt's own docs recommend this pattern** ("Configuring database location with `alias`" in the [model-versions docs](https://docs.getdbt.com/docs/mesh/govern/model-versions?version=1.11&name=Core)): create the canonical-name relation yourself with a custom macro run as a post-hook. Prefer this over `config.alias` — it gives consumers the same "no suffix → latest, `_vN` → pinned" behavior outside dbt that `ref()` gives inside dbt. The macro is a no-op except on the latest version, where it creates (or replaces) a view at the unsuffixed name pointing to the current relation. Note this is wired as a **project-wide** `post-hook`, so it runs (as a no-op) on every model, not just the versioned one:

```sql
-- macros/create_latest_version_view.sql
{% macro create_latest_version_view() %}
    -- applied as a project-wide post-hook, this macro runs on every model, but the CREATE VIEW
    -- below executes only for the latest version of a versioned model; otherwise it's a no-op
    {% if model.get('version') and model.get('version') == model.get('latest_version') %}
        {% set new_relation = this.incorporate(path={"identifier": model['name']}) %}
        {% set existing_relation = load_relation(new_relation) %}
        {% if existing_relation and not existing_relation.is_view %}
            {{ drop_relation_if_exists(existing_relation) }}
        {% endif %}
        {% set create_view_sql -%}
            -- this syntax may vary by data platform
            create or replace view {{ new_relation }} as select * from {{ this }}
        {%- endset %}
        {% do log("Creating view " ~ new_relation ~ " pointing to " ~ this, info = true) if execute %}
        {{ return(create_view_sql) }}
    {% else %}
        -- no-op
        select 1 as id
    {% endif %}
{% endmacro %}
```

```yaml
# dbt_project.yml
models:
  +post-hook:
    - "{{ create_latest_version_view() }}"
```

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

**Introducing the new version and promoting it to `latest_version` are two separate deploys, separated by the migration window — never the same change.** The new version always starts as non-latest.

1. **Add the new version** with `columns` changes but keep `latest_version` pointing to the old version — **do NOT make the new version latest yet.** This is what keeps the unsuffixed relation (and the pointer view) serving the old shape so external consumers don't break.
   - **Ensure a canonical-name pointer exists** (the recommended default): on **≥1.12** enable `latest_version_pointer`; on **≤1.11** wire the `create_latest_version_view` post-hook. With `latest_version` still on the old version, the pointer serves the old shape now and auto-re-points when you bump it in step 6 — no relation rename. Use `config.alias` on the old version only as a fallback (manual rewiring required at promotion).
2. **Create the SQL file** for the new version
3. **Deploy** — both versions now exist in the warehouse
4. **Verify the migration window is open** — the consumer's relation must still return the old columns:
   ```bash
   dbt show --inline "select <old_col> from {{ target.schema }}.<unsuffixed_relation>"
   ```
   A `column does not exist` error means `latest_version` was promoted too early and the consumer is already broken.
5. **Notify consumers** to migrate their `ref()` calls to the new version (or pin to the old one)
6. **Bump `latest_version`** to the new version once consumers have migrated — this is a breaking release for any unsuffixed consumer that hasn't migrated, so confirm migration first
7. **Set deprecation date** on the old version (optional):
   ```yaml
   versions:
     - v: 1
       deprecation_date: 2025-06-01 00:00:00.00+00:00
   ```
8. **Remove the old version** after the deprecation window has passed

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
| Leaving no pointer to the latest version | Consumers querying the unsuffixed name break when you bump `latest_version`. ≥1.12: enable `latest_version_pointer` (currently **beta**); ≤1.11: use the `create_latest_version_view` post-hook (see [Latest Version Pointer](#latest-version-pointer)). `config.alias` pins one version to a name — it is not a moving pointer. |
| Using `config.alias` as the default canonical-name mechanism | It collapses to 2 relations and forces manual un-aliasing + rewiring when you bump `latest_version`. Default to the version-appropriate pointer (`latest_version_pointer` ≥1.12, `create_latest_version_view` post-hook ≤1.11); use `config.alias` only as a fallback. |
| Not creating a SQL file for the new version | Each version needs its own SQL file (or a `defined_in` reference) |
| Removing old version too quickly | Set a deprecation date and give consumers a migration window |
