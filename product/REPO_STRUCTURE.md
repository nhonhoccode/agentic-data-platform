# REPO_STRUCTURE

## Proposed Directory Tree
```text
Project/
  Required.md
  product/
    PROJECT_BRIEF.md
    FEATURES.json
    ARCHITECTURE.md
    DATA_MODEL.md
    API_SPEC.md
    AGENT_DESIGN.md
    TESTING.md
    ROADMAP.md
    REPO_STRUCTURE.md
    AGENTS.md
  code/
    app/
      api/
      agent/
      db/
      definitions/
      ingestion/
      services/
      transform/
    airflow/dags/
    dbt/models/{staging,marts,serving}
    docker/{api,airflow}
    scripts/
    tests/{unit,integration,e2e}
    data/
    docs/sample_data/
    pyproject.toml
    docker-compose.yml
```

## Purpose of Each Folder
- `product/`: project-level architecture/product docs and implementation guidance.
- `code/app/`: application runtime modules.
- `code/airflow/`: orchestration DAGs.
- `code/dbt/`: data transformation and validation models.
- `code/docker/`: container build assets.
- `code/scripts/`: operational helper scripts.
- `code/tests/`: quality and contract tests.
- `code/data/`: source Olist datasets.
- `code/docs/sample_data/`: lightweight sample slices for documentation.

## Naming Conventions
- Python modules: `snake_case`.
- SQL models: `stg_`, `dim_`, `fct_`, `kpi_` prefixes by semantic role.
- Schemas: `raw`, `staging`, `marts`, `serving`.
- Endpoint names map directly to required tool names.

## Ownership Conventions
- Data Engineering: ingestion, schemas, Airflow, dbt foundations.
- Analytics Engineering: marts/KPI definitions and tests.
- Backend Engineering: API contracts, auth, query guardrails.
- AI Engineering: multi-agent orchestration and tool routing.

## Prompt and Agent Artifacts
- Prompting logic for agents lives in `code/app/agent/`.
- Business definitions used by agents live in `code/app/definitions/`.

## Evaluation Artifacts
- Unit/integration/e2e checks in `code/tests/`.
- Future agent eval datasets can be added in `code/tests/e2e/fixtures/`.

## Configs, Pipelines, Agents, Docs, Tests
- Configs: `.env`, `pyproject.toml`, `dbt/profiles.yml`, `docker-compose.yml`.
- Pipelines: `app/ingestion`, `dbt/models`, `airflow/dags`.
- Agents: `app/agent`.
- Docs: `product/` and `code/README.md`.
- Tests: `code/tests`.
