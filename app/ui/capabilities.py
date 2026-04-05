from __future__ import annotations

from typing import Any

UI_CAPABILITIES: dict[str, Any] = {
    "assistant_name": "Tro ly Olist Multi-Agent",
    "description": (
        "Trung tam chatbot cho KPI, schema discovery, business glossary va "
        "SQL chi doc co guardrail."
    ),
    "can_do": [
        "Chat tu nhien va tu route dung tool",
        "Tom tat KPI tong quan theo khoang ngay",
        "Chay SQL chi doc tren marts/serving",
        "Tim schema tren raw/staging/marts/serving",
        "Giai thich business term nhu GMV, AOV, delivery delay",
        "Bat/tat tinh nang bang runtime rules",
    ],
    "quick_commands": [
        {"label": "Ban lam duoc gi?", "command": "/help"},
        {"label": "Xu huong doanh thu thang", "command": "show monthly revenue trend"},
        {"label": "Tom tat KPI", "command": "/kpi 2017-01-01 2018-12-31"},
        {"label": "Tra schema", "command": "/schema payment"},
        {"label": "Dinh nghia", "command": "/definition gmv"},
        {"label": "Chay SQL", "command": "/sql SELECT * FROM serving.kpi_overview"},
        {"label": "Tat SQL", "command": "/rule sql off"},
    ],
    "slash_commands": {
        "/help": "Xem kha nang va mau cau hoi.",
        "/kpi <start_date> <end_date>": "Lay KPI summary truc tiep.",
        "/sql <query>": "Chay SQL chi doc co guardrail.",
        "/schema <keyword>": "Tra cuu metadata schema.",
        "/definition <term>": "Lay dinh nghia business term.",
        "/rules": "Xem runtime rules hien tai.",
        "/rule <target> <on|off>": "Cap nhat runtime rules.",
        "/rule sql_limit <1-5000>": "Dat gioi han so dong cho SQL mode.",
        "/rule reset": "Reset rules ve mac dinh.",
    },
    "rule_targets": ["agent", "kpi", "sql", "schema", "definition", "sql_limit"],
    "guardrails": [
        "SQL chi doc va duoc validate bang AST",
        "Chi cho truy van schema marts/serving",
        "Bat buoc gioi han row va statement timeout",
        "Loi duoc tra ve an toan, khong lo credential",
    ],
}
