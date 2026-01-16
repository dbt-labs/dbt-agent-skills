# Planning dbt Models: The Backwards Approach

This skill teaches a methodology for planning dbt models by starting with the desired output and working backwards, inspired by [Claire Carroll's article](https://discourse.getdbt.com/t/writing-models-backwards-an-unorthodox-approach-to-data-transformation/2287).

## When to Use

Use this approach when:

- Building a new complex model with unclear data requirements
- Planning multi-step transformations across multiple models
- Unsure about the grain or structure of intermediate models

## The Backwards Method

### Step 1: Mock the Final Output

Create a spreadsheet or markdown table with the **ideal output** you want to produce. Include:

- Column names that match business requirements
- Sample data rows (numbers don't need to be accurate)
- The grain/granularity you're targeting

**Example:** Daily inventory levels

| date       | product_id | product_name | quantity_on_hand | value_on_hand |
|------------|------------|--------------|------------------|---------------|
| 2024-01-01 | SKU-001    | Widget A     | 100              | 2500.00       |
| 2024-01-01 | SKU-002    | Widget B     | 50               | 1250.00       |
| 2024-01-02 | SKU-001    | Widget A     | 95               | 2375.00       |

### Step 2: Mock the SQL query for this output

Write pseudocode or actual SQL that would produce this table, even if you don't know what table you're selecting from yet:

```sql
select
  date_trunc('day', ????) as date,
  product_id,
  sum(???) as quantity_on_hand  -- Need running total, not daily sum
from ???
group by 1, 2
```

**Key insight:** If you can't write the query logic, your output table structure needs refinement.

### Step 3: Identify gaps and iterate

As you write the query, you'll discover what the **upstream model** needs to provide:

**Questions to ask:**

- What date field should inventory levels be based on?
- Should I calculate a cumulative sum across transactions?
- What about products with no transactions on a given day?
- Do I need a running balance or just daily aggregates?

**Example iteration:** Realized we need a running total, not a daily sum. This means we need window functions over transaction history, not a simple GROUP BY.

### Step 4: Mock the required upstream model

Based on your query needs, mock the table you're selecting from:

**Upstream model:** `product_transactions` (one record per inventory transaction)

| transaction_id | transaction_date | product_id | transaction_type | quantity | unit_cost |
|----------------|------------------|------------|------------------|----------|-----------|
| 1              | 2024-01-01       | SKU-001    | purchase         | 100      | 25.00     |
| 2              | 2024-01-01       | SKU-001    | sale             | -5       | 25.00     |
| 3              | 2024-01-02       | SKU-001    | return           | 3        | 25.00     |
| 4              | 2024-01-01       | SKU-002    | purchase         | 50       | 25.00     |

### Step 5: Update final model SQL based on new upstream structure

Now write the query to produce your final output, selecting from the mocked upstream model:

```sql
with running_balance as (
  select
    transaction_date as date,
    product_id,
    transaction_type,
    quantity,
    unit_cost,
    sum(quantity) over (
      partition by product_id
      order by transaction_date, transaction_id
      rows between unbounded preceding and current row
    ) as quantity_on_hand
  from product_transactions
),

end_of_day_balance as (
  select
    date,
    product_id,
    quantity_on_hand,
    unit_cost,
    row_number() over (partition by product_id, date order by transaction_id desc) as rn
  from running_balance
)

select
  date,
  product_id,
  'Widget ' || right(product_id, 1) as product_name,  -- TODO: join to product dimension
  quantity_on_hand,
  quantity_on_hand * unit_cost as value_on_hand
from end_of_day_balance
where rn = 1
```

This reveals we need:

- The upstream `product_transactions` table
- Logic to get the last transaction of each day (running balance at EOD)
- A product dimension table for proper product names

### Step 6: Match with Source Data

Now that you know what inputs you need, look at the actual resources available in your dbt project:

- What tables exist?
- What grain are they at?
- Do multiple tables need to be unioned?
- What joins are required?

If a table with the characteristics of the mocked-up `product_transactions` table already exists, use that. Otherwise, add it as another model which needs to be built and recursively repeat the process of establishing its parents' shape and code.

### Step 7: Implement the planned models

Once you've worked backwards to existing models or source data, you can now implement with real code. Reuse existing models wherever possible.

## Practical Tips

### Use Placeholder Columns

When building incrementally, use placeholders to define the interface:

```sql
select
  transaction_date,
  product_id,
  quantity,
  null::integer as quantity_on_hand -- TODO: implement cumulative sum window function
from {{ ref('stg_inventory_transactions') }}
```

### Document Your Planning

Create a markdown file alongside your models:

```markdown
## Goal
Calculate daily inventory levels per product

## Final output grain
One row per product per day

## Intermediate model grain
One row per transaction with running balance

## Required transformations
1. Combine purchase, sale, and return transaction types
2. Add window function for cumulative quantity on hand
3. Filter to end-of-day balance per product
```

### Test Your Assumptions Early

Don't wait to test edge cases:

- What if multiple transactions occur on the same day for one product?
- What if a product has no transactions for several days?
- How do you handle null transaction dates or quantities?

## Common Pitfalls

❌ **Starting to code before understanding the output**

- Leads to multiple refactors and unclear model purposes

❌ **Assuming upstream data has the grain you need**

- Check early whether you need to change grain (aggregate or explode)

❌ **Not iterating on the mockup**

- If you can't write the SQL, revise your output structure

❌ **Forgetting about data quality**

- Consider null handling, duplicates, and edge cases in your planning

## Comparison with Traditional Approach

### Traditional (Left-to-Right)

1. Look at source data
2. Start writing transformations
3. Hope it produces the right output
4. Debug when it doesn't

### Backwards (Right-to-Left)

1. Define exact output needed
2. Work backwards to understand requirements
3. Build with clear purpose at each step
4. Less debugging needed

## Benefits

✅ **Clearer model purpose** - Each model has an obvious goal  
✅ **Better intermediate models** - You know exactly what fields and grain are needed  
✅ **Fewer refactors** - Understanding requirements upfront prevents rework  
✅ **Easier debugging** - When you know what you expect, issues are obvious  
✅ **Better tests** - You can define expected output before building  

## Related Concepts

- **Test-Driven Development (TDD)**: Similar philosophy of defining expected output first
- **Kimball Methodology**: Start with business questions, work back to data requirements
- **Dimensional Modeling**: Understanding fact/dimension grain before implementation

## Example Workflow

```bash
# 1. Create a planning doc
touch models/marts/inventory/PLANNING.md

# 2. Mock output in the doc
# (add your table mockups)

# 3. Create placeholder models
touch models/marts/inventory/daily_inventory_levels.sql
touch models/intermediate/inventory/int_transactions_with_running_balance.sql

# 4. Add placeholder columns
# (null::type as column_name)

# 5. Write the actual SQL based on your planning
# Fill in the real logic for each model, working left to right

# 7. Run new models once code complete to validate correctness
dbt run --select +daily_inventory_levels
```
