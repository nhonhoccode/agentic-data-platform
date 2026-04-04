from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.agent.core import run_workflow
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


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{DATA_NOT_READY_HINT}. Error: {exc}")


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
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, #f2f8ff 0%, var(--bg) 50%);
    }
    .shell {
      max-width: 1180px;
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
    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 3px 12px rgba(18, 38, 58, 0.08);
    }
    .card h2 {
      margin-top: 0;
      font-size: 16px;
      color: #0a4c73;
    }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    label { display: block; font-weight: 600; font-size: 13px; margin: 8px 0 6px; }
    input, textarea, button {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--border);
      padding: 10px;
      font: inherit;
    }
    textarea { min-height: 110px; resize: vertical; }
    button {
      margin-top: 10px;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
      border: none;
      font-weight: 600;
    }
    button:hover { filter: brightness(0.95); }
    .inline {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    pre {
      background: #0e1e2f;
      color: #d6f0ff;
      border-radius: 10px;
      padding: 12px;
      overflow: auto;
      min-height: 150px;
      margin: 8px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
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
      color: var(--muted);
    }
    .status.error { color: var(--danger); font-weight: 600; }
    @media (max-width: 980px) {
      .span-4, .span-6, .span-8 { grid-column: span 12; }
      .inline { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell" id="olist-ui-root">
    <section class="hero">
      <h1>Olist Data Platform Demo UI</h1>
      <p>FastAPI HTML demo for KPI, agent workflow, safe SQL query, and schema lookup.</p>
      <p class="status" id="bootstrap-status">Checking bootstrap readiness...</p>
    </section>

    <section class="grid">
      <article class="card span-4">
        <h2>KPI Summary</h2>
        <div class="inline">
          <div>
            <label for="kpi-start">Start date</label>
            <input id="kpi-start" type="date" value="2017-01-01" />
          </div>
          <div>
            <label for="kpi-end">End date</label>
            <input id="kpi-end" type="date" value="2018-12-31" />
          </div>
        </div>
        <button id="btn-kpi">Load KPI</button>
        <pre id="out-kpi">{}</pre>
      </article>

      <article class="card span-8">
        <h2>Agent Workflow</h2>
        <label for="agent-question">Question</label>
        <textarea id="agent-question">show monthly revenue trend and summarize key changes</textarea>
        <button id="btn-agent">Run Agent</button>
        <pre id="out-agent">{}</pre>
      </article>

      <article class="card span-6">
        <h2>SQL Playground <span class="pill">read-only guarded</span></h2>
        <label for="sql-query">SQL</label>
        <textarea id="sql-query">SELECT * FROM serving.kpi_overview</textarea>
        <button id="btn-sql">Run SQL</button>
        <pre id="out-sql">{}</pre>
      </article>

      <article class="card span-6">
        <h2>Schema + Business Definition</h2>
        <label for="schema-keyword">Schema keyword</label>
        <input id="schema-keyword" value="payment" />
        <button id="btn-schema">Search Schema</button>
        <pre id="out-schema">{}</pre>

        <label for="biz-term">Business term</label>
        <input id="biz-term" value="gmv" />
        <button id="btn-definition">Get Definition</button>
        <pre id="out-definition">{}</pre>
      </article>
    </section>
  </main>

  <script>
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

    async function checkBootstrap() {
      try {
        const data = await callJson("/ui/proxy/kpi", "POST", {
          start_date: document.getElementById("kpi-start").value || null,
          end_date: document.getElementById("kpi-end").value || null,
        });
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

    document.getElementById("btn-kpi").onclick = async () => {
      try {
        const data = await callJson("/ui/proxy/kpi", "POST", {
          start_date: document.getElementById("kpi-start").value || null,
          end_date: document.getElementById("kpi-end").value || null,
        });
        setOut("out-kpi", data);
      } catch (err) {
        setOut("out-kpi", err);
      }
    };

    document.getElementById("btn-agent").onclick = async () => {
      try {
        const data = await callJson("/ui/proxy/agent", "POST", {
          question: document.getElementById("agent-question").value,
          context: {
            start_date: document.getElementById("kpi-start").value || null,
            end_date: document.getElementById("kpi-end").value || null,
          }
        });
        setOut("out-agent", data);
      } catch (err) {
        setOut("out-agent", err);
      }
    };

    document.getElementById("btn-sql").onclick = async () => {
      try {
        const data = await callJson("/ui/proxy/sql", "POST", {
          sql: document.getElementById("sql-query").value,
          limit: 500,
        });
        setOut("out-sql", data);
      } catch (err) {
        setOut("out-sql", err);
      }
    };

    document.getElementById("btn-schema").onclick = async () => {
      try {
        const data = await callJson("/ui/proxy/schema", "POST", {
          keyword: document.getElementById("schema-keyword").value,
          schemas: ["raw", "staging", "marts", "serving"],
        });
        setOut("out-schema", data);
      } catch (err) {
        setOut("out-schema", err);
      }
    };

    document.getElementById("btn-definition").onclick = async () => {
      try {
        const term = encodeURIComponent(document.getElementById("biz-term").value);
        const res = await fetch(`/ui/proxy/definition?term=${term}`);
        const data = await res.json();
        if (!res.ok) throw data;
        setOut("out-definition", data);
      } catch (err) {
        setOut("out-definition", err);
      }
    };

    checkBootstrap();
  </script>
</body>
</html>
"""


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
