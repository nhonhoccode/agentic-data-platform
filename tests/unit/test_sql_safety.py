import pytest

from app.db.sql_safety import UnsafeQueryError, enforce_limit, validate_read_only_sql


def test_validate_read_only_sql_accepts_select() -> None:
    validate_read_only_sql("SELECT * FROM serving.kpi_overview")


def test_validate_read_only_sql_rejects_unqualified_table() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("SELECT * FROM kpi_overview")


def test_validate_read_only_sql_rejects_non_allowlist_schema() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("SELECT * FROM raw.orders")


def test_validate_read_only_sql_rejects_dml() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("DELETE FROM marts.fct_orders")


def test_validate_read_only_sql_rejects_semicolon() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql("SELECT * FROM serving.kpi_overview; SELECT 2")


def test_enforce_limit_adds_default_limit() -> None:
    bounded = enforce_limit("SELECT * FROM serving.kpi_overview", default_limit=250)
    assert bounded.endswith("LIMIT 250")


def test_enforce_limit_caps_limit() -> None:
    bounded = enforce_limit("SELECT * FROM serving.kpi_overview LIMIT 99999", max_limit=500)
    assert bounded.endswith("LIMIT 500")
