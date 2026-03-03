-- This analysis uses a PostgreSQL-specific function that doesn't exist in DuckDB
-- This should trigger a static analysis error in Fusion

select
  invalid_sql as sleep_result,
  array_to_string(array_agg(name), ', ') as names,
  count(*) as total
from {{ ref('example_model') }}
group by 1
