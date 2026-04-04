select
    trim(seller_id) as seller_id,
    nullif(seller_zip_code_prefix, '')::int as seller_zip_code_prefix,
    lower(trim(seller_city)) as seller_city,
    upper(trim(seller_state)) as seller_state
from {{ source('raw', 'sellers') }}
