from __future__ import annotations

import re
from typing import Any


def _is_numeric_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _detect_columns(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    if not rows:
        return [], []
    keys: list[str] = []
    for row in rows[:50]:
        for key in row.keys():
            if key not in keys:
                keys.append(key)

    numeric_cols: list[str] = []
    for key in keys:
        sample = [row.get(key) for row in rows[:50]]
        non_empty = [v for v in sample if v not in (None, "")]
        if not non_empty:
            continue
        if sum(1 for v in non_empty if _is_numeric_value(v)) / len(non_empty) >= 0.6:
            numeric_cols.append(key)

    label_cols = [k for k in keys if k not in numeric_cols]
    return numeric_cols, label_cols


_LABEL_PRIORITY = ("month", "order_month", "date", "category_name_en", "table_name", "column_name")
_VALUE_PRIORITY = (
    "gmv",
    "total_revenue",
    "avg_order_value",
    "total_orders",
    "delivered_orders",
    "late_delivery_rate",
    "avg_delivery_delay_days",
)


def _is_time_series(label_value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}", str(label_value)))


_LINE_HINTS = (
    "trend",
    "xu hướng",
    "xu huong",
    "theo tháng",
    "theo thang",
    "theo quý",
    "theo quy",
    "monthly",
    "weekly",
    "daily",
    "over time",
    "diễn biến",
    "dien bien",
    "tăng giảm",
    "tang giam",
)
_BAR_HINTS = (
    "top",
    "so sánh",
    "so sanh",
    "cao nhất",
    "cao nhat",
    "thấp nhất",
    "thap nhat",
    "ranking",
    "xếp hạng",
    "xep hang",
    "theo danh mục",
    "theo danh muc",
    "theo loại",
    "theo loai",
    "by category",
)


def _intent_chart_type(question: str | None, label_col: str | None, sample_x: str) -> str:
    if question:
        q = question.lower()
        if any(h in q for h in _LINE_HINTS):
            return "line"
        if any(h in q for h in _BAR_HINTS):
            return "bar"
    if label_col and _is_time_series(sample_x):
        return "line"
    return "bar"


def build_chart(
    rows: list[dict[str, Any]], question: str | None = None
) -> dict[str, Any] | None:
    if not rows:
        return None
    numeric_cols, label_cols = _detect_columns(rows)
    if not numeric_cols:
        return None

    value_col = next((c for c in _VALUE_PRIORITY if c in numeric_cols), numeric_cols[0])
    label_col = next(
        (c for c in _LABEL_PRIORITY if c in label_cols),
        label_cols[0] if label_cols else None,
    )

    series: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:30], start=1):
        label = str(row.get(label_col) if label_col else idx)
        value = row.get(value_col)
        try:
            series.append({"x": label, "y": float(value)})
        except (TypeError, ValueError):
            continue

    if len(series) < 2:
        return None

    chart_type = _intent_chart_type(question, label_col, series[0]["x"])

    # For "top N" queries, sort series descending so visualization is intuitive
    if chart_type == "bar" and question and ("top" in question.lower() or "cao nhất" in question.lower() or "cao nhat" in question.lower()):
        series.sort(key=lambda p: p["y"], reverse=True)
        series = series[:15]
    elif chart_type == "line" and label_col and any(_is_time_series(p["x"]) for p in series):
        series.sort(key=lambda p: p["x"])

    return {
        "chart_type": chart_type,
        "label_column": label_col or "index",
        "value_column": value_col,
        "series": series,
        "title": f"{value_col} theo {label_col}" if label_col else value_col,
    }
