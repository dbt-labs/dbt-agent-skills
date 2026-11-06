-- Its SQL can't run on Lake Compute (semi-structured access): it stays a view,
-- and switch adds an Iceberg table of it, built on Snowflake, for stuck_reader.
{{ config(materialized='view') }}
select event_id, payload:status::string as status from {{ source('ecom', 'raw_order_events') }}
