-- This model has an empty SELECT (no columns)
-- Triggers dbt0404: "SELECT with no columns"

{% set columns = [] %}

select
  {% for col in columns %}
    {{ col }}{{ "," if not loop.last }}
  {% endfor %}
from {{ ref('some_table') }}
