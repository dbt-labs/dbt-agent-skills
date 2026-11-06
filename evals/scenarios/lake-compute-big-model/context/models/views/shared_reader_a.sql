{{ config(materialized='table') }}
select store_id from {{ ref('shared_view') }}
