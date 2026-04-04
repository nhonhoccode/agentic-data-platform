from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agent.core import run_workflow
from app.agent.router import classify_intent
from app.api.schemas import (
    AgentWorkflowRequest,
    AgentWorkflowResponse,
    BusinessDefinitionResponse,
    KpiSummaryRequest,
    KpiSummaryResponse,
    QueryDataRequest,
    QueryDataResponse,
    SearchSchemaRequest,
    SearchSchemaResponse,
)
from app.db.sql_safety import UnsafeQueryError
from app.services.query_service import QueryService

router = APIRouter(prefix="/ui", tags=["ui"])
service = QueryService()

DATA_NOT_READY_HINT = (
    "Data platform may not be initialized yet. "
    "Check bootstrap logs with: docker compose logs -f bootstrap"
)

DEFAULT_CHAT_CONTEXT: dict[str, str] = {
    "start_date": "2017-01-01",
    "end_date": "2018-12-31",
}
DEFAULT_SCHEMAS = ["raw", "staging", "marts", "serving"]

UI_CAPABILITIES: dict[str, Any] = {
    "assistant_name": "Olist Multi-Agent Assistant",
    "description": (
        "Chatbot command center for KPI, agent insights, schema discovery, "
        "business glossary, and read-only SQL."
    ),
    "can_do": [
        "Chat naturally and route to the right tool",
        "Summarize KPI overview for a date range",
        "Run guarded read-only SQL on trusted serving/marts data",
        "Search schema across raw/staging/marts/serving",
        "Explain business terms like GMV and delivery metrics",
        "Apply runtime rules to allow/deny specific capabilities",
    ],
    "quick_commands": [
        {"label": "What can you do?", "command": "/help"},
        {"label": "Ask naturally", "command": "show monthly revenue trend and key insights"},
        {"label": "KPI overview", "command": "/kpi 2017-01-01 2018-12-31"},
        {"label": "Schema lookup", "command": "/schema payment"},
        {"label": "Business definition", "command": "/definition gmv"},
        {"label": "Run SQL", "command": "/sql SELECT * FROM serving.kpi_overview"},
        {"label": "Show rules", "command": "/rules"},
        {"label": "Disable SQL", "command": "/rule sql off"},
    ],
    "slash_commands": {
        "/help": "Show capabilities and sample commands.",
        "/kpi <start_date> <end_date>": "Get KPI summary directly (dates optional; format YYYY-MM-DD).",
        "/sql <query>": "Run a read-only SQL query with guardrails.",
        "/schema <keyword>": "Search schema metadata by keyword.",
        "/definition <term>": "Get a business term definition.",
        "/rules": "Show active runtime rules.",
        "/rule <target> <on|off>": "Update rules. Targets: agent, kpi, sql, schema, definition.",
        "/rule sql_limit <1-5000>": "Set SQL result row limit.",
        "/rule reset": "Reset rules to defaults.",
    },
    "guardrails": [
        "SQL is read-only and safety-checked",
        "Query result row limits are enforced",
        "Errors are surfaced safely with no credentials exposure",
    ],
}


class UiRuleConfig(BaseModel):
    allow_agent: bool = True
    allow_kpi: bool = True
    allow_sql: bool = True
    allow_schema: bool = True
    allow_definition: bool = True
    sql_limit: int = Field(default=500, ge=1, le=5000)


class UiChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    rules: UiRuleConfig = Field(default_factory=UiRuleConfig)


class UiChatResponse(BaseModel):
    mode: str
    assistant_message: str
    active_rules: UiRuleConfig
    blocked: bool = False
    warnings: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{DATA_NOT_READY_HINT}. Error: {exc}")


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


def _rules_text(rules: UiRuleConfig) -> str:
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


def _help_text(rules: UiRuleConfig) -> str:
    return (
        "Bạn có thể chat tự nhiên hoặc dùng lệnh ngắn.\n\n"
        "Lệnh nhanh:\n"
        "/help, /kpi, /sql, /schema, /definition, /rules, /rule ...\n\n"
        "Active rules:\n"
        f"{_rules_text(rules)}"
    )


def _bool_from_token(token: str) -> bool | None:
    lowered = token.strip().lower()
    if lowered in {"on", "true", "1", "yes", "allow", "enabled"}:
        return True
    if lowered in {"off", "false", "0", "no", "deny", "disabled"}:
        return False
    return None


def _apply_rule_command(message: str, rules: UiRuleConfig) -> tuple[UiRuleConfig, str]:
    body = _strip_prefix(
        message,
        [
            "/rule ",
            "rule ",
            "set rule ",
            "đặt rule ",
            "dat rule ",
            "/rule",
            "rule",
        ],
    )

    if not body:
        return (
            rules,
            "Usage: /rule <agent|kpi|sql|schema|definition> <on|off> | "
            "/rule sql_limit <1-5000> | /rule reset",
        )

    tokens = body.split()
    key = tokens[0].lower()

    if key in {"reset", "default"}:
        return UiRuleConfig(), "Rules reset to default values."

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
        return (
            rules,
            "Unknown rule target. Use: agent, kpi, sql, schema, definition, sql_limit.",
        )

    updated_data = rules.model_dump()

    if target == "sql_limit":
        if len(tokens) < 2:
            return rules, "Usage: /rule sql_limit <1-5000>"

        try:
            limit = int(tokens[1])
        except ValueError:
            return rules, "sql_limit must be an integer between 1 and 5000."

        if not 1 <= limit <= 5000:
            return rules, "sql_limit must be between 1 and 5000."

        updated_data["sql_limit"] = limit
        updated = UiRuleConfig(**updated_data)
        return updated, f"Updated rule: sql_limit={limit}."

    if len(tokens) < 2:
        return rules, f"Usage: /rule {key} <on|off>"

    value = _bool_from_token(tokens[1])
    if value is None:
        return rules, "Rule value must be on/off (or true/false)."

    updated_data[target] = value
    updated = UiRuleConfig(**updated_data)
    status = "on" if value else "off"
    return updated, f"Updated rule: {key}={status}."


def _blocked_response(mode: str, rules: UiRuleConfig, reason: str) -> UiChatResponse:
    return UiChatResponse(
        mode=mode,
        assistant_message=f"Blocked by active rule: {reason}",
        active_rules=rules,
        blocked=True,
        warnings=[reason],
    )


@router.get("", response_class=HTMLResponse)
def ui_home() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Olist Data Platform Demo UI</title>
  <style>
    :root {
      --bg: #f7f4ed;
      --panel: #ffffff;
      --ink: #12263a;
      --accent: #067d68;
      --accent-soft: #cdeee8;
      --danger: #ad1f1f;
      --muted: #4f6373;
      --border: #d6e2e9;
      --chip-bg: #ebf6ff;
      --chip-ink: #0a4c73;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, #f2f8ff 0%, var(--bg) 50%);
    }
    .shell {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 14px;
    }
    .hero {
      background: linear-gradient(140deg, #0f7f6f, #0f4f6f);
      border-radius: 14px;
      color: #fff;
      padding: 18px;
    }
    .hero h1 { margin: 0 0 8px; font-size: 24px; }
    .hero p { margin: 0; opacity: 0.92; }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 3px 12px rgba(18, 38, 58, 0.08);
    }
    .card h2 {
      margin-top: 0;
      margin-bottom: 6px;
      font-size: 16px;
      color: #0a4c73;
    }
    .pill {
      display: inline-block;
      background: var(--accent-soft);
      color: #0a5f52;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
    }
    .status {
      margin-top: 8px;
      font-size: 13px;
      color: #e7f6f3;
    }
    .status.error {
      color: #ffd6d6;
      font-weight: 600;
    }
    .helper {
      margin: 6px 0 0;
      font-size: 12px;
      color: var(--muted);
    }
    .chat-log {
      margin-top: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      min-height: 280px;
      max-height: 480px;
      overflow-y: auto;
      background: #fafbfd;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .msg {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .msg.user { align-items: flex-end; }
    .msg.assistant { align-items: flex-start; }
    .bubble {
      max-width: 86%;
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 14px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .msg.user .bubble {
      background: #0f7f6f;
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }
    .msg.assistant .bubble {
      background: #eaf2ff;
      color: #0c2942;
      border-bottom-left-radius: 4px;
    }
    label {
      display: block;
      font-weight: 600;
      font-size: 13px;
      margin: 10px 0 6px;
    }
    textarea, button {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--border);
      padding: 10px;
      font: inherit;
    }
    textarea {
      min-height: 92px;
      resize: vertical;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      color: #fff;
      border: none;
      font-weight: 600;
      margin-top: 0;
    }
    button:hover { filter: brightness(0.95); }
    button.secondary {
      background: #ebf4ff;
      color: #0a4c73;
      border: 1px solid #bfd8f3;
    }
    .cmd-actions {
      margin-top: 8px;
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .cmd-examples {
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .cmd-chip {
      width: auto;
      background: var(--chip-bg);
      color: var(--chip-ink);
      border: 1px solid #bdd9f3;
      padding: 7px 10px;
      font-size: 13px;
    }
    .cmd-chip:hover { background: #d8ecff; filter: none; }
    pre {
      background: #f4f8fc;
      color: #17324a;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      overflow: auto;
      margin: 8px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
    }
    pre.detail {
      min-height: 0;
      max-height: 240px;
      max-width: 100%;
      margin: 0;
      width: 100%;
    }
    details.raw-json {
      width: 100%;
      margin-top: 4px;
    }
    details.raw-json summary {
      cursor: pointer;
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
      margin: 0 0 6px;
    }
    .table-wrap {
      width: 100%;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #ffffff;
    }
    table.chat-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    table.chat-table th,
    table.chat-table td {
      border-bottom: 1px solid var(--border);
      border-right: 1px solid var(--border);
      padding: 8px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    table.chat-table th {
      background: #eef6ff;
      color: #0a4c73;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    table.chat-table th:last-child,
    table.chat-table td:last-child {
      border-right: none;
    }
    @media (max-width: 980px) {
      .cmd-actions { grid-template-columns: 1fr 1fr; }
      .bubble { max-width: 96%; }
    }
  </style>
</head>
<body>
  <main class="shell" id="olist-ui-root">
    <section class="hero">
      <h1>Olist Data Platform Demo UI</h1>
      <p>Chatbot interface: ask naturally first, then set runtime rules for what the assistant can do.</p>
      <p class="status" id="bootstrap-status">Checking bootstrap readiness...</p>
    </section>

    <section class="card">
      <h2>Command Center <span class="pill">Chatbot + Rules</span></h2>
      <p class="helper" id="capability-hint">Loading capabilities...</p>
      <div class="chat-log" id="chat-log"></div>
      <label for="cmd-prompt">Chat input</label>
      <textarea id="cmd-prompt" placeholder="Ask naturally, e.g. show revenue trend by month"></textarea>
      <p class="helper">Use <code>/help</code> to see commands. Use <code>/rule ...</code> to enable/disable capabilities.</p>
      <div class="cmd-actions">
        <button id="btn-run-command">Send</button>
        <button id="btn-capabilities" class="secondary">/help</button>
        <button id="btn-show-rules" class="secondary">/rules</button>
        <button id="btn-clear" class="secondary">Clear chat</button>
      </div>
      <div class="cmd-examples" id="cmd-examples"></div>
    </section>

    <section class="card">
      <h2>Active Rules</h2>
      <p class="helper">Session-scoped rules. They apply immediately to the chatbot runtime.</p>
      <pre id="out-rules">{}</pre>
    </section>
  </main>

  <script>
    const DEFAULT_DATE_CONTEXT = {
      start_date: "2017-01-01",
      end_date: "2018-12-31"
    };

    const DEFAULT_RULES = {
      allow_agent: true,
      allow_kpi: true,
      allow_sql: true,
      allow_schema: true,
      allow_definition: true,
      sql_limit: 500
    };

    const DEFAULT_QUICK_COMMANDS = [
      { label: "What can you do?", command: "/help" },
      { label: "Ask naturally", command: "show monthly revenue trend and summarize key changes" },
      { label: "KPI overview", command: "/kpi 2017-01-01 2018-12-31" },
      { label: "Schema lookup", command: "/schema payment" },
      { label: "Definition", command: "/definition gmv" },
      { label: "Disable SQL", command: "/rule sql off" },
      { label: "Show rules", command: "/rules" }
    ];

    let activeRules = { ...DEFAULT_RULES };

    async function callJson(url, method, payload) {
      const options = { method, headers: { "Content-Type": "application/json" } };
      if (payload !== undefined) options.body = JSON.stringify(payload);
      const res = await fetch(url, options);
      const data = await res.json().catch(() => ({ detail: "Invalid JSON response" }));
      if (!res.ok) throw data;
      return data;
    }

    function setOut(id, value) {
      document.getElementById(id).textContent = JSON.stringify(value, null, 2);
    }

    function setBootstrapStatus(text, isError=false) {
      const el = document.getElementById("bootstrap-status");
      el.textContent = text;
      el.classList.toggle("error", isError);
    }

    function renderRules() {
      setOut("out-rules", activeRules);
    }

    function extractRows(payload) {
      if (!payload || !payload.result) {
        return null;
      }

      const result = payload.result;
      const pickRows = (obj) => {
        if (!obj || typeof obj !== "object") return null;
        if (Array.isArray(obj.data) && obj.data.length) return obj.data;
        if (Array.isArray(obj.matches) && obj.matches.length) return obj.matches;
        if (Array.isArray(obj.series) && obj.series.length) return obj.series;
        return null;
      };

      return pickRows(result) || pickRows(result.raw_result);
    }

    function tableFromRows(rows) {
      if (!Array.isArray(rows) || rows.length === 0) {
        return null;
      }

      const visibleRows = rows.slice(0, 200);
      const columns = [];
      for (const row of visibleRows) {
        if (!row || typeof row !== "object") continue;
        for (const key of Object.keys(row)) {
          if (!columns.includes(key)) columns.push(key);
        }
      }
      if (!columns.length) return null;

      const wrap = document.createElement("div");
      wrap.className = "table-wrap";

      const table = document.createElement("table");
      table.className = "chat-table";

      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      for (const col of columns) {
        const th = document.createElement("th");
        th.textContent = col;
        headRow.appendChild(th);
      }
      thead.appendChild(headRow);

      const tbody = document.createElement("tbody");
      for (const row of visibleRows) {
        const tr = document.createElement("tr");
        for (const col of columns) {
          const td = document.createElement("td");
          const value = row?.[col];
          if (value === null || value === undefined) {
            td.textContent = "";
          } else if (typeof value === "object") {
            td.textContent = JSON.stringify(value);
          } else {
            td.textContent = String(value);
          }
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      }

      table.appendChild(thead);
      table.appendChild(tbody);
      wrap.appendChild(table);
      return wrap;
    }

    function suggestionsFromPayload(payload) {
      const suggestions = payload?.result?.suggestions;
      if (!Array.isArray(suggestions) || !suggestions.length) {
        return null;
      }

      const wrap = document.createElement("div");
      wrap.className = "cmd-examples";
      for (const suggestion of suggestions.slice(0, 8)) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "cmd-chip secondary";
        chip.textContent = suggestion;
        chip.onclick = () => {
          const input = document.getElementById("cmd-prompt");
          input.value = suggestion;
          input.focus();
        };
        wrap.appendChild(chip);
      }
      return wrap;
    }

    function rulesFromPayload(payload) {
      const rules = payload?.result?.rules;
      if (!rules || typeof rules !== "object") {
        return null;
      }

      const wrap = document.createElement("div");
      wrap.className = "cmd-examples";
      for (const [key, value] of Object.entries(rules)) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "cmd-chip secondary";
        chip.textContent = `${key}: ${value}`;
        chip.disabled = true;
        wrap.appendChild(chip);
      }
      return wrap;
    }

    function shouldShowJsonDetail(payload) {
      if (!payload || !payload.result) return false;
      return ["sql", "schema", "definition", "kpi", "agent", "error"].includes(payload.mode);
    }

    function rawJsonDetails(payload) {
      const details = document.createElement("details");
      details.className = "raw-json";
      const summary = document.createElement("summary");
      summary.textContent = "Raw response (optional)";
      details.appendChild(summary);

      const detail = document.createElement("pre");
      detail.className = "detail";
      detail.textContent = JSON.stringify(payload.result, null, 2);
      details.appendChild(detail);
      return details;
    }

    function appendMessage(role, text, payload) {
      const log = document.getElementById("chat-log");
      const row = document.createElement("div");
      row.className = `msg ${role}`;

      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = text;
      row.appendChild(bubble);

      if (payload !== undefined && payload !== null) {
        if (payload.result) {
          const rows = extractRows(payload);
          const table = tableFromRows(rows);
          if (table) {
            row.appendChild(table);
          } else {
            const rules = rulesFromPayload(payload);
            const suggestions = suggestionsFromPayload(payload);
            if (rules) {
              row.appendChild(rules);
            } else if (suggestions) {
              row.appendChild(suggestions);
            } else if (shouldShowJsonDetail(payload)) {
              row.appendChild(rawJsonDetails(payload));
            }
          }
        }
      }

      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
    }

    function resetChat() {
      const log = document.getElementById("chat-log");
      log.innerHTML = "";
      appendMessage(
        "assistant",
        "Xin chào. Bạn cứ hỏi tự nhiên trước. Khi cần giới hạn hành vi, dùng /rules hoặc /rule ..."
      );
    }

    function renderQuickCommands(commands) {
      const holder = document.getElementById("cmd-examples");
      holder.innerHTML = "";
      const items = Array.isArray(commands) && commands.length ? commands : DEFAULT_QUICK_COMMANDS;
      for (const item of items) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cmd-chip secondary";
        btn.textContent = item.label || item.command;
        btn.onclick = () => {
          const input = document.getElementById("cmd-prompt");
          input.value = item.command;
          input.focus();
        };
        holder.appendChild(btn);
      }
    }

    async function checkBootstrap() {
      try {
        const data = await callJson("/ui/proxy/kpi", "POST", DEFAULT_DATE_CONTEXT);
        setBootstrapStatus(
          `Ready. total_orders=${data.overview?.total_orders ?? "n/a"}, gmv=${data.overview?.gmv ?? "n/a"}`
        );
      } catch (err) {
        setBootstrapStatus(
          err?.detail || "Data bootstrap not ready. Check: docker compose logs -f bootstrap",
          true
        );
      }
    }

    async function loadCapabilities() {
      try {
        const data = await callJson("/ui/proxy/capabilities", "GET");
        document.getElementById("capability-hint").textContent = data.description || "Capabilities loaded.";
        renderQuickCommands(data.quick_commands || []);
      } catch (_err) {
        document.getElementById("capability-hint").textContent = "Could not load capabilities.";
        renderQuickCommands(DEFAULT_QUICK_COMMANDS);
      }
    }

    async function sendPrompt(rawInput) {
      const inputEl = document.getElementById("cmd-prompt");
      const input = (rawInput ?? inputEl.value).trim();
      if (!input) {
        return;
      }

      appendMessage("user", input);
      inputEl.value = "";

      try {
        const data = await callJson("/ui/proxy/chat", "POST", {
          message: input,
          context: DEFAULT_DATE_CONTEXT,
          rules: activeRules,
        });

        if (data.active_rules) {
          activeRules = {
            ...activeRules,
            ...data.active_rules,
          };
          renderRules();
        }

        appendMessage("assistant", data.assistant_message || "Done.", {
          mode: data.mode,
          blocked: data.blocked,
          result: data.result,
        });
      } catch (err) {
        appendMessage("assistant", err?.detail || "Unexpected error.", {
          mode: "error",
          blocked: true,
          result: err,
        });
      }
    }

    document.getElementById("btn-run-command").onclick = () => {
      void sendPrompt();
    };

    document.getElementById("btn-capabilities").onclick = () => {
      void sendPrompt("/help");
    };

    document.getElementById("btn-show-rules").onclick = () => {
      void sendPrompt("/rules");
    };

    document.getElementById("btn-clear").onclick = () => {
      resetChat();
    };

    document.getElementById("cmd-prompt").addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        void sendPrompt();
      }
    });

    renderRules();
    resetChat();
    checkBootstrap();
    loadCapabilities();
  </script>
</body>
</html>
"""


@router.post("/proxy/chat", response_model=UiChatResponse)
def proxy_chat(payload: UiChatRequest) -> UiChatResponse:
    message = payload.message.strip()
    rules = payload.rules
    message_lower = message.lower()
    context = _merge_context(payload.context)

    if _is_help_request(message_lower):
        return UiChatResponse(
            mode="help",
            assistant_message=_help_text(rules),
            active_rules=rules,
            result={"rules": rules.model_dump()},
        )

    if message_lower in {"/rules", "rules", "show rules", "xem rules"}:
        return UiChatResponse(
            mode="rules",
            assistant_message=f"Active rules:\n{_rules_text(rules)}",
            active_rules=rules,
            result={"rules": rules.model_dump()},
        )

    if (
        message_lower.startswith("/rule")
        or message_lower.startswith("rule ")
        or message_lower.startswith("set rule")
        or message_lower.startswith("đặt rule")
        or message_lower.startswith("dat rule")
    ):
        updated_rules, text = _apply_rule_command(message, rules)
        return UiChatResponse(
            mode="rules_update",
            assistant_message=text,
            active_rules=updated_rules,
            result={"rules": updated_rules.model_dump()},
        )

    if message_lower.startswith("/sql") or message_lower.startswith("sql:"):
        if not rules.allow_sql:
            return _blocked_response("sql", rules, "SQL is disabled (`allow_sql=off`).")

        sql_text = _strip_prefix(message, ["/sql ", "sql:", "/sql"])
        if not sql_text:
            return UiChatResponse(
                mode="sql",
                assistant_message="Usage: /sql <SELECT query>",
                active_rules=rules,
                warnings=["missing_sql"],
            )

        try:
            result = service.query_data(sql_text, limit=rules.sql_limit)
            return UiChatResponse(
                mode="sql",
                assistant_message=(
                    f"SQL executed successfully. Returned {result.get('row_count', 0)} rows "
                    f"(limit={rules.sql_limit})."
                ),
                active_rules=rules,
                result=result,
            )
        except UnsafeQueryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _service_unavailable(exc) from exc

    if message_lower.startswith("/schema") or message_lower.startswith("schema:"):
        if not rules.allow_schema:
            return _blocked_response("schema", rules, "Schema search is disabled (`allow_schema=off`).")

        keyword = _strip_prefix(message, ["/schema ", "schema:", "/schema"])
        if not keyword:
            return UiChatResponse(
                mode="schema",
                assistant_message="Usage: /schema <keyword>",
                active_rules=rules,
                warnings=["missing_keyword"],
            )

        try:
            result = service.search_schema(keyword, schemas=DEFAULT_SCHEMAS)
            return UiChatResponse(
                mode="schema",
                assistant_message=f"Found {result.get('match_count', 0)} schema matches for '{keyword}'.",
                active_rules=rules,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            raise _service_unavailable(exc) from exc

    if (
        message_lower.startswith("/definition")
        or message_lower.startswith("definition:")
        or message_lower.startswith("/define")
        or message_lower.startswith("define ")
        or message_lower.startswith("define:")
    ):
        if not rules.allow_definition:
            return _blocked_response(
                "definition",
                rules,
                "Business definition tool is disabled (`allow_definition=off`).",
            )

        term = _strip_prefix(
            message,
            ["/definition ", "definition:", "/define ", "define ", "define:", "/definition", "/define"],
        )
        if not term:
            return UiChatResponse(
                mode="definition",
                assistant_message="Usage: /definition <term>",
                active_rules=rules,
                warnings=["missing_term"],
            )

        try:
            result = service.get_business_definition(term)
            if result.get("found"):
                definition = result.get("definition", {})
                summary = f"{definition.get('term')}: {definition.get('definition')}"
            else:
                summary = "Definition not found. Use available_terms in the payload to pick a valid term."

            return UiChatResponse(
                mode="definition",
                assistant_message=summary,
                active_rules=rules,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            raise _service_unavailable(exc) from exc

    if message_lower.startswith("/kpi") or message_lower.startswith("kpi:"):
        if not rules.allow_kpi:
            return _blocked_response("kpi", rules, "KPI summary is disabled (`allow_kpi=off`).")

        start_date, end_date = _extract_dates(message, context)

        try:
            result = service.get_kpi_summary(start_date=start_date, end_date=end_date)
            overview = result.get("overview", {})
            summary = (
                "KPI summary loaded: "
                f"orders={overview.get('total_orders')}, "
                f"gmv={overview.get('gmv')}, "
                f"delivered_rate={overview.get('delivered_order_rate')}"
            )
            return UiChatResponse(
                mode="kpi",
                assistant_message=summary,
                active_rules=rules,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            raise _service_unavailable(exc) from exc

    inferred_intent = classify_intent(message)
    if inferred_intent == "help_request":
        return UiChatResponse(
            mode="help",
            assistant_message=_help_text(rules),
            active_rules=rules,
            result={"rules": rules.model_dump(), "inferred_intent": inferred_intent},
        )

    if inferred_intent == "chitchat":
        return UiChatResponse(
            mode="chitchat",
            assistant_message=(
                "Mình đang online. Bạn cứ hỏi tự nhiên về KPI, doanh thu, schema, hoặc business definition. "
                "Ví dụ: 'show monthly revenue trend' hoặc '/sql SELECT * FROM serving.kpi_overview'."
            ),
            active_rules=rules,
            result={
                "inferred_intent": inferred_intent,
                "suggestions": [
                    "show monthly revenue trend",
                    "/schema payment",
                    "/definition gmv",
                ],
            },
        )

    if not rules.allow_agent:
        return _blocked_response(
            "agent",
            rules,
            "Natural-language agent workflow is disabled (`allow_agent=off`).",
        )

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
        return _blocked_response(inferred_intent, rules, reason)

    try:
        result = run_workflow(message, context)
        return UiChatResponse(
            mode="agent",
            assistant_message=result.get("result_summary", "Workflow completed."),
            active_rules=rules,
            warnings=result.get("warnings", []),
            result={
                **result,
                "inferred_intent": inferred_intent,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/kpi", response_model=KpiSummaryResponse)
def proxy_kpi(payload: KpiSummaryRequest) -> KpiSummaryResponse:
    try:
        result = service.get_kpi_summary(start_date=payload.start_date, end_date=payload.end_date)
        return KpiSummaryResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/agent", response_model=AgentWorkflowResponse)
def proxy_agent(payload: AgentWorkflowRequest) -> AgentWorkflowResponse:
    try:
        result = run_workflow(payload.question, payload.context)
        return AgentWorkflowResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/sql", response_model=QueryDataResponse)
def proxy_sql(payload: QueryDataRequest) -> QueryDataResponse:
    try:
        result = service.query_data(payload.sql, limit=payload.limit)
        return QueryDataResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/schema", response_model=SearchSchemaResponse)
def proxy_schema(payload: SearchSchemaRequest) -> SearchSchemaResponse:
    try:
        result = service.search_schema(payload.keyword, schemas=payload.schemas)
        return SearchSchemaResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.get("/proxy/definition", response_model=BusinessDefinitionResponse)
def proxy_definition(term: str) -> BusinessDefinitionResponse:
    try:
        result = service.get_business_definition(term)
        return BusinessDefinitionResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.get("/proxy/capabilities")
def proxy_capabilities() -> dict[str, Any]:
    return UI_CAPABILITIES
