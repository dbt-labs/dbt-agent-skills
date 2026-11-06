-- No incremental_strategy: dbt-snowflake merges on unique_key.
{{ config(materialized='incremental', unique_key='order_id') }}

select order_id, order_total from {{ ref('orders') }}
