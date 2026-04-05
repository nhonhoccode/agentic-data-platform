from __future__ import annotations

from typing import Any

UI_CAPABILITIES: dict[str, Any] = {
    "assistant_name": "Olist Multi-Agent Assistant",
    "description": (
        "Chatbot command center for KPI, schema discovery, business glossary, and "
        "guarded read-only SQL."
    ),
    "can_do": [
        "Chat naturally and route to the right tool",
        "Summarize KPI overview for a date range",
        "Run read-only SQL only on marts/serving schemas",
        "Search schema across raw/staging/marts/serving",
        "Explain business terms such as GMV, AOV, delivery delay",
        "Apply runtime rules to enable/disable capabilities",
    ],
    "quick_commands": [
        {"label": "What can you do?", "command": "/help"},
        {"label": "Monthly revenue trend", "command": "show monthly revenue trend"},
        {"label": "KPI summary", "command": "/kpi 2017-01-01 2018-12-31"},
        {"label": "Schema lookup", "command": "/schema payment"},
        {"label": "Definition", "command": "/definition gmv"},
        {"label": "Run SQL", "command": "/sql SELECT * FROM serving.kpi_overview"},
        {"label": "Disable SQL", "command": "/rule sql off"},
    ],
    "slash_commands": {
        "/help": "Show capabilities and sample commands.",
        "/kpi <start_date> <end_date>": "Get KPI summary directly.",
        "/sql <query>": "Run read-only SQL query with guardrails.",
        "/schema <keyword>": "Search schema metadata.",
        "/definition <term>": "Get a business term definition.",
        "/rules": "Show active runtime rules.",
        "/rule <target> <on|off>": "Update runtime rules.",
        "/rule sql_limit <1-5000>": "Set query row limit for SQL mode.",
        "/rule reset": "Reset rules to defaults.",
    },
    "rule_targets": ["agent", "kpi", "sql", "schema", "definition", "sql_limit"],
    "guardrails": [
        "SQL is read-only and AST-validated",
        "Only marts/serving schemas are queryable",
        "Query row limits and statement timeout are enforced",
        "Errors are surfaced safely with no credential exposure",
    ],
}
