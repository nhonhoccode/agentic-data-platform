BUSINESS_DEFINITIONS = {
    "gmv": {
        "term": "Gross Merchandise Value",
        "definition": "Total paid order value before cancellations and refunds in the selected window.",
        "formula": "SUM(payment_value)",
        "source_table": "marts.fct_payments",
    },
    "aov": {
        "term": "Average Order Value",
        "definition": "Average payment value per delivered order.",
        "formula": "SUM(payment_value) / COUNT(DISTINCT delivered_order_id)",
        "source_table": "serving.kpi_overview",
    },
    "delivery_delay_days": {
        "term": "Delivery Delay (Days)",
        "definition": "Average number of days between delivered date and estimated date.",
        "formula": "AVG(delivery_delay_days)",
        "source_table": "marts.fct_delivery_performance",
    },
    "delivered_order_rate": {
        "term": "Delivered Order Rate",
        "definition": "Share of delivered orders over all created orders.",
        "formula": "COUNT(delivered_orders) / COUNT(total_orders)",
        "source_table": "serving.kpi_overview",
    },
}

KPI_SQL_MAP = {
    "gmv": "SUM(payment_value) AS value",
    "orders": "COUNT(DISTINCT order_id) AS value",
    "customers": "COUNT(DISTINCT customer_unique_id) AS value",
    "aov": "ROUND(SUM(payment_value) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS value",
}
