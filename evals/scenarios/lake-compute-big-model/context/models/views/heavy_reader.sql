{{ config(materialized='table') }}
select sku, items from {{ ref('heavy_view') }}
