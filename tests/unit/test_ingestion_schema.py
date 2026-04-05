from app.ingestion.schema import DATASET_SPECS


def test_dataset_specs_cover_all_expected_files() -> None:
    expected = {
        "olist_customers_dataset.csv",
        "olist_geolocation_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv",
        "olist_order_reviews_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_products_dataset.csv",
        "olist_sellers_dataset.csv",
        "product_category_name_translation.csv",
    }
    actual = {spec.file_name for spec in DATASET_SPECS}
    assert actual == expected


def test_dataset_specs_have_columns() -> None:
    for spec in DATASET_SPECS:
        assert spec.columns
        assert all(column.strip() for column in spec.columns)
