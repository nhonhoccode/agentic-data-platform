select
    order_id,
    payment_sequential,
    payment_type,
    payment_installments,
    payment_value
from {{ ref('stg_order_payments') }}
