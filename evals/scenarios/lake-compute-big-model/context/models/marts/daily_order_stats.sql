-- Portable SQL that also works on DuckDB, using qualify and listagg.
select
    order_date,
    count(*) as order_count,
    listagg(distinct location_id, ',') as location_ids
from {{ ref('orders') }}
group by 1
qualify row_number() over (order by order_date desc) <= 30
