select
    trim(order_id) as order_id,
    trim(customer_id) as customer_id,
    trim(order_status) as order_status,
    nullif(order_purchase_timestamp, '')::timestamp as order_purchase_ts,
    nullif(order_approved_at, '')::timestamp as order_approved_ts,
    nullif(order_delivered_carrier_date, '')::timestamp as order_delivered_carrier_ts,
    nullif(order_delivered_customer_date, '')::timestamp as order_delivered_customer_ts,
    nullif(order_estimated_delivery_date, '')::timestamp as order_estimated_delivery_ts
from {{ source('raw', 'orders') }}
