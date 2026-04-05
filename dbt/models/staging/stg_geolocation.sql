select
    nullif(geolocation_zip_code_prefix, '')::int as geolocation_zip_code_prefix,
    nullif(geolocation_lat, '')::double precision as geolocation_lat,
    nullif(geolocation_lng, '')::double precision as geolocation_lng,
    lower(trim(geolocation_city)) as geolocation_city,
    upper(trim(geolocation_state)) as geolocation_state
from {{ source('raw', 'geolocation') }}
