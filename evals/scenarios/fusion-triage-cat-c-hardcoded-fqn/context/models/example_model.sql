-- This model uses a hardcoded fully-qualified name
-- This may cause permission errors: dbt0214 or similar
-- The fix depends on what 'orders' is

select
  order_id,
  user_id,
  order_date
from prod.raw.orders  -- Hardcoded FQN - should use ref() or source()
where order_date >= '2024-01-01'
