from __future__ import annotations

from app.db.client import DatabaseClient

REQUIRED_SERVING_OBJECTS = [
    ("serving", "kpi_overview"),
    ("serving", "kpi_monthly_sales"),
    ("serving", "fct_sales_by_category"),
]


class ServingValidationError(RuntimeError):
    """Raised when required serving objects are missing."""


def validate_serving_layer() -> None:
    db = DatabaseClient()
    check_sql = """
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema = ANY(%(schemas)s)
    """
    rows = db.run_system_query(check_sql, {"schemas": ["serving"]})
    existing = {(row["table_schema"], row["table_name"]) for row in rows}

    missing = [item for item in REQUIRED_SERVING_OBJECTS if item not in existing]
    if missing:
        joined = ", ".join([f"{schema}.{name}" for schema, name in missing])
        raise ServingValidationError(f"Serving layer is incomplete. Missing objects: {joined}")

    print("[SERVING] Validation passed for required serving views.")


def main() -> None:
    validate_serving_layer()


if __name__ == "__main__":
    main()
