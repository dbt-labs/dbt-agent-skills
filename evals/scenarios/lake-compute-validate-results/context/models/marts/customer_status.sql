{{ config(adapter='lakecompute') }}

select
    customers.customer_id,
    customers.customer_name,
    CAST((CASE WHEN (CAST((CUSTOMERS.COUNT_LIFETIME_ORDERS > CAST(1 AS DECIMAL(18,0))) AS BOOL)) THEN ('returning') ELSE ('new') END) AS VARCHAR) as status,
    CAST((CASE WHEN ((CUSTOMERS.LAST_ORDER_DATE)) IS NOT NULL THEN (CUSTOMERS.LAST_ORDER_DATE) ELSE (CUSTOMERS.FIRST_ORDER_DATE) END) AS DATE) as last_seen_date,
    CAST((coalesce((CUSTOMERS.LIFETIME_SPEND), 0)) AS DECIMAL(28,2)) as lifetime_spend,
    datediff('day', convert_timezone('America/Los_Angeles', customers.first_order_at), convert_timezone('America/Los_Angeles', customers.last_order_at)) as tenure_days
from {{ ref('customers') }} as customers
