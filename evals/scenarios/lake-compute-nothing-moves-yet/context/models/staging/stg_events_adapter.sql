-- A table, so it compiles offline: its colon paths and dateadd get checked.
{{ config(materialized='table') }}

select
    event_id,
    emitted_at,
    payload:adapter_type::varchar as adapter_type,
    dateadd(day, 1, emitted_at) as expires_at
from {{ ref('base_events_adapter') }}
