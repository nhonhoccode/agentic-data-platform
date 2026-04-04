select
    trim(p.product_id) as product_id,
    trim(p.product_category_name) as product_category_name,
    coalesce(t.product_category_name_english, 'unknown') as product_category_name_en,
    nullif(p.product_name_lenght, '')::int as product_name_length,
    nullif(p.product_description_lenght, '')::int as product_description_length,
    nullif(p.product_photos_qty, '')::int as product_photos_qty,
    nullif(p.product_weight_g, '')::numeric(12, 2) as product_weight_g,
    nullif(p.product_length_cm, '')::numeric(12, 2) as product_length_cm,
    nullif(p.product_height_cm, '')::numeric(12, 2) as product_height_cm,
    nullif(p.product_width_cm, '')::numeric(12, 2) as product_width_cm
from {{ source('raw', 'products') }} p
left join {{ ref('stg_product_category_translation') }} t
    on trim(p.product_category_name) = t.product_category_name
