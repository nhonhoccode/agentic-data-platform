#!/usr/bin/env bash
set -euo pipefail

cd /opt/project

echo "[BOOTSTRAP] Waiting to start full data bootstrap..."
python -m app.ingestion.loader

cd dbt
dbt deps --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .

cd ..
python -m app.db.provision_readonly
python -m app.transform.serving

echo "[BOOTSTRAP] Full data bootstrap completed successfully."
