{{
  config(
    materialized='table',
    my_custom_key='custom_value',
    another_unexpected_key=123
  )
}}

SELECT 1 as id, 'test' as name
