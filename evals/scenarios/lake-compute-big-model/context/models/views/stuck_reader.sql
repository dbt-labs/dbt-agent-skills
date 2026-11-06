{{ config(materialized='table') }}
select event_id, status from {{ ref('stuck_view') }}
