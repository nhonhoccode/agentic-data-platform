# ARCHITECTURE

## End-to-End Architecture
The platform is a batch-first analytics architecture:
1. Source CSV files in `code/data/` are ingested to PostgreSQL raw tables.
2. dbt transforms raw data into standardized staging views.
3. dbt builds marts and serving views for KPI consumption.
4. FastAPI exposes trusted data tools to users and agents.
5. LangGraph orchestrates multi-agent workflows for query/insight tasks.
6. Airflow orchestrates full pipeline execution.

## System Layers
- Source Layer: Olist CSV files.
- Raw Layer (`raw` schema): immutable landing tables loaded as text.
- Staging Layer (`staging` schema): typed, cleaned, normalized entities.
- Marts Layer (`marts` schema): analytics-ready fact/dimension and KPI tables.
- Serving Layer (`serving` schema): stable views for API and agent access.
- Application Layer: FastAPI tools and auth.
- Agent Layer: Supervisor + SQL + Retrieval + Insight agents.
- Orchestration Layer: Airflow DAG and Docker runtime.

## Data Flow
- `app.ingestion.loader` recreates and loads `raw.*` tables.
- dbt models execute in dependency order (`staging -> marts -> serving`).
- API and agents query only staging/marts/serving (never direct raw mutations).
- Airflow DAG operationalizes this flow with task-level retries.

## Agent Responsibilities
- Supervisor Agent:
  - Classifies intent.
  - Routes to specialized agent/tool.
- SQL Agent:
  - Handles read-only SQL requests.
  - Applies SQL safety controls through service layer.
- Retrieval/Schema Agent:
  - Searches metadata (tables/columns/types).
  - Returns business term definitions.
- Insight Agent:
  - Pulls KPI summary and trend data.
  - Produces concise insight narrative.

## Component Interactions
- FastAPI route -> QueryService -> DatabaseClient -> Postgres.
- `run_agent_workflow` -> LangGraph state machine -> service tools.
- Airflow task -> Python module/dbt CLI -> Postgres artifacts.
- Docker Compose wires API/Airflow/Postgres in a reproducible local environment.

## Security Considerations
- API key auth via `X-API-Key`.
- SQL guardrails:
  - Only `SELECT`/CTE queries.
  - Block DDL/DML keywords.
  - Enforce row limits.
  - Statement timeout on execution.
- Agent tools route through same guarded query layer.

## Scalability Considerations
- Postgres is sufficient for MVP scale with Olist-sized batch data.
- Full dataset mode may require indexes/materialized artifacts as usage grows.
- dbt lineage enables modular model expansion.
- Service and agent layers are separated for future horizontal API scaling.

## Future Extension Path
- Add semantic retrieval/RAG over schema docs and business glossary.
- Add tracing/observability (OpenTelemetry, LangSmith or equivalent).
- Add CI/CD checks for dbt + API + agent evaluation.
- Move to managed cloud services (managed Postgres/warehouse, managed orchestration).
- Introduce LLMOps pipelines for prompt/version/eval lifecycle.
