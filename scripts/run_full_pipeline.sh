#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${VENV_PATH:-/home/maximus_nhonlearningcode/Workspace/venv/.venv_Test/bin/activate}"

if [[ ! -f "${VENV_PATH}" ]]; then
  echo "Venv activate script not found: ${VENV_PATH}" >&2
  exit 1
fi

source "${VENV_PATH}"
cd "${PROJECT_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

uv pip install -e .[dev]

docker compose up -d postgres

python -m app.ingestion.loader

cd dbt
dbt deps --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .

cd ..
python -m app.db.provision_readonly
python -m app.transform.serving

echo "Pipeline completed successfully at ${PROJECT_DIR}."
