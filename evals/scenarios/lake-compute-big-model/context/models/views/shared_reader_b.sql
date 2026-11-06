{{ config(materialized='table') }}
select store_name from {{ ref('shared_view') }}
