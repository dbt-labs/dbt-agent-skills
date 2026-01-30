# Discovering Data with dbt show

Use `dbt show` to interactively explore raw data, understand table structures, and document findings for downstream model development.

## When to Use

- Onboarding to a new dbt project with unfamiliar source data
- Investigating data quality issues reported by stakeholders
- Planning new models and need to understand source grain/structure
- Mapping relationships between tables before building joins

## The Iron Rule

**Complete all 6 steps for every table you will build models on.**

## Rationalizations That Mean STOP

| You're Thinking... | Reality |
|-------------------|---------|
| "I don't have time for full discovery" | You don't have time for wrong models. |
| "It's just a quick stakeholder briefing" | Quick briefings become "can you build a model from this?" You need to do full discovery before building anything. |
| "I'll do proper discovery later" | You won't. Document now or create technical debt someone else inherits. |
| "This is technical debt I'm accepting" | You're not accepting it - you're passing it to your future self or teammates. |
| "47 tables is too many for full methodology" | Then prioritize which tables you'll actually use and do full discovery on those. Don't half-discover everything. |
| "I'll just do the critical tables thoroughly" | ALL tables you build on are critical. If it's not worth full discovery, don't build models on it yet. |
| "Standard patterns, I know this data" | You know the pattern. This instance's data might vary. Verify. |

## Red Flags - You're About to Skip Steps

Stop if you catch yourself:
- Running only `SELECT *` without grain analysis
- Saying "the join worked" without checking orphan counts
- Noting "some nulls" without quantifying null rates
- Planning to "document later"
- Feeling time pressure and reaching for shortcuts
- Treating a large table count as permission to be less thorough

**All of these mean: slow down, follow all 6 steps.**

## Large Scope Strategy

When facing many tables (20+), the answer is NOT abbreviated discovery. The answer is:

1. **Scope ruthlessly first** - Which tables will you actually build models on? Only those need discovery now.
2. **Full methodology on scoped tables** - Every table in scope gets all 6 steps. No exceptions.
3. **Explicit deferral for out-of-scope** - Document which tables you're NOT discovering and why. "Not needed for current project" is valid. "Too many tables" is not.

**Wrong approach:** "I'll do light discovery on all 47 tables"
**Right approach:** "I'll do full discovery on the 8 tables needed for this project"

## Core Method: Iterative Discovery

### Step 1: Inventory relevant objects

#### Sources

When discovering new raw data, list all tables from the new source. E.g. listing all `ecom` source tables:

```bash
# quoting is critical when selecting sources
dbt ls --select "source:ecom.*" --output json
```

Review the existing YAML file at `original_file_path` to understand what's already documented.

#### Models

When previewing existing models, use standard node selection syntax:

```bash
# quoting is critical when selecting multiple nodes
dbt ls --select "my_first_model my_second_model" --output json
```

Review existing YAML files (normally colocated with the model's `original_file_path`) to understand what's already documented.

### Step 2: Sample Raw Data

Preview rows from each source table:

```bash
dbt show --inline "SELECT * FROM {{ source('source_name', 'table_name') }}" --limit 50 --output json
```

**Document immediately:**

- Column names and warehouse-native data types
- Which columns appear to be identifiers vs attributes
- Obvious nulls, low-cardinality values, and values which are not obvious from their column name

### Run standard EDA

Continue to use `dbt show` to run standard exploratory data analysis queries such as:

- Identify the grain of the table
- Check for duplicate/null primary keys
- Validate data ranges make sense (e.g. event timestamps are in the past)
- Profile key columns
- Identify potential foreign key relationships
- Inconsistent data types in a column

## Documenting Findings

Create a discovery report that other agents can consume. Place in a `data_discovery.md` file alongside the SQL/YAML files. Do not use Jinja in these discovery files to avoid them being mistaken for doc blocks.

### Discovery Report Template

```markdown
## Source: {source_name}.{table_name}

### Overview
- **Row count**: X
- **Grain**: One row per [entity] per [time period]
- **Primary key**: column_name (verified unique)

### Column Analysis
| Column | Type | Nulls | Notes |
|--------|------|-------|-------|
| id | integer | 0% | Primary key |
| status | string | 2% | Values: active, inactive, pending |
| created_at | timestamp | 0% | UTC timezone |

### Data Quality Issues
- [ ] `status` has 15 rows with value "unknown" - clarify with stakeholder
- [ ] `amount` has negative values - confirm if valid or error

### Relationships
- `user_id` → `users.id` (5 orphan records found)
- `product_id` → `products.id` (clean join)

### Recommended Staging Transformations
1. Filter out `status = 'unknown'` rows or map to valid value
2. Cast `created_at` to consistent timezone
3. Add surrogate key if natural key unreliable
```

## Previewing Data Efficiently

When using `dbt show --inline` to preview data, push `LIMIT` clauses as early as possible in CTEs to minimize data scanning. Never add a `LIMIT` at the end of the query - `dbt show` always adds an additional limit and you will cause a syntax error.

```sql
-- ✅ GOOD: Limit pushed early, minimizes scanning
with orders as (
    select * from {{ source('ecom', 'orders') }} limit 100
),
customers as (
    select * from {{ source('ecom', 'customers') }} limit 100
)
select ... from orders join customers ...

-- ❌ BAD: Full table scan before limit applied
with orders as (
    select * from {{ source('ecom', 'orders') }}
),
customers as (
    select * from {{ source('ecom', 'customers') }}
)
select ... from orders join customers ...
limit 100  -- Too late, and redundant with --limit flag
```

## Common Mistakes

**Assuming column names reflect content**. Always verify with sample data; `customer_id` might contain account IDs

**Not documenting findings**. Discovery without documentation wastes effort; write it down immediately

**Testing relationships on sampled data only**. Orphan records may exist outside your sample; run full counts

**Ignoring soft deletes**. Check for `deleted_at`, `is_active`, or `status` columns that filter valid records
