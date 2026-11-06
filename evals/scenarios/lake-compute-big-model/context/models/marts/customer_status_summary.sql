-- DuckDB-compatible SQL, but its parent (customer_status) is not, so it is
-- only eligible if customer_status is fixed and moved too.
select
    status,
    count(*) as customer_count,
    sum(lifetime_spend) as lifetime_spend
from {{ ref('customer_status') }}
group by 1
