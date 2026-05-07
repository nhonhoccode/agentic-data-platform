from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from app.config import get_settings
from app.db.client import DatabaseClient
from app.definitions.business_glossary import BUSINESS_DEFINITIONS
from app.rag.embeddings import get_embedding_provider
from app.rag.store import collection_count, ensure_collection, upsert_points

DEFAULT_SCHEMAS = ("marts", "serving", "staging")


def _stable_id(text: str) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _fetch_columns(schemas: tuple[str, ...]) -> list[dict[str, Any]]:
    db = DatabaseClient()
    placeholders = ",".join(["%s"] * len(schemas))
    sql = f"""
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema IN ({placeholders})
        ORDER BY table_schema, table_name, ordinal_position
    """
    return db.run_system_query(sql, list(schemas))


def _group_by_table(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["table_schema"], row["table_name"])
        grouped.setdefault(key, []).append(row)
    return grouped


def _table_document(schema: str, table: str, columns: list[dict[str, Any]]) -> str:
    col_lines = [
        f"- {c['column_name']} ({c['data_type']})"
        for c in columns
    ]
    return (
        f"Table: {schema}.{table}\n"
        f"Columns:\n" + "\n".join(col_lines)
    )


def index_schema(schemas: tuple[str, ...] = DEFAULT_SCHEMAS) -> dict[str, Any]:
    settings = get_settings()
    provider = get_embedding_provider()
    ensure_collection(settings.qdrant_collection_schema, dim=provider.dim)

    rows = _fetch_columns(schemas)
    grouped = _group_by_table(rows)
    if not grouped:
        return {"indexed_tables": 0, "indexed_columns": 0}

    docs: list[str] = []
    ids: list[int] = []
    payloads: list[dict[str, Any]] = []

    for (schema, table), cols in grouped.items():
        doc = _table_document(schema, table, cols)
        docs.append(doc)
        ids.append(_stable_id(f"{schema}.{table}"))
        payloads.append(
            {
                "schema": schema,
                "table": table,
                "fully_qualified": f"{schema}.{table}",
                "columns": [c["column_name"] for c in cols],
                "column_types": {c["column_name"]: c["data_type"] for c in cols},
                "document": doc,
            }
        )

    vectors = provider.embed(docs)
    upsert_points(settings.qdrant_collection_schema, ids, vectors, payloads)

    column_count = sum(len(cols) for cols in grouped.values())
    return {
        "indexed_tables": len(grouped),
        "indexed_columns": column_count,
        "collection": settings.qdrant_collection_schema,
    }


def index_business_glossary() -> dict[str, Any]:
    settings = get_settings()
    provider = get_embedding_provider()
    ensure_collection(settings.qdrant_collection_glossary, dim=provider.dim)

    docs: list[str] = []
    ids: list[int] = []
    payloads: list[dict[str, Any]] = []

    for key, payload in BUSINESS_DEFINITIONS.items():
        doc = (
            f"Term: {payload['term']} ({key})\n"
            f"Definition: {payload['definition']}\n"
            f"Formula: {payload['formula']}\n"
            f"Source: {payload['source_table']}"
        )
        docs.append(doc)
        ids.append(_stable_id(f"glossary::{key}"))
        payloads.append(
            {
                "key": key,
                "term": payload["term"],
                "definition": payload["definition"],
                "formula": payload["formula"],
                "source_table": payload["source_table"],
                "document": doc,
            }
        )

    if not docs:
        return {"indexed_terms": 0}

    vectors = provider.embed(docs)
    upsert_points(settings.qdrant_collection_glossary, ids, vectors, payloads)
    return {"indexed_terms": len(docs), "collection": settings.qdrant_collection_glossary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Index schema metadata + glossary into Qdrant")
    parser.add_argument(
        "--schemas",
        nargs="+",
        default=list(DEFAULT_SCHEMAS),
        help="Postgres schemas to index",
    )
    parser.add_argument("--skip-schema", action="store_true")
    parser.add_argument("--skip-glossary", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {}
    if not args.skip_schema:
        report["schema"] = index_schema(tuple(args.schemas))
    if not args.skip_glossary:
        report["glossary"] = index_business_glossary()

    settings = get_settings()
    report["counts"] = {
        "schema": collection_count(settings.qdrant_collection_schema),
        "glossary": collection_count(settings.qdrant_collection_glossary),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
