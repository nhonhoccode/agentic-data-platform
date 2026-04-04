select
    order_id,
    order_month,
    order_purchase_date,
    order_estimated_delivery_ts::date as estimated_delivery_date,
    order_delivered_customer_ts::date as delivered_customer_date,
    case
        when order_delivered_customer_ts is not null and order_estimated_delivery_ts is not null
            then (order_delivered_customer_ts::date - order_estimated_delivery_ts::date)
        else null
    end as delivery_delay_days,
    case
        when order_delivered_customer_ts::date > order_estimated_delivery_ts::date then 1
        else 0
    end as is_late_delivery
from {{ ref('fct_orders') }}
where order_status = 'delivered'
