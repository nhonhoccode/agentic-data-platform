# TESTING

## Definition of Done
- Full dataset can be ingested into raw schema.
- dbt run completes for staging/marts/serving.
- dbt tests pass for core constraints.
- All required API endpoints are callable with valid contracts.
- Agent workflow executes with deterministic fallback without LLM key.

## Unit Testing Strategy
- SQL safety validator tests:
  - Accept read-only SELECT/CTE.
  - Reject DDL/DML and multi-statement SQL.
  - Enforce and cap query limits.
- Router tests:
  - Intent classification and route mapping for representative prompts.
- Ingestion schema tests:
  - Validate full source file coverage and non-empty column definitions.

## Data Validation Tests
- dbt generic tests:
  - `not_null`, `unique`, `relationships` on critical keys.
- Casting checks:
  - null-safe conversion for timestamps and numeric fields.
- Freshness/sanity:
  - row count consistency checks from raw to key staging models.

## Pipeline Validation
- Airflow DAG smoke run validates task dependency chain:
  - ingest -> dbt run -> dbt test -> serving validation.
- Retry semantics tested through induced task failure in dev.

## Agent Behavior Tests
- Route-to-tool correctness by intent.
- Business definition retrieval behavior for found/not-found terms.
- SQL agent default query template fallback behavior.
- LLM-off mode still returns deterministic summary.

## SQL Correctness Checks
- Compare selected serving KPIs to direct SQL reference queries.
- Validate no unsafe SQL reaches database execution.

## End-to-End Smoke Tests
- Local flow:
  1. Start Postgres.
  2. Run ingestion.
  3. Run dbt run/test.
  4. Validate serving objects.
  5. Hit all API endpoints.
  6. Run agent workflow sample question.

## Reliability and Safety Checks
- Statement timeout enforcement for long-running queries.
- API auth rejection tests for missing/invalid key.
- Graceful fallback path when optional LLM provider is unavailable.
