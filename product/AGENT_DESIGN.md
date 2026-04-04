# AGENT_DESIGN

## System Goals
- Provide reliable analytics assistance using trusted structured data.
- Keep agent behavior deterministic and safe in MVP.
- Support optional LLM enhancement without blocking local runtime.

## Orchestration Logic
- Framework: LangGraph state graph.
- Sequence:
  1. Supervisor classifies user intent.
  2. Supervisor routes to SQL/Retrieval/Insight agent node.
  3. Selected agent invokes tool(s) via service layer.
  4. Synthesis step returns concise result summary.

## Tool Selection Rules
- `query_data`:
  - intent = SQL query or generic analytics request requiring tabular output.
- `search_schema`:
  - intent contains schema/table/column/metadata terms.
- `get_business_definition`:
  - intent asks for meaning/definition of KPI terms.
- `get_kpi_summary`:
  - intent asks for KPI overview, trend, revenue summary.
- `run_agent_workflow`:
  - orchestrates above tools under one request contract.

## Routing Logic
- Deterministic keyword-first classifier in MVP.
- Mapping:
  - `sql_query -> SQL Agent`
  - `schema_search -> Retrieval/Schema Agent`
  - `business_definition -> Retrieval/Schema Agent`
  - `kpi_summary -> Insight Agent`

## Prompting Strategy
- Local-first mode:
  - deterministic summary templates from structured results.
- LLM-enabled mode (if API key exists):
  - use lightweight summarization prompt with bounded response length.
  - no direct unrestricted SQL generation from LLM.

## Guardrails
- SQL execution restricted to read-only validated queries.
- Row limits enforced.
- Statement timeout configured per query.
- Agent tools call shared service layer (single enforcement point).
- Errors returned with safe, actionable messages.

## Failure Modes
- Missing serving artifacts after dbt run.
- Invalid user SQL blocked by safety validator.
- Schema search keyword too broad returns capped result set.
- Optional LLM call failure gracefully falls back to deterministic summary.

## Human-in-the-Loop Checkpoints
- Schema changes require data engineer review.
- New tool addition requires API spec and tests update.
- KPI definition changes require analyst/business sign-off.

## Evaluation Criteria
- Intent routing accuracy on representative query set.
- Tool correctness and response schema validity.
- SQL safety violation detection rate.
- Consistency of KPI outputs versus direct SQL benchmark.
- End-to-end latency for typical agent workflow requests.

## Future Evolution to GenAI and LLMOps
- Add retrieval-augmented semantic context over schema/docs.
- Add prompt/version registry and offline evaluations.
- Add trace-based observability for tool calls and decisions.
- Add policy engine for role-based tool/action permissions.
