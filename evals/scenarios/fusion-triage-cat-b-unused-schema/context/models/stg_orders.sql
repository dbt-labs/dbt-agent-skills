-- Only stg_orders.sql exists, stg_users.sql does NOT
-- This will trigger dbt1005 for the unused stg_users entry in schema.yml

select
  1 as order_id,
  100 as user_id
