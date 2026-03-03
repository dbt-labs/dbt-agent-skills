{{
  config(
    materialized='table',
    meta={
      'owner': 'analytics_team',
      'logical_key': ['id', 'user_id']
    }
  )
}}

{% set owner = config.require('owner') %}
{% set keys = config.require('logical_key') %}

select
  1 as id,
  100 as user_id,
  '{{ owner }}' as owner,
  '{{ keys | join(", ") }}' as key_columns
