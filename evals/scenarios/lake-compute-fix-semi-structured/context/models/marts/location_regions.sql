-- DuckDB-compatible SQL, but reads a seed (a native Snowflake table).
select
    locations.location_id,
    locations.location_name,
    store_regions.region
from {{ ref('locations') }} as locations
left join {{ ref('store_regions') }} as store_regions
    on locations.location_name = store_regions.location_name
