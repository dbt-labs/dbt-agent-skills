select
    i.invocation_id,
    i.dbt_version,
    count(c.event_id) as commands
from {{ ref('stg_events_invocation') }} i
left join {{ ref('stg_events_command') }} c using (invocation_id)
group by 1, 2
