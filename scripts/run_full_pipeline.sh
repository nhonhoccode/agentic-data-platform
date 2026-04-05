#!/usr/bin/env bash
set -euo pipefail

cd /home/maximus_nhonlearningcode/Workspace/DataPlatform/Project/code

source /home/maximus_nhonlearningcode/Workspace/venv/.venv_Test/bin/activate

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
python -m app.transform.serving

echo "Pipeline completed successfully."
