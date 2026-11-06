-- Merges on unique_key (the dbt-snowflake default), and reads the payload
-- with colon paths.
select
    event_id,
    emitted_at,
    payload:invocation_id::varchar as invocation_id,
    payload:"context":"version"::varchar as dbt_version
from {{ ref('base_events_command') }}
{% if is_incremental() %}
where emitted_at > (select dateadd(day, -3, max(emitted_at)) from {{ this }})
{% endif %}
