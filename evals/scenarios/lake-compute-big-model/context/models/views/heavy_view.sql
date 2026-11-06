-- One reader, but its plan holds memory (an aggregate): switch makes it a table.
{{ config(materialized='view') }}
select sku, count(*) as items from {{ source('ecom', 'raw_items') }} group by sku
