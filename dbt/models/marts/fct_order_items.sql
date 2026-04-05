select
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    p.product_category_name_en as category_name_en,
    oi.seller_id,
    oi.shipping_limit_ts,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value) as gross_item_value
from {{ ref('stg_order_items') }} oi
left join {{ ref('dim_products') }} p
    on oi.product_id = p.product_id
