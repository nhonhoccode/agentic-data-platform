from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSpec:
    file_name: str
    table_name: str
    columns: list[str]


DATASET_SPECS: list[DatasetSpec] = [
    DatasetSpec(
        file_name="olist_customers_dataset.csv",
        table_name="customers",
        columns=[
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
    ),
    DatasetSpec(
        file_name="olist_geolocation_dataset.csv",
        table_name="geolocation",
        columns=[
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ],
    ),
    DatasetSpec(
        file_name="olist_order_items_dataset.csv",
        table_name="order_items",
        columns=[
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
    ),
    DatasetSpec(
        file_name="olist_order_payments_dataset.csv",
        table_name="order_payments",
        columns=[
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
    ),
    DatasetSpec(
        file_name="olist_order_reviews_dataset.csv",
        table_name="order_reviews",
        columns=[
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ],
    ),
    DatasetSpec(
        file_name="olist_orders_dataset.csv",
        table_name="orders",
        columns=[
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ),
    DatasetSpec(
        file_name="olist_products_dataset.csv",
        table_name="products",
        columns=[
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
    ),
    DatasetSpec(
        file_name="olist_sellers_dataset.csv",
        table_name="sellers",
        columns=[
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ],
    ),
    DatasetSpec(
        file_name="product_category_name_translation.csv",
        table_name="product_category_translation",
        columns=["product_category_name", "product_category_name_english"],
    ),
]
