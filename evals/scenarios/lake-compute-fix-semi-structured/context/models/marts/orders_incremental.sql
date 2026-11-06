-- DuckDB-compatible SQL with Iceberg upstreams, but lakecompute only supports
-- incremental strategies 'append' and 'insert_overwrite'.
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='order_id') }}
select * from {{ ref('orders') }}
{% if is_incremental() %}
where order_date > (select max(order_date) from {{ this }})
{% endif %}
