select
    trim(customer_id) as customer_id,
    trim(customer_unique_id) as customer_unique_id,
    nullif(customer_zip_code_prefix, '')::int as customer_zip_code_prefix,
    lower(trim(customer_city)) as customer_city,
    upper(trim(customer_state)) as customer_state
from {{ source('raw', 'customers') }}
