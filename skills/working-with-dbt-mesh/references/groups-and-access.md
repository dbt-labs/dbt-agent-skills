# Groups and Access Modifiers

Groups and access modifiers work together to organize models by team ownership and control which models can reference each other.

## Groups

Groups represent domains of resources owned by a specific team. They make ownership explicit — when something breaks, you know who to contact.

### Defining Groups

Groups can be defined in a standalone YAML file or alongside model definitions:

```yaml
# models/_groups.yml (or any .yml file in your models directory)
groups:
  - name: finance
    owner:
      name: Firstname Lastname
      email: finance@jaffleshop.com
      slack: finance-data
      github: finance-data-team
  - name: product
    owner:
      email: product@jaffleshop.com
      github: product-data-team
```

**Owner requirements:** At least `name` or `email` is required. Other properties (`slack`, `github`) are optional.

### Assigning Models to Groups

Three ways to assign a model to a group:

**1. In model YAML (recommended for individual models):**

```yaml
models:
  - name: fct_orders
    config:
      group: finance
```

**2. In `dbt_project.yml` (recommended for directory-level assignment):**

```yaml
# dbt_project.yml
models:
  my_project:
    marts:
      finance:
        +group: finance
      marketing:
        +group: marketing
```

**3. In SQL config block:**

```sql
-- models/marts/finance/fct_orders.sql
{{ config(group='finance') }}

select ...
```

### What Can Be Grouped

Groups apply to: models, seeds, snapshots, tests, analyses, metrics, semantic models, and saved queries.

## Access Modifiers

Access modifiers control which models can `ref` yours:

| Access | Who Can Reference | Use Case |
|--------|-------------------|----------|
| **`private`** | Same group only | Internal implementation details, rapidly changing models |
| **`protected`** | Same project (or installed as a package) | Standard intra-project models (this is the default) |
| **`public`** | Any group, package, or project | Stable APIs intended for cross-team or cross-project consumption |

### Configuring Access

```yaml
models:
  - name: fct_orders
    config:
      group: finance
      access: public
```

Or in `dbt_project.yml` at the directory level:

```yaml
models:
  my_project:
    staging:
      +access: private
      +group: platform
    marts:
      +access: protected
```

Or in SQL:

```sql
{{ config(access='public', group='finance') }}
```

### Access Rules

- **Default access is `protected`** — all models in a project can reference each other regardless of group
- **`private` models** trigger a `DbtReferenceError` if referenced from outside their group
- **`public` models** are the only models visible to other projects via cross-project `ref()`
- **Ephemeral models cannot be `public`** — attempting this causes a parsing error

### Access and Contracts

Access and contracts are complementary:

| Access Level | Contract Recommended? | Why |
|-------------|----------------------|-----|
| `public` | Yes | Consumers outside your project depend on schema stability |
| `protected` | Optional | Useful for high-criticality intra-project models |
| `private` | No | Internal models change frequently; contracts add friction |

## Practical Example: Multi-Team Project

```yaml
# models/_groups.yml
groups:
  - name: finance
    owner:
      email: finance-data@company.com
  - name: marketing
    owner:
      email: marketing-data@company.com

# models/marts/finance/_finance_models.yml
models:
  - name: fct_revenue
    config:
      group: finance
      access: public       # Other projects can ref this
      contract:
        enforced: true
    columns:
      - name: revenue_id
        data_type: varchar
      - name: amount
        data_type: numeric(38, 2)
      - name: recorded_at
        data_type: timestamp_ntz

  - name: int_revenue_daily
    config:
      group: finance
      access: private       # Only finance group can ref this

# models/marts/marketing/_marketing_models.yml
models:
  - name: fct_campaigns
    config:
      group: marketing
      access: protected     # Same project can ref, other projects cannot
```

In this setup:
- `fct_revenue` is available to anyone (public, contracted)
- `int_revenue_daily` is only available within the finance group
- `fct_campaigns` is available to all models in the same project but not to other projects
- If `fct_campaigns` tries to `ref('int_revenue_daily')`, dbt raises a `DbtReferenceError`

## Best Practices

1. **Start with `private` for new models** and widen access only when there's a real consumer
2. **Always pair `public` with a contract** — a public model without a contract is a liability
3. **Use directory-level group assignment** in `dbt_project.yml` when your directory structure mirrors team ownership
4. **Keep groups aligned with team structure** — a group should map to a real team that can respond to issues
5. **Don't create groups for one model** — groups represent team boundaries, not individual model boundaries

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Not assigning a group to private models | `private` access requires a `group` — dbt errors without one |
| Making everything `public` | Only public-ify models that are intentional cross-team APIs |
| Creating groups that don't map to real teams | Groups need an owner who can respond when things break |
| Relying on `protected` (default) when `private` is more appropriate | Be intentional — `protected` is permissive within the project |
| Expecting `access` to control database permissions | Access modifiers are a dbt concept — manage database permissions separately |
