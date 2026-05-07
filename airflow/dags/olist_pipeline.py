from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/project"

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="olist_end_to_end_pipeline",
    default_args=DEFAULT_ARGS,
    description="Ingest full Olist dataset, build dbt models, validate serving layer",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["olist", "mvp", "data-platform"],
) as dag:
    ingest_raw = BashOperator(
        task_id="ingest_raw",
        bash_command=f"cd {PROJECT_DIR} && python -m app.ingestion.loader",
        execution_timeout=timedelta(minutes=40),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
            f"cd {PROJECT_DIR}/dbt && "
            "dbt run --profiles-dir . --log-path /tmp/dbt_logs --target-path /tmp/dbt_target"
        ),
        execution_timeout=timedelta(minutes=30),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
            f"cd {PROJECT_DIR}/dbt && "
            "dbt test --profiles-dir . --log-path /tmp/dbt_logs --target-path /tmp/dbt_target"
        ),
        execution_timeout=timedelta(minutes=20),
    )

    provision_readonly = BashOperator(
        task_id="provision_readonly_role",
        bash_command=f"cd {PROJECT_DIR} && python -m app.db.provision_readonly",
        execution_timeout=timedelta(minutes=5),
    )

    validate_serving = BashOperator(
        task_id="validate_serving",
        bash_command=f"cd {PROJECT_DIR} && python -m app.transform.serving",
        execution_timeout=timedelta(minutes=5),
    )

    rag_index = BashOperator(
        task_id="rag_index",
        bash_command=f"cd {PROJECT_DIR} && python -m app.rag.indexer",
        execution_timeout=timedelta(minutes=15),
        trigger_rule="all_success",
    )

    ingest_raw >> dbt_run >> dbt_test >> provision_readonly >> validate_serving >> rag_index
