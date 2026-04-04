# AGENTS

## Project Purpose
Build and evolve an AI-ready e-commerce analytics data platform using trusted structured data and a modular multi-agent architecture.

## Architecture Summary
- Data pipeline: `raw -> staging -> marts -> serving` in PostgreSQL.
- API layer: FastAPI endpoints exposing trusted tools.
- Agent layer: LangGraph supervisor routing to SQL, Retrieval/Schema, and Insight roles.
- Orchestration: Airflow DAG for end-to-end batch runs.

## Codebase Rules
- Keep module boundaries strict (`ingestion`, `transform`, `api`, `agent`, `services`, `db`).
- Do not bypass service layer for query execution from API/agents.
- Do not introduce write-capable SQL in query endpoints/tools.

## Coding Conventions
- Python 3.9+ compatible code.
- Type hints required on public functions.
- Keep functions small and composable.
- Use explicit error handling for unsafe SQL and missing dependencies.

## Build Commands
```bash
source /home/maximus_nhonlearningcode/Workspace/venv/.venv_Test/bin/activate
cd /home/maximus_nhonlearningcode/Workspace/DataPlatform/Project/code
uv pip install -e .[dev]
```

## Test Commands
```bash
cd /home/maximus_nhonlearningcode/Workspace/DataPlatform/Project/code
pytest
```

## Validation Workflow
1. Run ingestion (`python -m app.ingestion.loader`).
2. Run dbt (`dbt deps && dbt run && dbt test`).
3. Validate serving artifacts (`python -m app.transform.serving`).
4. Run API contract and unit tests (`pytest`).
5. Smoke-check API and agent workflow.

## Schema Change Rules
- Any schema/model change must update:
  - dbt models/tests
  - data model docs (`DATA_MODEL.md`)
  - API/agent behavior if affected
- Preserve backward compatibility in serving layer where possible.

## Agent Tool Addition Rules
- New tool must include:
  - Request/response contract
  - Guardrails and auth assumptions
  - Route selection criteria
  - Unit/integration tests
  - API_SPEC documentation update

## Documentation Update Rules
- Update `product/*.md` when behavior contracts change.
- Keep `FEATURES.json` statuses and dependencies aligned with implementation.

## What Not To Do
- Do not run unbounded SQL queries in production-facing endpoints.
- Do not couple agent logic directly to raw tables.
- Do not add heavyweight enterprise components prematurely.

## Missing Context Behavior
- Prefer safe defaults and deterministic behavior.
- Record assumptions in docs/PR notes.
- Fail fast on critical data/runtime prerequisites.

## Verification Before Finishing Work
- Confirm tests pass locally.
- Confirm required serving objects exist.
- Confirm all required endpoints return schema-valid output.
- Confirm no unresolved TODO placeholders remain in committed deliverables.
