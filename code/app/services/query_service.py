from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from app.db.client import DatabaseClient
from app.definitions.business_glossary import BUSINESS_DEFINITIONS


class QueryService:
    def __init__(self) -> None:
        self.db = DatabaseClient()

    def query_data(
        self,
        sql_text: str,
        limit: int = 500,
        params: Sequence[Any] | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        executed_sql, rows = self.db.run_read_query(
            sql_text,
            params=params,
            limit_default=limit,
            limit_max=5000,
        )
        return {
            "executed_sql": executed_sql,
            "row_count": len(rows),
            "data": rows,
            "warnings": [],
        }

    def search_schema(self, keyword: str, schemas: list[str] | None = None) -> dict[str, Any]:
        schemas = schemas or ["raw", "staging", "marts", "serving"]
        sql_text = """
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = ANY(%(schemas)s)
          AND (
              table_name ILIKE %(keyword)s
              OR column_name ILIKE %(keyword)s
          )
        ORDER BY table_schema, table_name, ordinal_position
        LIMIT 300
        """
        rows = self.db.run_system_query(sql_text, {"schemas": schemas, "keyword": f"%{keyword}%"})
        return {
            "keyword": keyword,
            "match_count": len(rows),
            "matches": rows,
        }

    def get_business_definition(self, term: str) -> dict[str, Any]:
        normalized = term.strip().lower()

        if normalized in BUSINESS_DEFINITIONS:
            return {"found": True, "definition": BUSINESS_DEFINITIONS[normalized]}

        for key, value in BUSINESS_DEFINITIONS.items():
            if normalized in key or normalized in value["term"].lower():
                return {"found": True, "definition": value}

        return {
            "found": False,
            "definition": None,
            "available_terms": sorted(BUSINESS_DEFINITIONS.keys()),
        }

    def get_kpi_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        overview_sql = """
        SELECT
            total_orders,
            delivered_orders,
            delivered_order_rate,
            gmv,
            avg_order_value,
            avg_delivery_delay_days
        FROM serving.kpi_overview
        LIMIT 1
        """
        trend_sql = """
        SELECT
            month,
            total_orders,
            delivered_orders,
            gmv,
            avg_order_value
        FROM serving.kpi_monthly_sales
        WHERE (%(start_date)s::date IS NULL OR month >= %(start_date)s::date)
          AND (%(end_date)s::date IS NULL OR month <= %(end_date)s::date)
        ORDER BY month
        """

        overview_rows = self.db.run_system_query(overview_sql)
        trend_rows = self.db.run_system_query(
            trend_sql,
            {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        )

        return {
            "overview": overview_rows[0] if overview_rows else {},
            "series": trend_rows,
            "series_row_count": len(trend_rows),
        }
