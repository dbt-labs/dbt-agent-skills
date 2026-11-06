-- Read by two models: switch makes it a table (built once, read by each).
{{ config(materialized='view') }}
select id as store_id, name as store_name from {{ source('ecom', 'raw_stores') }}
