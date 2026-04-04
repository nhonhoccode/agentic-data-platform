select
    order_month,
    round(avg(delivery_delay_days)::numeric, 2) as avg_delivery_delay_days,
    round(avg(is_late_delivery)::numeric, 4) as late_delivery_rate
from {{ ref('fct_delivery_performance') }}
group by 1
order by 1
