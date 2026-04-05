select
    trim(order_id) as order_id,
    nullif(order_item_id, '')::int as order_item_id,
    trim(product_id) as product_id,
    trim(seller_id) as seller_id,
    nullif(shipping_limit_date, '')::timestamp as shipping_limit_ts,
    nullif(price, '')::numeric(12, 2) as price,
    nullif(freight_value, '')::numeric(12, 2) as freight_value
from {{ source('raw', 'order_items') }}
