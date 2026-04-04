{{ config(alias='kpi_monthly_sales') }}

select * from {{ ref('kpi_monthly_sales') }}
