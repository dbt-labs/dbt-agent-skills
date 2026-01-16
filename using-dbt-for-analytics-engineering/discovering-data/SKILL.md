---
name: discovering-data
description: Use when exploring unfamiliar data sources, onboarding to a new dbt project, or investigating data quality issues before building models
---

# Discovering Data with dbt show

Use `dbt show` to interactively explore raw data, understand table structures, and document findings for downstream model development.

## When to Use

- Onboarding to a new dbt project with unfamiliar source data
- Investigating data quality issues reported by stakeholders
- Planning new models and need to understand source grain/structure
- Mapping relationships between tables before building joins

## The Iron Rule

**Complete all 6 steps for every table you will build models on. No exceptions.**

Skipping steps doesn't save time - it moves the cost to debugging, rework, and incorrect business metrics. A 30-minute discovery shortcut becomes a 2-week production incident.

## Rationalizations That Mean STOP

| You're Thinking... | Reality |
|-------------------|---------|
| "I don't have time for full discovery" | You don't have time for wrong models. |
| "It's just a quick stakeholder briefing" | Quick briefings become "can you build a model from this?" You need to do full discovery before building anything." |
| "I'll do proper discovery later" | You won't. Document now or create technical debt someone else inherits. |
| "This is technical debt I'm accepting" | You're not accepting it - you're passing it to your future self or teammates. |
| "47 tables is too many for full methodology" | Then prioritize which tables you'll actually use and do full discovery on those. Don't half-discover everything. |
| "I'll just do the critical tables thoroughly" | ALL tables you build on are critical. If it's not worth full discovery, don't build models on it yet. |
| "Standard patterns, I know this data" | You know the pattern. You don't know THIS instance. Verify. |
| "The senior engineer said skip it" | The senior engineer won't debug your models at 2am. Follow the methodology. |

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
4. **Sequential, not parallel shortcuts** - If you have 15 in-scope tables, do full discovery on each one sequentially. Don't sample all 15, then grain-check all 15. Complete each table fully before moving to the next.

**Wrong approach:** "I'll do light discovery on all 47 tables"
**Right approach:** "I'll do full discovery on the 8 tables needed for this project"

## Core Method: Iterative Discovery

### Step 1: Inventory Available Sources

List all sources defined in the project:

```bash
dbt ls --resource-type source --output name
```

Review `models/staging/` for existing `_sources.yml` files to understand what's already documented.

### Step 2: Sample Raw Data

Preview rows from each source table:

```bash
dbt show --inline "SELECT * FROM {{ source('source_name', 'table_name') }} LIMIT 20" --output json
```

**Document immediately:**
- Column names and apparent data types
- Which columns appear to be identifiers vs attributes
- Obvious nulls, empty strings, or placeholder values

### Step 3: Analyze Table Grain

Determine what one row represents:

```bash
# Check total rows vs distinct keys
dbt show --inline "
SELECT
  COUNT(*) as total_rows,
  COUNT(DISTINCT id_column) as distinct_ids
FROM {{ source('source_name', 'table_name') }}
" --output json
```

**Grain indicators:**
- `total_rows = distinct_ids` → One row per entity (dimension-like)
- `total_rows > distinct_ids` → Multiple rows per entity (fact-like, needs grouping)
- Look for date columns that suggest time-series grain

### Step 4: Profile Key Columns

For each important column, check distribution and quality:

```bash
# Value distribution
dbt show --inline "
SELECT column_name, COUNT(*) as cnt
FROM {{ source('source_name', 'table_name') }}
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20
" --output json

# Null analysis
dbt show --inline "
SELECT
  COUNT(*) as total,
  COUNT(column_name) as non_null,
  COUNT(*) - COUNT(column_name) as null_count
FROM {{ source('source_name', 'table_name') }}
" --output json
```

**Data nuances to document:**
- Columns with high null rates
- Unexpected values (e.g., "N/A", "-1", "unknown")
- Date formats and timezone handling
- Numeric precision issues

### Step 5: Map Relationships

Test suspected foreign key relationships:

```bash
# Check if FK values exist in parent table
dbt show --inline "
SELECT COUNT(*) as orphan_count
FROM {{ source('source_name', 'child_table') }} c
LEFT JOIN {{ source('source_name', 'parent_table') }} p
  ON c.parent_id = p.id
WHERE p.id IS NULL
" --output json
```

**Relationship types to identify:**
- One-to-one: Both sides have same distinct count
- One-to-many: Parent has fewer distinct values
- Many-to-many: Requires junction table

### Step 6: Identify Structural Issues

Common problems to check:

```bash
# Duplicate primary keys
dbt show --inline "
SELECT id_column, COUNT(*) as cnt
FROM {{ source('source_name', 'table_name') }}
GROUP BY 1
HAVING COUNT(*) > 1
LIMIT 10
" --output json

# Mixed data in columns
dbt show --inline "
SELECT DISTINCT
  CASE
    WHEN TRY_CAST(mixed_column AS INTEGER) IS NOT NULL THEN 'integer'
    WHEN TRY_CAST(mixed_column AS DATE) IS NOT NULL THEN 'date'
    ELSE 'string'
  END as detected_type
FROM {{ source('source_name', 'table_name') }}
" --output json
```

## Documenting Findings

Create a discovery report that other agents can consume. Place in `docs/data_discovery/` or alongside the source YAML.

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

When using `dbt show --inline` to preview data, push `LIMIT` clauses as early as possible in CTEs to minimize data scanning. Never add a `LIMIT` at the end of the query - `dbt show --limit` handles that automatically.

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

## Quick Reference

| Task | Command |
|------|---------|
| List sources | `dbt ls --resource-type source` |
| Preview data | `dbt show --inline "SELECT * FROM {{ source(...) }} LIMIT 20" --output json` |
| Count rows | `dbt show --inline "SELECT COUNT(*) FROM {{ source(...) }}" --output json` |
| Check uniqueness | `dbt show --inline "SELECT col, COUNT(*) FROM ... GROUP BY 1 HAVING COUNT(*) > 1" --output json` |
| Test FK relationship | `dbt show --inline "SELECT COUNT(*) FROM child LEFT JOIN parent ON ... WHERE parent.id IS NULL" --output json` |

## Common Mistakes

**Assuming column names reflect content**
- Always verify with sample data; `customer_id` might contain account IDs

**Skipping null analysis**
- High null rates affect join behavior and aggregations

**Not documenting findings**
- Discovery without documentation wastes effort; write it down immediately

**Testing relationships on sampled data only**
- Orphan records may exist outside your sample; run full counts

**Ignoring soft deletes**
- Check for `deleted_at`, `is_active`, or `status` columns that filter valid records
