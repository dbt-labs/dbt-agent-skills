with

source as (

    select * from {{ source('ecom', 'raw_supplies') }}

),

renamed as (

    select

        ----------  ids
        md5(id || '-' || sku) as supply_uuid,
        id as supply_id,
        sku as product_id,

        ---------- text
        name as supply_name,

        ---------- numerics
        {{ cents_to_dollars('cost') }} as supply_cost,

        ---------- booleans
        perishable as is_perishable_supply

    from source

)

select * from renamed
