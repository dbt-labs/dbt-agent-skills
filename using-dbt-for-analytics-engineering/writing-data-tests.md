# Writing Data Tests in dbt

Write high-value tests that catch real data issues without burning warehouse credits on low-signal checks. Testing should drive action—not accumulate alerts.

## When to Use

- Adding tests to new or existing models
- Reviewing test coverage for cost optimization
- After completing data discovery (use discovering-data skill first)
- When stakeholders report data quality issues

## Understanding Data Quality

### Data Hygiene

Issues you address in your staging layer. Hygienic data meets expectations around formatting (correct values and structure), completeness (no unexpected nulls), and granularity (no duplicates).

### Business-Focused Anomalies

Unexpected behavior based on what you know to be typical in your business. These tests need periodic adjustment as business context shifts. Revenue volatility or user retention changes may be due to a sale, but could also reflect a problem in data ingestion or now-invalid transformation logic.

## Where Tests Belong in the Pipeline

Different layers need different tests. Don't duplicate tests for pass-through columns.

### Staging

Catch data hygiene issues and basic anomalies.

```yaml
models:
  - name: stg_orders
    columns:
      - name: order_id
        data_tests:
          - unique
          - not_null
      - name: customer_id
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_customers')
                field: customer_id
      - name: status
        data_tests:
          - accepted_values:
              arguments:
                values: ['pending', 'completed', 'cancelled']
```

### Intermediate

Test when grain changes or joins create new risks.

```yaml
models:
  - name: int_orders_enriched
    columns:
      - name: order_customer_key
        description: "Composite key created by join"
        data_tests:
          - unique
          - not_null
```

### Marts

Protect end-user facing data. Test business expectations and new calculated fields.

```yaml
models:
  - name: fct_orders
    data_tests:
      # ONE critical business rule, not ten
      - dbt_utils.expression_is_true:
          arguments:
            expression: "total_amount >= 0 OR is_refund = true"
    columns:
      - name: order_id
        data_tests:
          - unique
          - not_null
```

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
| `not_null` | Discovery confirmed 0% nulls AND nulls would break logic | Catches regressions |

### Tier 3: Selective Use (Business Logic)

| Test | Apply When | Why |
|------|------------|-----|
| `expression_is_true` | Logic spans multiple columns | Detects subtle logic bugs |
| `accepted_range` | Constrained value set such as ages or dates | Avoids illogical values like 200 year old person or login before account creation |

### Tier 4: Avoid Unless Justified

| Test | Problem |
|------|---------|
| `not_null` on every column | Low signal, high cost |
| Multiple `expression_is_true` per model | Expensive, hard to read and maintain |
| `unique` on non-PK columns | Unnecessary and likely wrong |

## Before Writing Tests

### Step 1: Check Installed Packages

```bash
# List installed packages
cat package-lock.yml
```

**Common test packages:**
- `dbt-utils`: `expression_is_true`, `recency`, `at_least_one`, `unique_combination_of_columns`, `accepted_range`
- `dbt-expectations`: `expect_column_values_to_be_between`, `expect_column_values_to_match_regex`, statistical tests
- `elementary`: Anomaly detection, schema change monitoring

### Step 2: Install packages if needed

```bash
dbt deps --add-package dbt-labs/dbt_utils@">=1.0.0,<2.0.0"
```

### Step 3: Review Discovery Findings

If you used the instructions in [discovering-data](./discovering-data.md), your findings tell you exactly what to test:

| Discovery Finding | Test Action |
|-------------------|-------------|
| "Verified unique, no nulls" | Add `unique` + `not_null` |
| "X% orphan records" | Add `relationships` with `severity: warn` if >1% |
| "Small number of well-known values present" | Add `accepted_values` |
| "Y% null rate" | Do NOT add `not_null` - nulls are expected |
| "Creation date always in the past" | Add `dbt_utils.accepted_range` |

## Document Debugging Steps

Non-obvious tests should have documented first steps for debugging. Add these to test descriptions or a shared framework document.

```yaml
models:
  - name: fct_orders
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: "total_amount >= 0 OR is_refund = true"
          description: |
            Negative totals indicate calculation errors.
            Debug steps:
            1. Query failed rows using test SQL
            2. Check line_items for same orders in staging
            3. Verify discount logic in int_orders_discounted
```

## Cost-Conscious Testing

### For Large Tables (millions of rows)

Use `where` to limit scope:

```yaml
- relationships:
    arguments:
      to: ref('dim_users')
      field: user_id
    config:
      where: "created_at >= current_date - interval '7 days'"
```

## Common Mistakes

### Testing nulls that are valid

```yaml
# WRONG: Discovery showed 45% nulls are expected
- name: optional_field
  data_tests:
    - not_null  # Will fail unnecessarily

# RIGHT: No test, document why
- name: optional_field
  description: "Nullable - only populated for X scenario"
```

### Over-testing business logic

Don't check that the SQL ran correctly, think of places that an assumption could prove false and write a test to detect it.

```yaml
# WRONG: 10 expression tests for one model
data_tests:
  - dbt_utils.expression_is_true:
      arguments:
        expression: "a > 0"
  - dbt_utils.expression_is_true:
      arguments:
        expression: "b > 0"
  # ... 8 more

# RIGHT: One critical invariant
data_tests:
  - dbt_utils.expression_is_true:
      arguments:
        expression: "total = subtotal + tax + shipping"
```

### Not using discovery findings

```yaml
# WRONG: Guessing at values without context
- name: order_status
  data_tests:
    - accepted_values:
        arguments:
          values: ['placed', 'shipped', 'completed', 'returned']

# RIGHT: Checked actual values during data discovery
- name: order_status
  data_tests:
    - accepted_values:
        arguments:
          values: ['created', 'processing', 'shipped', 'delivered', 'refunded']
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| Primary key | `unique` + `not_null` always |
| Foreign key | `relationships` |
| Enum column | `accepted_values` |
| Nullable column | No `not_null` test |
| Large table (1M+) | Use `where` config on expensive tests |
| Nice-to-know issue | `severity: warn` or remove |
