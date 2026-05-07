from app.agent.analytic import correlation_summary, drill_down_summary, time_series_summary


def test_time_series_summary_detects_uptrend() -> None:
    rows = [
        {"month": "2017-01-01", "gmv": 100},
        {"month": "2017-02-01", "gmv": 150},
        {"month": "2017-03-01", "gmv": 250},
        {"month": "2017-04-01", "gmv": 400},
    ]
    out = time_series_summary(rows)
    assert out["trend"] == "up"
    assert out["metric"] == "gmv"
    assert out["pct_change"] == 300.0
    assert out["peak"]["value"] == 400.0
    assert out["trough"]["value"] == 100.0


def test_time_series_summary_no_time_axis() -> None:
    rows = [{"category": "a", "value": 10}]
    out = time_series_summary(rows)
    assert out["trend"] == "no_time_axis"


def test_drill_down_summary_groups_correctly() -> None:
    rows = [
        {"category_name_en": "a", "gmv": 100},
        {"category_name_en": "a", "gmv": 50},
        {"category_name_en": "b", "gmv": 200},
    ]
    out = drill_down_summary(rows)
    assert out["dimension"] == "category_name_en"
    assert out["metric"] == "gmv"
    groups = {g["group"]: g["sum"] for g in out["groups"]}
    assert groups["a"] == 150.0
    assert groups["b"] == 200.0


def test_correlation_summary_finds_strong_correlation() -> None:
    rows = [
        {"x": 1, "y": 2, "z": 5},
        {"x": 2, "y": 4, "z": 5},
        {"x": 3, "y": 6, "z": 5},
        {"x": 4, "y": 8, "z": 5},
        {"x": 5, "y": 10, "z": 5},
    ]
    out = correlation_summary(rows)
    pairs = {(c["x"], c["y"]): c["pearson"] for c in out["correlations"]}
    assert pairs.get(("x", "y"), 0) > 0.99


def test_correlation_summary_empty() -> None:
    assert correlation_summary([])["correlations"] == []
