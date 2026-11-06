-- A dashboard reads it: it stays a view, and switch adds an Iceberg table of it
-- for exposed_reader.
{{ config(materialized='view') }}
select id as product_sku, name as product_name from {{ source('ecom', 'raw_products') }}
