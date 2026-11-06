{{ config(materialized='table') }}
select product_sku from {{ ref( "exposed_view" ) }}
