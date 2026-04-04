# API_SPEC

Base URL: `/api/v1`
Auth: `X-API-Key: <shared-key>`

## 1) `POST /query_data`
Purpose: Execute guarded read-only SQL query for trusted analytics data.

Input schema:
```json
{
  "sql": "string (SELECT/CTE only)",
  "limit": "integer 1..5000 (optional, default 500)"
}
```

Output schema:
```json
{
  "executed_sql": "string",
  "row_count": "integer",
  "data": ["object"],
  "warnings": ["string"]
}
```

Example request:
```json
{
  "sql": "SELECT * FROM serving.kpi_overview",
  "limit": 10
}
```

Example response:
```json
{
  "executed_sql": "SELECT * FROM serving.kpi_overview LIMIT 10",
  "row_count": 1,
  "data": [{"gmv": 15843275.45}],
  "warnings": []
}
```

Error cases:
- `400`: unsafe SQL (DML/DDL/semicolon/non-read query)
- `401`: missing or invalid API key
- `500`: unexpected execution failure

Auth assumptions:
- Shared API key for internal MVP usage.

## 2) `POST /search_schema`
Purpose: Discover tables/columns/types by keyword across selected schemas.

Input schema:
```json
{
  "keyword": "string",
  "schemas": ["raw", "staging", "marts", "serving"]
}
```

Output schema:
```json
{
  "keyword": "string",
  "match_count": "integer",
  "matches": [
    {
      "table_schema": "string",
      "table_name": "string",
      "column_name": "string",
      "data_type": "string"
    }
  ]
}
```

Example request:
```json
{
  "keyword": "payment",
  "schemas": ["marts", "serving"]
}
```

Example response:
```json
{
  "keyword": "payment",
  "match_count": 6,
  "matches": [
    {
      "table_schema": "marts",
      "table_name": "fct_payments",
      "column_name": "payment_value",
      "data_type": "numeric"
    }
  ]
}
```

Error cases:
- `401`: missing or invalid API key
- `500`: metadata lookup failure

Auth assumptions:
- Same shared API key model.

## 3) `GET /get_business_definition?term=<term>`
Purpose: Return trusted business glossary definition.

Input schema:
- Query param: `term` (string)

Output schema:
```json
{
  "found": "boolean",
  "definition": "object|null",
  "available_terms": ["string"]
}
```

Example request:
- `GET /api/v1/get_business_definition?term=gmv`

Example response:
```json
{
  "found": true,
  "definition": {
    "term": "Gross Merchandise Value",
    "definition": "Total paid order value before cancellations and refunds in the selected window.",
    "formula": "SUM(payment_value)",
    "source_table": "marts.fct_payments"
  },
  "available_terms": null
}
```

Error cases:
- `401`: missing or invalid API key

Auth assumptions:
- Same shared API key model.

## 4) `POST /get_kpi_summary`
Purpose: Return overview KPI snapshot and monthly trend series.

Input schema:
```json
{
  "start_date": "YYYY-MM-DD|null",
  "end_date": "YYYY-MM-DD|null"
}
```

Output schema:
```json
{
  "overview": {
    "total_orders": "integer",
    "delivered_orders": "integer",
    "delivered_order_rate": "number",
    "gmv": "number",
    "avg_order_value": "number",
    "avg_delivery_delay_days": "number"
  },
  "series": ["object"],
  "series_row_count": "integer"
}
```

Example request:
```json
{
  "start_date": "2017-01-01",
  "end_date": "2018-12-31"
}
```

Example response:
```json
{
  "overview": {
    "total_orders": 99441,
    "delivered_orders": 96478,
    "delivered_order_rate": 0.9702,
    "gmv": 15843275.45,
    "avg_order_value": 159.33,
    "avg_delivery_delay_days": 0.27
  },
  "series": [
    {"month": "2017-01-01", "gmv": 312345.10}
  ],
  "series_row_count": 24
}
```

Error cases:
- `401`: missing or invalid API key
- `500`: serving model not available

Auth assumptions:
- Same shared API key model.

## 5) `POST /run_agent_workflow`
Purpose: Run Supervisor-orchestrated agent workflow on analytics questions.

Input schema:
```json
{
  "question": "string",
  "context": {
    "start_date": "YYYY-MM-DD (optional)",
    "end_date": "YYYY-MM-DD (optional)"
  }
}
```

Output schema:
```json
{
  "intent": "string",
  "selected_tools": ["string"],
  "sql": "string|null",
  "result_summary": "string",
  "confidence": "number 0..1",
  "warnings": ["string"],
  "raw_result": "object"
}
```

Example request:
```json
{
  "question": "show monthly revenue trend",
  "context": {}
}
```

Example response:
```json
{
  "intent": "kpi_summary",
  "selected_tools": ["get_kpi_summary"],
  "sql": null,
  "result_summary": "KPI summary loaded...",
  "confidence": 0.88,
  "warnings": [],
  "raw_result": {
    "overview": {"gmv": 15843275.45}
  }
}
```

Error cases:
- `401`: missing or invalid API key
- `500`: tool execution/runtime error

Auth assumptions:
- Same shared API key model, extensible to OAuth/JWT later.
