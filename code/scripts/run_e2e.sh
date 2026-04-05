#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_PATH="${VENV_PATH:-/home/maximus_nhonlearningcode/Workspace/venv/.venv_Test/bin/activate}"
E2E_API_HOST="${E2E_API_HOST:-127.0.0.1}"
E2E_API_PORT="${E2E_API_PORT:-8000}"

if [[ ! -f "${VENV_PATH}" ]]; then
  echo "Venv activate script not found: ${VENV_PATH}" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

source "${VENV_PATH}"
cd "${CODE_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

set -a
source .env
set +a

uv pip install -e .[dev]

ruff check app tests
pytest

docker compose up -d postgres

python -m app.ingestion.loader

cd dbt
dbt deps --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
cd ..

python -m app.db.provision_readonly
python -m app.transform.serving

APP_API_KEY="${APP_API_KEY:-change-me}" \
uvicorn app.main:app --host "${E2E_API_HOST}" --port "${E2E_API_PORT}" > /tmp/olist_e2e_api.log 2>&1 &
API_PID=$!

for _ in $(seq 1 30); do
  if curl -s -H "X-API-Key: ${APP_API_KEY:-change-me}" "http://${E2E_API_HOST}:${E2E_API_PORT}/health" >/dev/null; then
    break
  fi
  sleep 1
done

API_BASE_URL="http://${E2E_API_HOST}:${E2E_API_PORT}" \
API_KEY="${APP_API_KEY:-change-me}" \
python scripts/mock_api.py

echo "E2E pipeline + API smoke completed successfully."
