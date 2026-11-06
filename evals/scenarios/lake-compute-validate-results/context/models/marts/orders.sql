{{ config(adapter='lakecompute') }}

select * from {{ ref('stg_orders') }}
