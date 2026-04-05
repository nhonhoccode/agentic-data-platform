{{ config(alias='kpi_overview') }}

select * from {{ ref('kpi_overview') }}
