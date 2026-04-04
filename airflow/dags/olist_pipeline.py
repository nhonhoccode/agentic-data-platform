from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/project"

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
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
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {PROJECT_DIR}/dbt && "
            "dbt deps --profiles-dir . && "
            "dbt run --profiles-dir ."
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt test --profiles-dir .",
    )

    validate_serving = BashOperator(
        task_id="validate_serving",
        bash_command=f"cd {PROJECT_DIR} && python -m app.transform.serving",
    )

    ingest_raw >> dbt_run >> dbt_test >> validate_serving
