select
    trim(order_id) as order_id,
    nullif(payment_sequential, '')::int as payment_sequential,
    trim(payment_type) as payment_type,
    nullif(payment_installments, '')::int as payment_installments,
    nullif(payment_value, '')::numeric(12, 2) as payment_value
from {{ source('raw', 'order_payments') }}
