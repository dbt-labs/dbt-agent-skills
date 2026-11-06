select event_id, emitted_at, payload
from {{ source('telemetry', 'events_adapter') }}
