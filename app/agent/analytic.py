from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return None
    return round(cov / denom, 4)


def correlation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"correlations": [], "note": "Không có dữ liệu"}

    keys = list(rows[0].keys())
    numeric_keys: list[str] = []
    for key in keys:
        sample = [_to_float(row.get(key)) for row in rows[:60]]
        valid = [v for v in sample if v is not None]
        if len(valid) >= max(3, len(sample) * 0.6):
            numeric_keys.append(key)

    correlations: list[dict[str, Any]] = []
    for i, a in enumerate(numeric_keys):
        for b in numeric_keys[i + 1 :]:
            xs: list[float] = []
            ys: list[float] = []
            for row in rows:
                fa = _to_float(row.get(a))
                fb = _to_float(row.get(b))
                if fa is not None and fb is not None:
                    xs.append(fa)
                    ys.append(fb)
            if len(xs) < 3:
                continue
            r = _pearson(xs, ys)
            if r is None:
                continue
            correlations.append({"x": a, "y": b, "pearson": r, "n": len(xs)})

    correlations.sort(key=lambda c: abs(c["pearson"]), reverse=True)
    return {"correlations": correlations[:8], "numeric_columns": numeric_keys}


def drill_down_summary(
    rows: list[dict[str, Any]], dimension: str | None = None, metric: str | None = None
) -> dict[str, Any]:
    if not rows:
        return {"groups": [], "note": "Không có dữ liệu"}

    keys = list(rows[0].keys())
    if dimension is None:
        for cand in ("category_name_en", "month", "order_month", "seller_id", "customer_state"):
            if cand in keys:
                dimension = cand
                break
        if dimension is None:
            dimension = keys[0]

    if metric is None:
        for cand in ("gmv", "total_revenue", "total_orders", "avg_order_value"):
            if cand in keys:
                metric = cand
                break

    groups: dict[str, dict[str, float]] = {}
    for row in rows:
        key = str(row.get(dimension))
        if key not in groups:
            groups[key] = {"sum": 0.0, "count": 0.0}
        if metric:
            value = _to_float(row.get(metric))
            if value is not None:
                groups[key]["sum"] += value
                groups[key]["count"] += 1
        else:
            groups[key]["count"] += 1

    aggregated = [
        {
            "group": k,
            "sum": round(v["sum"], 2),
            "count": int(v["count"]),
            "avg": round(v["sum"] / v["count"], 2) if v["count"] else 0.0,
        }
        for k, v in groups.items()
    ]
    aggregated.sort(key=lambda g: g["sum"], reverse=True)
    return {
        "dimension": dimension,
        "metric": metric,
        "groups": aggregated[:15],
        "total_groups": len(aggregated),
    }


def time_series_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"trend": "no_data"}

    keys = list(rows[0].keys())
    time_key = None
    for cand in ("month", "order_month", "date"):
        if cand in keys:
            time_key = cand
            break
    if time_key is None:
        return {"trend": "no_time_axis"}

    metric_key = None
    for cand in ("gmv", "total_orders", "avg_order_value", "total_revenue"):
        if cand in keys:
            metric_key = cand
            break
    if metric_key is None:
        return {"trend": "no_metric"}

    series = sorted(
        ((row.get(time_key), _to_float(row.get(metric_key))) for row in rows),
        key=lambda p: str(p[0]),
    )
    series = [(t, v) for t, v in series if v is not None]
    if len(series) < 3:
        return {"trend": "insufficient", "points": len(series)}

    first = series[0][1]
    last = series[-1][1]
    direction = "up" if last > first else ("down" if last < first else "flat")
    delta = round(last - first, 2)
    pct = round((last - first) / first * 100, 2) if first else None

    peak = max(series, key=lambda p: p[1])
    trough = min(series, key=lambda p: p[1])

    return {
        "trend": direction,
        "metric": metric_key,
        "time_axis": time_key,
        "first": {"t": series[0][0], "value": first},
        "last": {"t": series[-1][0], "value": last},
        "delta": delta,
        "pct_change": pct,
        "peak": {"t": peak[0], "value": peak[1]},
        "trough": {"t": trough[0], "value": trough[1]},
        "n_points": len(series),
    }
