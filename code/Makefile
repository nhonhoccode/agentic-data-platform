.PHONY: install lint test ingest serve dbt-run dbt-test e2e precommit-install precommit-run up down logs-bootstrap logs-tunnel

install:
	uv pip install -e .[dev]

lint:
	ruff check app tests

test:
	pytest

ingest:
	dp-ingest

serve:
	dp-api

dbt-run:
	cd dbt && dbt deps && dbt run

dbt-test:
	cd dbt && dbt test

e2e:
	bash scripts/run_e2e.sh

up:
	docker compose up --build -d

down:
	docker compose down

logs-bootstrap:
	docker compose logs -f bootstrap

logs-tunnel:
	docker compose logs -f cloudflared

precommit-install:
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		uv run --python 3.11 --extra dev pre-commit install && uv run --python 3.11 --extra dev pre-commit install --hook-type pre-push; \
	else \
		echo "No git repository detected. Run 'git init' first, then retry precommit-install."; \
	fi

precommit-run:
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		uv run --python 3.11 --extra dev pre-commit run --all-files && uv run --python 3.11 --extra dev pre-commit run --all-files --hook-stage pre-push; \
	else \
		echo "No git repository detected. Running equivalent checks directly..."; \
		ruff check app tests && pytest && (cd dbt && DBT_LOG_PATH=/tmp DBT_TARGET_PATH=/tmp/dbt_target dbt parse --profiles-dir .); \
	fi
