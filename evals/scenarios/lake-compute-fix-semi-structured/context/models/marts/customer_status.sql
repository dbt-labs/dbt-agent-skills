-- Snowflake-only scalar functions: binds fail on DuckDB
-- (iff, nvl, zeroifnull, unquoted datediff date part).
select
    customers.customer_id,
    customers.customer_name,
    iff(customers.count_lifetime_orders > 1, 'returning', 'new') as status,
    nvl(customers.last_order_date, customers.first_order_date) as last_seen_date,
    zeroifnull(customers.lifetime_spend) as lifetime_spend,
    datediff(day, customers.first_order_date, customers.last_order_date) as tenure_days
from {{ ref('customers') }} as customers
