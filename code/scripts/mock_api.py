"""Simple API smoke runner for manual endpoint checks."""

from __future__ import annotations

import json
import os

import httpx

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "change-me")
HEADERS = {"X-API-Key": API_KEY}


REQUESTS = [
    (
        "/api/v1/query_data",
        {
            "sql": "SELECT * FROM serving.kpi_overview",
            "limit": 10,
        },
    ),
    (
        "/api/v1/search_schema",
        {
            "keyword": "payment",
            "schemas": ["marts", "serving"],
        },
    ),
    (
        "/api/v1/get_kpi_summary",
        {
            "start_date": "2017-01-01",
            "end_date": "2018-12-31",
        },
    ),
    (
        "/api/v1/run_agent_workflow",
        {
            "question": "show monthly revenue trend",
            "context": {},
        },
    ),
]


def main() -> None:
    with httpx.Client(timeout=30.0) as client:
        for path, payload in REQUESTS:
            response = client.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload)
            print(f"[{response.status_code}] {path}")
            print(json.dumps(response.json(), indent=2, default=str)[:1200])

        response = client.get(
            f"{BASE_URL}/api/v1/get_business_definition",
            params={"term": "gmv"},
            headers=HEADERS,
        )
        print(f"[{response.status_code}] /api/v1/get_business_definition")
        print(json.dumps(response.json(), indent=2, default=str))


if __name__ == "__main__":
    main()
