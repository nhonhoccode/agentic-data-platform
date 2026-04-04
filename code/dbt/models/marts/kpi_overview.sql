select
    count(*)::bigint as total_orders,
    count(*) filter (where is_delivered)::bigint as delivered_orders,
    round(
        (count(*) filter (where is_delivered)::numeric / nullif(count(*), 0))::numeric,
        4
    ) as delivered_order_rate,
    sum(payment_total)::numeric(14, 2) as gmv,
    round(avg(payment_total)::numeric, 2) as avg_order_value,
    round(avg(d.delivery_delay_days)::numeric, 2) as avg_delivery_delay_days
from {{ ref('fct_orders') }} o
left join {{ ref('fct_delivery_performance') }} d
    on o.order_id = d.order_id
