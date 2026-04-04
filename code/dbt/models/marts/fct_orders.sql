with item_agg as (
    select
        order_id,
        count(*) as item_count,
        sum(price) as item_total,
        sum(freight_value) as freight_total
    from {{ ref('stg_order_items') }}
    group by 1
),
payment_agg as (
    select
        order_id,
        sum(payment_value) as payment_total
    from {{ ref('stg_order_payments') }}
    group by 1
)
select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.order_purchase_ts,
    o.order_purchase_ts::date as order_purchase_date,
    date_trunc('month', o.order_purchase_ts)::date as order_month,
    o.order_approved_ts,
    o.order_delivered_carrier_ts,
    o.order_delivered_customer_ts,
    o.order_estimated_delivery_ts,
    (o.order_delivered_customer_ts is not null) as is_delivered,
    i.item_count,
    coalesce(i.item_total, 0)::numeric(14, 2) as item_total,
    coalesce(i.freight_total, 0)::numeric(14, 2) as freight_total,
    coalesce(p.payment_total, 0)::numeric(14, 2) as payment_total
from {{ ref('stg_orders') }} o
left join {{ ref('dim_customers') }} c
    on o.customer_id = c.customer_id
left join item_agg i
    on o.order_id = i.order_id
left join payment_agg p
    on o.order_id = p.order_id
