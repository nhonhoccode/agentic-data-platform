select
    trim(review_id) as review_id,
    trim(order_id) as order_id,
    nullif(review_score, '')::int as review_score,
    nullif(review_comment_title, '') as review_comment_title,
    nullif(review_comment_message, '') as review_comment_message,
    nullif(review_creation_date, '')::timestamp as review_creation_ts,
    nullif(review_answer_timestamp, '')::timestamp as review_answer_ts
from {{ source('raw', 'order_reviews') }}
