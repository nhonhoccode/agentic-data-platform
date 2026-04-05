with checks as (
    select
        'customers' as table_name,
        (select count(*)::bigint from raw.customers) as raw_count,
        (select count(*)::bigint from staging.stg_customers) as stg_count
    union all
    select
        'orders' as table_name,
        (select count(*)::bigint from raw.orders),
        (select count(*)::bigint from staging.stg_orders)
    union all
    select
        'order_items' as table_name,
        (select count(*)::bigint from raw.order_items),
        (select count(*)::bigint from staging.stg_order_items)
    union all
    select
        'order_payments' as table_name,
        (select count(*)::bigint from raw.order_payments),
        (select count(*)::bigint from staging.stg_order_payments)
    union all
    select
        'products' as table_name,
        (select count(*)::bigint from raw.products),
        (select count(*)::bigint from staging.stg_products)
    union all
    select
        'sellers' as table_name,
        (select count(*)::bigint from raw.sellers),
        (select count(*)::bigint from staging.stg_sellers)
    union all
    select
        'order_reviews' as table_name,
        (select count(*)::bigint from raw.order_reviews),
        (select count(*)::bigint from staging.stg_order_reviews)
)

select *
from checks
where raw_count <> stg_count
