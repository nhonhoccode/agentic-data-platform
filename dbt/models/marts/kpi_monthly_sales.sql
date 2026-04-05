select
    order_month as month,
    count(*)::bigint as total_orders,
    count(*) filter (where is_delivered)::bigint as delivered_orders,
    sum(payment_total)::numeric(14, 2) as gmv,
    round(avg(payment_total)::numeric, 2) as avg_order_value
from {{ ref('fct_orders') }}
group by 1
order by 1
