# PROJECT_BRIEF

## Problem Statement
E-commerce teams often have fragmented analytics data and inconsistent definitions across SQL analysts, BI dashboards, and AI assistants. As a result, business users receive conflicting answers for the same KPI (for example GMV or delivered order rate), and AI agents cannot reliably query trusted data.

## Business Context
The Olist dataset represents a realistic transactional commerce domain (orders, payments, reviews, products, sellers, customers). The organization needs a practical data platform MVP where data engineers can build pipelines, analysts can query trusted marts, and AI engineers can add multi-agent workflows on top of stable interfaces.

## Project Goals
- Build an MVP data platform with `raw -> staging -> marts -> serving` layers.
- Provide a trusted SQL/API surface for human users and AI agents.
- Implement a multi-agent architecture with clear role separation:
  - Supervisor Agent
  - SQL Agent
  - Retrieval/Schema Agent
  - Insight Agent
- Keep extension paths ready for GenAI, RAG, MLOps, observability, and cloud deployment.

## User Personas
1. Data Engineer: owns ingestion, transformations, orchestration, and data quality checks.
2. Data Analyst: consumes curated marts/serving views for BI and ad-hoc SQL.
3. Business Manager: reads KPI summaries and operational insights.
4. AI Engineer: builds/iterates agent tools and workflows using trusted interfaces.

## Core Use Cases
- Ingest full Olist CSV source files into Postgres raw schema.
- Clean and standardize core entities in staging.
- Build KPI-ready marts for orders, delivery, payments, and category sales.
- Serve governed views through API and SQL endpoints.
- Run agent workflows for schema discovery, business definitions, KPI summaries, and safe SQL querying.

## Scope (MVP)
- Full dataset ingestion from local CSV files.
- dbt transformation project with tests and lineage.
- FastAPI endpoints for required interfaces.
- LangGraph orchestration with deterministic local-first fallback.
- Airflow DAG for ingest -> dbt run -> dbt test -> serving validation.
- Docker Compose for local reproducible runtime.

## Out of Scope (Current Phase)
- Custom ML model training pipelines.
- Real-time streaming architecture.
- Enterprise IAM/governance stack.
- Multi-cloud production deployment.
- Full LLMOps experiment platform.

## Success Metrics
- Data reliability:
  - 100% required source files ingested into raw schema.
  - dbt tests pass for key constraints (not null, unique, relationships).
- Platform usability:
  - All 5 required API interfaces return schema-valid responses.
  - End-to-end pipeline runnable locally with one command sequence.
- Agent quality:
  - Correct tool routing for schema/KPI/definition/SQL intents.
  - Read-only SQL guardrails enforced for API and SQL agent calls.

## Assumptions
- Source CSV files are available in `code/data/` and use Olist column layout.
- PostgreSQL is the primary analytical serving engine for MVP.
- API key auth (`X-API-Key`) is sufficient for local/internal environments.
- Full dataset mode is default (not sample-only).

## Risks
- Data type edge cases during cast from raw text to typed staging columns.
- Query latency on full dataset without proper indexing/materialization tuning.
- Prompt/tool drift if future agents generate unrestricted SQL.
- Airflow + dbt dependency drift if versions are not pinned during upgrades.

## Constraints
- Python-first implementation stack.
- Local developer environment with Docker and uv package management.
- No enterprise platform dependencies in MVP.

## Expected Outcomes
- A practical starter repository that can be executed immediately by a team.
- Stable contracts for data, API, and agent tools.
- Clear roadmap and extension points toward GenAI, LLMOps/MLOps, and cloud operations.
