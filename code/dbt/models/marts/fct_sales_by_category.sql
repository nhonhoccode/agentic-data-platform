select
    coalesce(category_name_en, 'unknown') as category_name_en,
    count(distinct order_id) as total_orders,
    sum(price)::numeric(14, 2) as total_revenue,
    avg(price)::numeric(14, 2) as avg_item_value
from {{ ref('fct_order_items') }}
group by 1
