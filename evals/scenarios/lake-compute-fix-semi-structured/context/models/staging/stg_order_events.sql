select
    e.event_id,
    e.order_id,
    e.event_at,
    e.payload:status::varchar as event_status,
    f.value:sku::varchar as item_sku,
    object_construct('event_id', e.event_id, 'sku', f.value:sku) as event_item
from {{ source('ecom', 'raw_order_events') }} e,
    lateral flatten(input => e.payload:items) f
