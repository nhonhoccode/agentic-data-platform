{{ config(alias='fct_sales_by_category') }}

select * from {{ ref('fct_sales_by_category') }}
