with max_order_ts as (
    select max(nullif(order_purchase_timestamp, '')::timestamp) as max_purchase_ts
    from raw.orders
)

select *
from max_order_ts
where max_purchase_ts < timestamp '2018-08-01'
