{{ config(adapter='lakecompute') }}

select
    cast(ordered_at as date) as order_date,
    count(*) as order_count,
    sum(order_total) as revenue
from {{ ref('orders') }}
group by 1
