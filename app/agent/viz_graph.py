"""Viz Agent sub-graph (code generation + self-correction).

Diagram:
    __start__ → code_generation → code_execution
                         ↑               ↓
                         └─ code_fixbug ─┘
                                          ↓
                                       __end__

`code_generation` picks a chart spec (LLM if available, deterministic fallback otherwise).
`code_execution` validates the spec against the rows and builds the final chart payload.
`code_fixbug` records the failure and loops back to regenerate (max 2 attempts).
"""

from __future__ import annotations

import json
import re
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agent.llm import llm_invoke_text
from app.agent.viz import build_chart, _detect_columns

MAX_VIZ_FIX_ATTEMPTS = 2


class VizState(TypedDict, total=False):
    rows: list[dict[str, Any]]
    question: str
    spec: dict[str, Any]
    chart: dict[str, Any] | None
    error: str | None
    attempts: int
    history: list[dict[str, str]]
    selected_tools: list[str]


_SPEC_PROMPT_TEMPLATE = """Bạn là chuyên gia visualisation. Chọn đúng 1 chart spec cho dữ liệu sau.

Câu hỏi người dùng: {question}

Mẫu dữ liệu (3 dòng đầu):
{sample}

Cột numeric phát hiện: {numeric_cols}
Cột label phát hiện: {label_cols}

Quy tắc:
- chart_type: "line" cho time-series/trend, "bar" cho top/so sánh/ranking.
- value_column: tên cột numeric muốn vẽ trên trục Y.
- label_column: tên cột label trên trục X.

Trả lời CHỈ là JSON đúng format:
{{"chart_type": "bar|line", "value_column": "...", "label_column": "..."}}"""


_FIX_PROMPT_TEMPLATE = """Spec trước bị lỗi khi build chart. Sửa để chạy được.

Câu hỏi: {question}
Cột có trong data: numeric={numeric_cols}, label={label_cols}

Spec lỗi: {spec}
Lỗi: {error}

Trả lời CHỈ JSON: {{"chart_type": "bar|line", "value_column": "...", "label_column": "..."}}"""


def _strip_json(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _heuristic_spec(rows: list[dict[str, Any]], question: str) -> dict[str, Any]:
    """Deterministic fallback when LLM unavailable."""
    chart = build_chart(rows, question=question)
    if chart is None:
        return {}
    return {
        "chart_type": chart["chart_type"],
        "value_column": chart["value_column"],
        "label_column": chart["label_column"],
    }


def _code_generation_node(state: VizState) -> VizState:
    rows = state.get("rows", [])
    if not rows:
        return {**state, "spec": {}, "error": "no_rows"}

    numeric_cols, label_cols = _detect_columns(rows)
    if not numeric_cols:
        return {**state, "spec": {}, "error": "no_numeric_columns"}

    error = state.get("error")
    history = state.get("history", [])
    sample = json.dumps(rows[:3], default=str, ensure_ascii=False)

    if error and history:
        prompt = _FIX_PROMPT_TEMPLATE.format(
            question=state.get("question", ""),
            numeric_cols=numeric_cols,
            label_cols=label_cols,
            spec=json.dumps(state.get("spec", {})),
            error=error,
        )
    else:
        prompt = _SPEC_PROMPT_TEMPLATE.format(
            question=state.get("question", ""),
            sample=sample,
            numeric_cols=numeric_cols,
            label_cols=label_cols,
        )

    raw = llm_invoke_text(prompt)
    spec: dict[str, Any] = {}
    if raw:
        try:
            spec = json.loads(_strip_json(raw))
        except json.JSONDecodeError:
            spec = {}

    if not spec or "value_column" not in spec:
        spec = _heuristic_spec(rows, state.get("question", ""))

    return {
        **state,
        "spec": spec,
        "error": None,
        "selected_tools": [*state.get("selected_tools", []), "viz_code_gen"],
    }


def _code_execution_node(state: VizState) -> VizState:
    spec = state.get("spec") or {}
    rows = state.get("rows", [])

    if not spec or "value_column" not in spec:
        return {**state, "chart": None, "error": "empty_spec"}

    value_col = spec["value_column"]
    label_col = spec.get("label_column")
    chart_type = spec.get("chart_type", "bar")

    if not rows:
        return {**state, "chart": None, "error": "no_rows"}
    if value_col not in rows[0]:
        return {**state, "chart": None, "error": f"value_column_not_found: {value_col}"}
    if label_col and label_col not in rows[0]:
        return {**state, "chart": None, "error": f"label_column_not_found: {label_col}"}

    series: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:30], start=1):
        try:
            y = float(row.get(value_col))
        except (TypeError, ValueError):
            continue
        x = str(row.get(label_col) if label_col else idx)
        series.append({"x": x, "y": y})

    if len(series) < 2:
        return {**state, "chart": None, "error": "not_enough_points"}

    if chart_type == "bar":
        question = (state.get("question") or "").lower()
        if "top" in question or "cao nhất" in question or "cao nhat" in question:
            series.sort(key=lambda p: p["y"], reverse=True)
            series = series[:15]
    elif chart_type == "line" and label_col:
        if all(re.match(r"^\d{4}-\d{2}", p["x"]) for p in series):
            series.sort(key=lambda p: p["x"])

    chart = {
        "chart_type": chart_type if chart_type in {"bar", "line"} else "bar",
        "value_column": value_col,
        "label_column": label_col or "index",
        "series": series,
        "title": f"{value_col} theo {label_col}" if label_col else value_col,
    }
    return {
        **state,
        "chart": chart,
        "error": None,
        "selected_tools": [*state.get("selected_tools", []), "viz_code_exec"],
    }


def _code_fixbug_node(state: VizState) -> VizState:
    history = list(state.get("history", []))
    history.append(
        {"spec": json.dumps(state.get("spec", {})), "error": state.get("error", "")}
    )
    return {
        **state,
        "attempts": state.get("attempts", 0) + 1,
        "history": history,
        "selected_tools": [*state.get("selected_tools", []), "viz_fixbug"],
    }


def _post_exec_router(state: VizState) -> str:
    if not state.get("error"):
        return "ok"
    if state.get("attempts", 0) >= MAX_VIZ_FIX_ATTEMPTS:
        return "give_up"
    return "fix"


def build_viz_graph() -> Any:
    graph = StateGraph(VizState)
    graph.add_node("code_generation", _code_generation_node)
    graph.add_node("code_execution", _code_execution_node)
    graph.add_node("code_fixbug", _code_fixbug_node)

    graph.add_edge(START, "code_generation")
    graph.add_edge("code_generation", "code_execution")
    graph.add_conditional_edges(
        "code_execution",
        _post_exec_router,
        {"ok": END, "fix": "code_fixbug", "give_up": END},
    )
    graph.add_edge("code_fixbug", "code_generation")
    return graph.compile()


_GRAPH = build_viz_graph()


def run_viz_graph(rows: list[dict[str, Any]], question: str) -> dict[str, Any]:
    initial: VizState = {
        "rows": rows,
        "question": question,
        "attempts": 0,
        "history": [],
        "selected_tools": [],
    }
    final = _GRAPH.invoke(initial)
    return {
        "chart": final.get("chart"),
        "spec": final.get("spec"),
        "error": final.get("error"),
        "attempts": final.get("attempts", 0),
        "selected_tools": final.get("selected_tools", []),
    }
