from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.agent.core import run_workflow
from app.agent.router import classify_intent
from app.api.v2.schemas import Block, ChatRequest, RuleConfig, TracePayload
from app.services.query_service import QueryService

service = QueryService()
DEFAULT_CHAT_CONTEXT: dict[str, str] = {
    "start_date": "2017-01-01",
    "end_date": "2018-12-31",
}
DEFAULT_SCHEMAS = ["raw", "staging", "marts", "serving"]


def _strip_prefix(text: str, prefixes: list[str]) -> str:
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix) :].strip()
    return text.strip()


def _parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None

    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _merge_context(context: dict[str, Any]) -> dict[str, str | None]:
    merged: dict[str, str | None] = dict(DEFAULT_CHAT_CONTEXT)
    for key in ("start_date", "end_date"):
        value = context.get(key)
        if isinstance(value, date):
            merged[key] = value.isoformat()
        elif value is None:
            continue
        else:
            merged[key] = str(value)
    return merged


def _extract_dates(message: str, context: dict[str, str | None]) -> tuple[date | None, date | None]:
    matches = re.findall(r"\d{4}-\d{2}-\d{2}", message)
    start_text = matches[0] if matches else context.get("start_date")
    end_text = matches[1] if len(matches) > 1 else context.get("end_date")
    return _parse_iso_date(start_text), _parse_iso_date(end_text)


def _is_help_request(message_lower: str) -> bool:
    return (
        message_lower in {"/help", "help"}
        or "what can you do" in message_lower
        or "làm được gì" in message_lower
        or "ban lam duoc gi" in message_lower
    )


def _rules_text(rules: RuleConfig) -> str:
    def status(value: bool) -> str:
        return "on" if value else "off"

    return "\n".join(
        [
            f"- agent: {status(rules.allow_agent)}",
            f"- kpi: {status(rules.allow_kpi)}",
            f"- sql: {status(rules.allow_sql)}",
            f"- schema: {status(rules.allow_schema)}",
            f"- definition: {status(rules.allow_definition)}",
            f"- sql_limit: {rules.sql_limit}",
        ]
    )


def _help_text(rules: RuleConfig) -> str:
    return (
        "Bạn có thể chat tự nhiên hoặc dùng slash command.\n\n"
        "Commands: /help, /kpi, /sql, /schema, /definition, /rules, /rule ...\n\n"
        f"Active rules:\n{_rules_text(rules)}"
    )


def _bool_from_token(token: str) -> bool | None:
    lowered = token.strip().lower()
    if lowered in {"on", "true", "1", "yes", "allow", "enabled"}:
        return True
    if lowered in {"off", "false", "0", "no", "deny", "disabled"}:
        return False
    return None


def _apply_rule_command(message: str, rules: RuleConfig) -> tuple[RuleConfig, str]:
    body = _strip_prefix(
        message,
        ["/rule ", "rule ", "set rule ", "đặt rule ", "dat rule ", "/rule", "rule"],
    )
    if not body:
        return (
            rules,
            "Usage: /rule <agent|kpi|sql|schema|definition> <on|off> | /rule sql_limit <1-5000> | /rule reset",
        )

    tokens = body.split()
    key = tokens[0].lower()

    if key in {"reset", "default"}:
        return RuleConfig(), "Rules reset to default values."

    if key in {"show", "status", "list"}:
        return rules, f"Active rules:\n{_rules_text(rules)}"

    key_map = {
        "agent": "allow_agent",
        "kpi": "allow_kpi",
        "sql": "allow_sql",
        "schema": "allow_schema",
        "definition": "allow_definition",
        "define": "allow_definition",
        "sql_limit": "sql_limit",
        "limit": "sql_limit",
    }
    target = key_map.get(key)
    if target is None:
        return rules, "Unknown rule target. Use: agent, kpi, sql, schema, definition, sql_limit."

    updated = rules.model_dump()
    if target == "sql_limit":
        if len(tokens) < 2:
            return rules, "Usage: /rule sql_limit <1-5000>"
        try:
            limit = int(tokens[1])
        except ValueError:
            return rules, "sql_limit must be an integer between 1 and 5000."
        if not 1 <= limit <= 5000:
            return rules, "sql_limit must be between 1 and 5000."
        updated["sql_limit"] = limit
        return RuleConfig(**updated), f"Updated rule: sql_limit={limit}."

    if len(tokens) < 2:
        return rules, f"Usage: /rule {key} <on|off>"

    value = _bool_from_token(tokens[1])
    if value is None:
        return rules, "Rule value must be on/off (or true/false)."

    updated[target] = value
    status = "on" if value else "off"
    return RuleConfig(**updated), f"Updated rule: {key}={status}."


def _infer_table_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows[:200]:
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    return columns


def _table_block(rows: list[dict[str, Any]], title: str | None = None) -> Block | None:
    if not rows:
        return None
    columns = _infer_table_columns(rows)
    if not columns:
        return None
    return Block(
        type="table",
        title=title,
        payload={
            "columns": columns,
            "rows": rows[:200],
            "row_count": len(rows),
        },
    )


def _figure_block(rows: list[dict[str, Any]], title: str | None = None) -> Block | None:
    if not rows:
        return None

    sample = rows[:50]
    keys: list[str] = []
    for row in sample:
        for key in row.keys():
            if key not in keys:
                keys.append(key)

    numeric_cols: list[str] = []
    for key in keys:
        valid = 0
        total = 0
        for row in sample:
            value = row.get(key)
            if value is None or value == "":
                continue
            total += 1
            try:
                float(value)
                valid += 1
            except (TypeError, ValueError):
                continue
        if total and valid / total >= 0.6:
            numeric_cols.append(key)

    if not numeric_cols:
        return None

    preferred_numeric = ["gmv", "total_revenue", "total_orders", "delivered_orders", "avg_order_value"]
    value_col = next((key for key in preferred_numeric if key in numeric_cols), numeric_cols[0])

    label_candidates = [key for key in keys if key not in numeric_cols]
    preferred_labels = ["month", "date", "order_month", "category_name_en", "table_name", "column_name"]
    label_col = next((key for key in preferred_labels if key in label_candidates), None)

    points: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:24], start=1):
        try:
            value = float(row.get(value_col))
        except (TypeError, ValueError):
            continue
        label = str(row.get(label_col) if label_col else idx)
        points.append({"x": label, "y": value})

    if len(points) < 2:
        return None

    return Block(
        type="figure",
        title=title or f"{value_col} trend",
        payload={
            "chart": "bar",
            "x_key": "x",
            "y_key": "y",
            "series": points,
            "label_column": label_col or "index",
            "value_column": value_col,
        },
    )


def _trace(
    *,
    intent: str,
    selected_tools: list[str] | None = None,
    sql: str | None = None,
    confidence: float | None = None,
    warnings: list[str] | None = None,
    blocked: bool = False,
) -> TracePayload:
    return TracePayload(
        inferred_intent=intent,
        selected_tools=selected_tools or [],
        sql=sql,
        confidence=confidence,
        warnings=warnings or [],
        blocked=blocked,
    )


def run_chat(payload: ChatRequest) -> dict[str, Any]:
    message = payload.message.strip()
    rules = payload.rules
    message_lower = message.lower()
    context = _merge_context(payload.context)

    if _is_help_request(message_lower):
        return {
            "mode": "help",
            "assistant_message": _help_text(rules),
            "active_rules": rules,
            "blocks": [Block(type="text", payload={"text": _help_text(rules)})],
            "trace": _trace(intent="help_request"),
        }

    if message_lower in {"/rules", "rules", "show rules", "xem rules"}:
        text = f"Current runtime rules:\n{_rules_text(rules)}"
        return {
            "mode": "rules",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": [Block(type="text", payload={"text": text})],
            "trace": _trace(intent="rules"),
        }

    if (
        message_lower.startswith("/rule")
        or message_lower.startswith("rule ")
        or message_lower.startswith("set rule")
        or message_lower.startswith("đặt rule")
        or message_lower.startswith("dat rule")
    ):
        updated_rules, text = _apply_rule_command(message, rules)
        return {
            "mode": "rules_update",
            "assistant_message": text,
            "active_rules": updated_rules,
            "blocks": [Block(type="text", payload={"text": text})],
            "trace": _trace(intent="rules_update"),
        }

    if message_lower.startswith("/sql") or message_lower.startswith("sql:"):
        if not rules.allow_sql:
            text = "Blocked by active rule: SQL is disabled (`allow_sql=off`)."
            return {
                "mode": "sql",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": [text]})],
                "trace": _trace(intent="sql_query", blocked=True, warnings=[text]),
            }

        sql_text = _strip_prefix(message, ["/sql ", "sql:", "/sql"])
        if not sql_text:
            text = "Usage: /sql <SELECT query>"
            return {
                "mode": "sql",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": ["missing_sql"]})],
                "trace": _trace(intent="sql_query", warnings=["missing_sql"]),
            }

        result = service.query_data(sql_text, limit=rules.sql_limit)
        rows = result.get("data", [])
        blocks: list[Block] = [
            Block(type="text", payload={"text": f"SQL executed successfully. Returned {len(rows)} rows."})
        ]
        table = _table_block(rows, title="Query Results")
        figure = _figure_block(rows, title="Auto Figure")
        if table:
            blocks.append(table)
        if figure:
            blocks.append(figure)

        return {
            "mode": "sql",
            "assistant_message": f"SQL executed successfully. Returned {len(rows)} rows.",
            "active_rules": rules,
            "blocks": blocks,
            "trace": _trace(
                intent="sql_query",
                selected_tools=["query_data"],
                sql=result.get("executed_sql"),
            ),
        }

    if message_lower.startswith("/schema") or message_lower.startswith("schema:"):
        if not rules.allow_schema:
            text = "Blocked by active rule: schema search is disabled (`allow_schema=off`)."
            return {
                "mode": "schema",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": [text]})],
                "trace": _trace(intent="schema_search", blocked=True, warnings=[text]),
            }

        keyword = _strip_prefix(message, ["/schema ", "schema:", "/schema"])
        if not keyword:
            text = "Usage: /schema <keyword>"
            return {
                "mode": "schema",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": ["missing_keyword"]})],
                "trace": _trace(intent="schema_search", warnings=["missing_keyword"]),
            }

        result = service.search_schema(keyword, schemas=DEFAULT_SCHEMAS)
        rows = result.get("matches", [])
        blocks: list[Block] = [
            Block(type="text", payload={"text": f"Found {len(rows)} schema matches for '{keyword}'."})
        ]
        table = _table_block(rows, title="Schema Matches")
        if table:
            blocks.append(table)

        return {
            "mode": "schema",
            "assistant_message": f"Found {len(rows)} schema matches for '{keyword}'.",
            "active_rules": rules,
            "blocks": blocks,
            "trace": _trace(intent="schema_search", selected_tools=["search_schema"]),
        }

    if (
        message_lower.startswith("/definition")
        or message_lower.startswith("definition:")
        or message_lower.startswith("/define")
        or message_lower.startswith("define ")
        or message_lower.startswith("define:")
    ):
        if not rules.allow_definition:
            text = "Blocked by active rule: business definition is disabled (`allow_definition=off`)."
            return {
                "mode": "definition",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": [text]})],
                "trace": _trace(intent="business_definition", blocked=True, warnings=[text]),
            }

        term = _strip_prefix(
            message,
            ["/definition ", "definition:", "/define ", "define ", "define:", "/definition", "/define"],
        )
        if not term:
            text = "Usage: /definition <term>"
            return {
                "mode": "definition",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": ["missing_term"]})],
                "trace": _trace(intent="business_definition", warnings=["missing_term"]),
            }

        result = service.get_business_definition(term)
        if result.get("found"):
            definition = result.get("definition", {})
            text = f"{definition.get('term')}: {definition.get('definition')}"
        else:
            text = "Definition not found. Check available terms."

        return {
            "mode": "definition",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": [Block(type="text", payload={"text": text})],
            "trace": _trace(intent="business_definition", selected_tools=["get_business_definition"]),
        }

    if message_lower.startswith("/kpi") or message_lower.startswith("kpi:"):
        if not rules.allow_kpi:
            text = "Blocked by active rule: KPI summary is disabled (`allow_kpi=off`)."
            return {
                "mode": "kpi",
                "assistant_message": text,
                "active_rules": rules,
                "blocks": [Block(type="warnings", payload={"warnings": [text]})],
                "trace": _trace(intent="kpi_summary", blocked=True, warnings=[text]),
            }

        start_date, end_date = _extract_dates(message, context)
        result = service.get_kpi_summary(start_date=start_date, end_date=end_date)
        overview = result.get("overview", {})
        series = result.get("series", [])
        text = (
            "KPI summary loaded: "
            f"orders={overview.get('total_orders')}, gmv={overview.get('gmv')}, "
            f"delivered_rate={overview.get('delivered_order_rate')}"
        )

        blocks: list[Block] = [Block(type="text", payload={"text": text})]
        if overview:
            ov_table = _table_block([overview], title="KPI Overview")
            if ov_table:
                blocks.append(ov_table)
        series_table = _table_block(series, title="KPI Series")
        series_figure = _figure_block(series, title="KPI Trend")
        if series_table:
            blocks.append(series_table)
        if series_figure:
            blocks.append(series_figure)

        return {
            "mode": "kpi",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": blocks,
            "trace": _trace(intent="kpi_summary", selected_tools=["get_kpi_summary"]),
        }

    inferred_intent = classify_intent(message)
    if inferred_intent == "chitchat":
        text = (
            "Mình đang online. Bạn có thể hỏi tự nhiên về KPI/query/dashboard/schema/definition, "
            "hoặc dùng /help để xem command."
        )
        return {
            "mode": "chitchat",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": [Block(type="text", payload={"text": text})],
            "trace": _trace(intent=inferred_intent),
        }

    if inferred_intent == "help_request":
        text = _help_text(rules)
        return {
            "mode": "help",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": [Block(type="text", payload={"text": text})],
            "trace": _trace(intent=inferred_intent),
        }

    if not rules.allow_agent:
        text = "Blocked by active rule: natural-language agent workflow is disabled (`allow_agent=off`)."
        return {
            "mode": "agent",
            "assistant_message": text,
            "active_rules": rules,
            "blocks": [Block(type="warnings", payload={"warnings": [text]})],
            "trace": _trace(intent=inferred_intent, blocked=True, warnings=[text]),
        }

    blocked_by_intent = {
        "sql_query": (not rules.allow_sql, "Natural-language SQL intent is disabled (`allow_sql=off`)."),
        "schema_search": (not rules.allow_schema, "Schema intent is disabled (`allow_schema=off`)."),
        "business_definition": (
            not rules.allow_definition,
            "Business definition intent is disabled (`allow_definition=off`).",
        ),
        "kpi_summary": (not rules.allow_kpi, "KPI intent is disabled (`allow_kpi=off`)."),
    }
    is_blocked, reason = blocked_by_intent.get(inferred_intent, (False, ""))
    if is_blocked:
        return {
            "mode": "agent",
            "assistant_message": f"Blocked by active rule: {reason}",
            "active_rules": rules,
            "blocks": [Block(type="warnings", payload={"warnings": [reason]})],
            "trace": _trace(intent=inferred_intent, blocked=True, warnings=[reason]),
        }

    result = run_workflow(message, context)
    raw_result = result.get("raw_result") or {}
    rows = []
    if isinstance(raw_result, dict):
        if isinstance(raw_result.get("data"), list):
            rows = raw_result.get("data", [])
        elif isinstance(raw_result.get("matches"), list):
            rows = raw_result.get("matches", [])
        elif isinstance(raw_result.get("series"), list):
            rows = raw_result.get("series", [])

    blocks: list[Block] = [
        Block(type="text", payload={"text": result.get("result_summary", "Workflow completed.")})
    ]
    table = _table_block(rows, title="Agent Results")
    figure = _figure_block(rows, title="Auto Figure")
    if table:
        blocks.append(table)
    if figure:
        blocks.append(figure)
    if result.get("warnings"):
        blocks.append(Block(type="warnings", payload={"warnings": result.get("warnings", [])}))

    return {
        "mode": "agent",
        "assistant_message": result.get("result_summary", "Workflow completed."),
        "active_rules": rules,
        "blocks": blocks,
        "trace": _trace(
            intent=inferred_intent,
            selected_tools=result.get("selected_tools", []),
            sql=result.get("sql"),
            confidence=result.get("confidence"),
            warnings=result.get("warnings", []),
        ),
    }


def run_query(sql_text: str, limit: int) -> dict[str, Any]:
    result = service.query_data(sql_text, limit=limit)
    rows = result.get("data", [])
    columns = _infer_table_columns(rows)
    return {
        "executed_sql": result.get("executed_sql", ""),
        "row_count": int(result.get("row_count", 0)),
        "columns": columns,
        "rows": rows,
        "warnings": result.get("warnings", []),
    }


def get_dashboard(start_date: date | None, end_date: date | None, top_categories_limit: int) -> dict[str, Any]:
    kpi_result = service.get_kpi_summary(start_date=start_date, end_date=end_date)
    warnings: list[str] = []
    top_categories: list[dict[str, Any]] = []

    try:
        top_categories_sql = """
        SELECT
            category_name_en,
            total_orders,
            total_revenue,
            avg_item_value
        FROM serving.fct_sales_by_category
        ORDER BY total_revenue DESC
        LIMIT %(limit)s
        """
        top_categories = service.db.run_system_query(top_categories_sql, {"limit": top_categories_limit})
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Top categories unavailable: {exc}")

    return {
        "context": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "overview": kpi_result.get("overview", {}),
        "series": kpi_result.get("series", []),
        "series_row_count": int(kpi_result.get("series_row_count", 0)),
        "top_categories": top_categories,
        "warnings": warnings,
    }
