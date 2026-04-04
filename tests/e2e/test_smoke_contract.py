from pathlib import Path


def test_required_runtime_files_exist() -> None:
    project_root = Path(__file__).resolve().parents[2]

    required_files = [
        project_root / "docker-compose.yml",
        project_root / "airflow/dags/olist_pipeline.py",
        project_root / "dbt/dbt_project.yml",
        project_root / "app/main.py",
    ]

    for path in required_files:
        assert path.exists(), f"Missing required runtime artifact: {path}"
