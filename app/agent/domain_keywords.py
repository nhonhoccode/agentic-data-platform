"""Cheap keyword-based domain verdict used as a fallback for the LLM
classifier in `domain_filter.py`."""

from __future__ import annotations

POSITIVE = {
    "gmv", "aov", "cr", "conversion", "churn", "retention", "ltv", "arpu",
    "ecommerce", "e-commerce", "retail", "marketplace", "seller", "buyer",
    "customer", "sku", "catalog", "fulfillment", "logistics",
    "sql", "dbt", "bigquery", "snowflake", "warehouse", "etl", "elt", "airflow",
    "brazil", "sea", "mercadolibre", "shopee", "lazada", "tiki", "olist",
    "doanh thu", "khách hàng", "đơn hàng", "danh mục", "sản phẩm",
}

NEGATIVE = {
    "weather", "thời tiết", "song", "bài hát", "music", "nhạc",
    "football", "bóng đá", "sport", "thể thao", "movie", "phim",
    "game", "trò chơi", "celebrity", "sao việt", "horoscope", "tử vi",
    "sơn tùng", "mtp", "tin tức",
}


def keyword_verdict(q: str) -> bool | None:
    """Return True if positive keyword matched, False if negative,
    None when no keyword applies (caller decides tie-break policy)."""
    ql = (q or "").lower()
    if any(k in ql for k in POSITIVE):
        return True
    if any(k in ql for k in NEGATIVE):
        return False
    return None
