-- Looks up a table's columns while it compiles: offline that gets
-- stand-ins, so its SQL isn't checked.
{%- set columns = adapter.get_columns_in_relation(ref('orders')) -%}
select
    {%- for column in columns %}
    {{ column.name }}{{ "," if not loop.last }}
    {%- endfor %}
from {{ ref('orders') }}
