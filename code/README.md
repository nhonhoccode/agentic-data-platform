# Olist AI-Ready Data Platform MVP

Runnable local MVP for e-commerce analytics with:
- Postgres data platform (`raw -> staging -> marts -> serving`)
- dbt transformations and tests
- FastAPI query and agent endpoints
- LangGraph-based multi-agent orchestration (hybrid local-first)
- Airflow pipeline orchestration

## 1) Environment setup

```bash
cd /home/maximus_nhonlearningcode/Workspace/DataPlatform/Project
source /home/maximus_nhonlearningcode/Workspace/venv/.venv_Test/bin/activate
uv pip install -e .[dev]
cp .env.example .env
```

## 1.1) LLM provider configuration (optional)

Default is deterministic local-first mode (`LLM_PROVIDER=none`).

Gemini:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
MODEL_API_BASE=gemini-2.0-flash
TEMPERATURE=0
```

DeepSeek:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_key
MODEL_API_BASE=deepseek-chat
TEMPERATURE=0
```

Self-host OpenAI-compatible (Qwen example):

```env
LLM_PROVIDER=self_host
MODEL_API_BASE=Qwen/Qwen3.5-27B
TEMPERATURE=0
OPENAI_API_KEY=your_gateway_key
BASE_URL=https://apimodel.berp.vn/v1
LLM_ENABLE_THINKING=false
```

## 2) Start infrastructure

```bash
docker compose up --build -d
```

This starts:
- `postgres`
- `bootstrap` (one-shot ingest + dbt run/test + serving validation)
- `api` (FastAPI)
- `cloudflared` (auto quick tunnel for public demo URL)
- `airflow-init`, `airflow-webserver`, `airflow-scheduler`

## 3) Open services

- Demo web UI: `http://localhost:8000/ui`
- API docs: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health/liveness`
- Readiness: `http://localhost:8000/health/readiness`
- Health endpoint (requires key): `http://localhost:8000/health`
- Airflow UI: `http://localhost:8080` (default user/password from `.env`: `AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD`)
- Public tunnel domain: check with `docker compose logs --tail=80 cloudflared` and open `https://<random>.trycloudflare.com/ui`
- For custom domain (e.g. `api.votrongnhon.cloud`): set `CLOUDFLARED_COMMAND=tunnel --no-autoupdate run --token <tunnel_token>` in `.env`, then add route in Cloudflare Tunnel -> `Published application routes` (`hostname=api.votrongnhon.cloud`, `service=http://api:8000`).
- For public exposure, apply Cloudflare Access policy to all published routes (`api/ui/airflow`).

## 4) Check bootstrap and readiness

```bash
docker compose logs -f bootstrap
docker compose logs -f cloudflared
```

When bootstrap completes successfully, UI/API will read from ready serving tables.

## 5) Optional manual data build commands

```bash
dp-ingest
cd dbt && dbt deps && dbt run && dbt test
python -m app.transform.serving
```

## 6) Stop stack

```bash
docker compose down
```

## Useful commands

```bash
make lint
make test
make ingest
make serve
make e2e
make up
make down
make logs-bootstrap
```

Install and run pre-commit hooks:

```bash
make precommit-install
make precommit-run
```

## Architecture notes

- No mock data path by default; full Olist CSV is the default runtime mode.
- Agent workflow works without LLM API key through deterministic routing + SQL tools.
- If `LLM_PROVIDER` and corresponding keys are configured, final response synthesis is enhanced by LLM.
- UI routes (`/ui`, `/ui/proxy/*`) run via server-side proxy and do not expose API key in browser.
- New v2 interfaces:
  - `POST /api/v2/chat`
  - `POST /api/v2/query`
  - `GET /api/v2/capabilities`
- v1 routes under `/api/v1/*` are kept short-term and marked deprecated.

## Security note

- Do not commit real API keys into `.env`.
- If keys were ever exposed in shared chat/logs, rotate them immediately.
- In non-dev environments, `APP_API_KEY` cannot be empty or `change-me`.
- API reads data with a dedicated read-only database role (`POSTGRES_READONLY_USER`).
