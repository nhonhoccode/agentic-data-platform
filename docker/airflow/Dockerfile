FROM apache/airflow:2.10.3-python3.11

USER airflow
WORKDIR /opt/project

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir "dbt-postgres>=1.8.0" "psycopg[binary]>=3.2.0"
