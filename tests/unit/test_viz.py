from app.agent.viz import build_chart


def test_build_chart_empty_returns_none() -> None:
    assert build_chart([]) is None


def test_build_chart_picks_priority_value_column() -> None:
    rows = [
        {"category_name_en": "a", "total_revenue": 100, "total_orders": 5},
        {"category_name_en": "b", "total_revenue": 200, "total_orders": 8},
    ]
    chart = build_chart(rows)
    assert chart is not None
    # gmv > total_revenue priority — total_revenue chosen here since gmv missing
    assert chart["value_column"] == "total_revenue"
    assert chart["chart_type"] == "bar"


def test_build_chart_detects_time_series_default_line() -> None:
    rows = [
        {"month": "2018-01-01", "gmv": 100},
        {"month": "2018-02-01", "gmv": 200},
        {"month": "2018-03-01", "gmv": 300},
    ]
    chart = build_chart(rows)
    assert chart is not None
    assert chart["chart_type"] == "line"
    assert chart["value_column"] == "gmv"


def test_build_chart_intent_top_forces_bar_and_sorts_desc() -> None:
    rows = [
        {"category_name_en": "a", "total_revenue": 100},
        {"category_name_en": "b", "total_revenue": 500},
        {"category_name_en": "c", "total_revenue": 300},
    ]
    chart = build_chart(rows, question="top 3 danh muc cao nhat")
    assert chart is not None
    assert chart["chart_type"] == "bar"
    ys = [p["y"] for p in chart["series"]]
    assert ys == [500.0, 300.0, 100.0]


def test_build_chart_intent_trend_forces_line() -> None:
    rows = [
        {"category_name_en": "a", "total_revenue": 100},
        {"category_name_en": "b", "total_revenue": 500},
    ]
    chart = build_chart(rows, question="xu huong doanh thu theo thang")
    assert chart is not None
    assert chart["chart_type"] == "line"


def test_build_chart_returns_none_when_no_numeric() -> None:
    rows = [
        {"name": "a", "city": "x"},
        {"name": "b", "city": "y"},
    ]
    chart = build_chart(rows)
    assert chart is None
