# ROADMAP

## Phase 1: Data Foundation
Objective:
- Establish reliable ingestion and raw persistence.

Deliverables:
- Full Olist CSV ingestion loader.
- Postgres schemas (`raw/staging/marts/serving`) bootstrapped.
- Dockerized local runtime baseline.

Risks:
- Source encoding/casting issues.
- Long ingest time on constrained local machines.

Exit Criteria:
- All source tables loaded in `raw`.
- Ingestion reproducible with consistent row counts.

## Phase 2: Data Modeling and Serving
Objective:
- Build trusted transformation and KPI-serving layers.

Deliverables:
- dbt staging and marts models.
- Serving views for KPI and category analytics.
- dbt tests for keys and relationships.

Risks:
- Model logic drift from business KPI definitions.
- Performance bottlenecks for broad analytical queries.

Exit Criteria:
- dbt run/test pass.
- Serving views return valid KPI outputs.

## Phase 3: Multi-Agent Integration
Objective:
- Integrate a safe multi-agent orchestration layer over trusted data.

Deliverables:
- Supervisor + SQL + Retrieval + Insight agents.
- Required agent tools exposed via API contracts.
- Deterministic fallback without LLM dependency.

Risks:
- Misrouting intent to wrong tools.
- Unsafe query attempts from user prompts.

Exit Criteria:
- `run_agent_workflow` works across representative question types.
- SQL safety guardrails verified.

## Phase 4: Evaluation and Optimization
Objective:
- Improve reliability, quality, and operational confidence.

Deliverables:
- Expanded unit/integration/e2e tests.
- Agent routing and response quality benchmark suite.
- Query and transformation performance tuning.

Risks:
- Metric regression during model changes.
- Test coverage gaps for corner-case prompts/data.

Exit Criteria:
- Stable CI-level quality gates defined.
- Baseline latency and correctness metrics documented.

## Phase 5: Future Cloud/MLOps Expansion
Objective:
- Prepare for production-grade deployment and GenAI operations.

Deliverables:
- Cloud deployment blueprint.
- Observability/tracing and model/tool telemetry.
- LLMOps/MLOps lifecycle integration (versioning, eval, rollout).

Risks:
- Increased platform complexity and operational overhead.
- Governance and access-control requirements expansion.

Exit Criteria:
- Approved production architecture decision record.
- Prioritized migration backlog with ownership and milestones.
