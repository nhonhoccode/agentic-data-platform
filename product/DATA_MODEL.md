# DATA_MODEL

## Main Entities
- Customer: identity and geographic attributes.
- Order: lifecycle timestamps and status.
- Order Item: product-level line items and seller linkage.
- Payment: payment method and value per order.
- Review: customer sentiment and score.
- Product: category and physical attributes.
- Seller: merchant location profile.
- Category Translation: Portuguese to English category mapping.

## Table Relationships
- `orders.customer_id -> customers.customer_id`
- `order_items.order_id -> orders.order_id`
- `order_items.product_id -> products.product_id`
- `order_items.seller_id -> sellers.seller_id`
- `order_payments.order_id -> orders.order_id`
- `order_reviews.order_id -> orders.order_id`
- `products.product_category_name -> product_category_translation.product_category_name`

## Grain of Important Tables
- `raw.orders`: one row per order.
- `raw.order_items`: one row per order item within an order.
- `staging.stg_orders`: one row per order (typed).
- `marts.fct_orders`: one row per order with aggregated financial metrics.
- `marts.fct_order_items`: one row per item enriched with category.
- `marts.kpi_monthly_sales`: one row per month.
- `serving.kpi_overview`: one row summary for global KPI snapshot.

## Primary and Foreign Keys
- Primary keys:
  - `customer_id`, `order_id`, `product_id`, `seller_id` in corresponding entities.
  - composite key (`order_id`, `order_item_id`) for order items.
- Foreign keys are enforced through dbt relationship tests in MVP.

## Layer Interpretation
- Raw:
  - Landing zone, source-accurate, minimal assumptions.
- Staging:
  - Type conversions, null normalization, naming cleanup.
- Marts:
  - Business logic and analytical grain definitions.
- Serving:
  - Stable, business-consumable views for API/agents.

## Business-Friendly Explanation
- Raw holds what came in.
- Staging makes data trustworthy.
- Marts makes data useful.
- Serving makes data easy and safe for applications and AI agents.

## Data Quality Rules
- Not null keys for core entities (`order_id`, `customer_id`, `product_id`).
- Uniqueness checks on primary grains (e.g., `stg_orders.order_id`).
- Relationship checks between orders/items/payments/customers.
- Timestamp and numeric fields casted from raw text with null-safe conversion.
- Serving validation requires key views to exist before API workflows proceed.

## KPI-Ready Marts Recommendations
- `marts.kpi_overview`: total orders, delivered orders, delivered rate, GMV, AOV, avg delivery delay.
- `marts.kpi_monthly_sales`: monthly trend for order and revenue analytics.
- `marts.fct_sales_by_category`: category-level contribution and average item value.
- `marts.delivery_performance_monthly`: delivery SLA trend and late-rate tracking.
