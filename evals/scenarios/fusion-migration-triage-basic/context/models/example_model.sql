{{
  config(
    materialized='table',
    meta={
      'logical_key': ['id', 'user_id'],
      'owner': 'analytics_team'
    }
  )
}}

-- This model uses the deprecated config.require('meta') API
-- It should trigger a dbt1501 error in Fusion

{% set keys = config.require('meta').logical_key %}
{% set owner = config.require('meta').owner %}

select
  1 as id,
  100 as user_id,
  'test' as name,
  '{{ owner }}' as owner,
  '{{ keys | join(", ") }}' as key_columns
