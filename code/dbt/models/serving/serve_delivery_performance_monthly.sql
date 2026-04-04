{{ config(alias='delivery_performance_monthly') }}

select * from {{ ref('delivery_performance_monthly') }}
