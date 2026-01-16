# Writing Data Tests in dbt

Write high-value tests that catch real data issues without burning warehouse credits on low-signal checks.

## When to Use

- Adding tests to new or existing models
- Reviewing test coverage for cost optimization
- After completing data discovery (use discovering-data skill first)
- When stakeholders report data quality issues

## The Priority Framework

Not all tests provide equal value. Use this framework to prioritize:

### Tier 1: Always Add (Structural Integrity)
| Test | Apply To | Why |
|------|----------|-----|
| `unique` | Primary keys only | Broken PKs break everything downstream |
| `not_null` | Primary keys only | Same reason |
| `relationships` | Foreign keys without orphans | Catches broken joins early |

### Tier 2: Add When Discovery Warrants (Data Quality)
| Test | Apply When | Why |
|------|------------|-----|
| `accepted_values` | Discovery found enum with known values | Catches new invalid values |
| `relationships` (warn) | Discovery found 1-5% orphans | Surfaces issue without blocking |
| `not_null` | Discovery confirmed 0% nulls AND nulls would break logic | Catches regressions |

### Tier 3: Selective Use (Business Logic)
| Test | Apply When | Why |
|------|------------|-----|
| `expression_is_true` | Single critical business rule | Validates invariant |
| `accepted_range` | Discovery found unexpected values | Catches data drift |

### Tier 4: Avoid Unless Justified
| Test | Problem |
|------|---------|
| `not_null` on every column | Low signal, high cost |
| Multiple `expression_is_true` per model | Expensive, hard to maintain |
| `unique` on non-PK columns | Usually wrong (use unique combo test) |

## Before Writing Tests

### Step 1: Check Installed Packages

```bash
# List installed packages
cat packages.yml
```

**Common test packages:**
- `dbt-utils`: `expression_is_true`, `recency`, `at_least_one`, `unique_combination_of_columns`, `accepted_range`
- `dbt-expectations`: `expect_column_values_to_be_between`, `expect_column_values_to_match_regex`, statistical tests
- `elementary`: Anomaly detection, schema change monitoring

### Step 2: Decide Whether to Install a Package

**Install dbt-utils if:**
- Not already installed AND
- You need `expression_is_true`, `unique_combination_of_columns`, or other tests it provides

**Install dbt-expectations if:**
- Not already installed AND
- You need statistical tests, regex validation, or distribution checks

### Step 3: Review Discovery Findings

If you used the discovering-data skill, your findings tell you exactly what to test:

| Discovery Finding | Test Action |
|-------------------|-------------|
| "Verified unique, no nulls" | Add `unique` + `not_null` |
| "X% orphan records" | Add `relationships` with `severity: warn` if >1% |
| "Small number of well-known values present" | Add `accepted_values` |
| "Y% null rate" | Do NOT add `not_null` - nulls are expected |

## Writing Tests: The Right Amount

### Staging Models
Focus on structural integrity. Let marts handle business logic.

```yaml
models:
  - name: stg_orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('stg_customers')
              field: customer_id
      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'completed', 'cancelled']
      # order_date, created_at, etc: NO tests unless discovery found issues
```

### Mart Models
Add business logic tests sparingly - one or two critical invariants.

```yaml
models:
  - name: fct_orders
    tests:
      # ONE critical business rule, not ten
      - dbt_utils.expression_is_true:
          expression: "total_amount >= 0 OR is_refund = true"
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
```

## Cost-Conscious Testing

### For Large Tables (millions of rows)

1. **Use `where` to limit scope:**
```yaml
- relationships:
    to: ref('dim_users')
    field: user_id
    config:
      where: "created_at >= current_date - interval '7 days'"
```

### What NOT to Optimize
- Primary key `unique` + `not_null` - always run these
- `recency` tests - these are cheap (just MAX aggregation)

## Common Mistakes

**Testing nulls that are valid**
```yaml
# WRONG: Discovery showed 45% nulls are expected
- name: optional_field
  tests:
    - not_null  # Will fail unnecessarily

# RIGHT: No test, document why
- name: optional_field
  description: "Nullable - only populated for X scenario"
```

**Over-testing business logic**
```yaml
# WRONG: 10 expression tests for one model
tests:
  - dbt_utils.expression_is_true:
      expression: "a > 0"
  - dbt_utils.expression_is_true:
      expression: "b > 0"
  # ... 8 more

# RIGHT: One critical invariant, or create singular test file
tests:
  - dbt_utils.expression_is_true:
      expression: "total = subtotal + tax + shipping"
```

**Not using discovery findings**
```yaml
# WRONG: Generic tests without context
- name: customer_id
  tests:
    - relationships:
        to: ref('stg_customers')
        field: customer_id

# RIGHT: Discovery-informed severity
- name: customer_id
  tests:
    - relationships:
        to: ref('stg_customers')
        field: customer_id
        config:
          severity: warn  # 3% orphans per discovery
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| Primary key | `unique` + `not_null` always |
| Foreign key, <1% orphans | `relationships` |
| Foreign key, 1-5% orphans | `relationships` with `severity: warn` |
| Foreign key, >5% orphans | Fix data first, don't test broken joins |
| Enum column | `accepted_values` |
| Nullable column | No `not_null` test |
| Large table (1M+) | Use `where` clause on expensive tests |
| Need business logic test | One `expression_is_true` max per model |
| Need statistical test | Use dbt-expectations |
