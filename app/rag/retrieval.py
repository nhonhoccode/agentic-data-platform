from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.rag.embeddings import get_embedding_provider
from app.rag.store import collection_count, search


def is_index_ready() -> bool:
    settings = get_settings()
    return collection_count(settings.qdrant_collection_schema) > 0


def retrieve_tables(question: str, limit: int = 5) -> list[dict[str, Any]]:
    settings = get_settings()
    if collection_count(settings.qdrant_collection_schema) == 0:
        return []
    provider = get_embedding_provider()
    vector = provider.embed([question])[0]
    return search(settings.qdrant_collection_schema, vector, limit=limit)


def retrieve_glossary(question: str, limit: int = 3) -> list[dict[str, Any]]:
    settings = get_settings()
    if collection_count(settings.qdrant_collection_glossary) == 0:
        return []
    provider = get_embedding_provider()
    vector = provider.embed([question])[0]
    return search(settings.qdrant_collection_glossary, vector, limit=limit)


def format_schema_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    blocks: list[str] = []
    for hit in hits:
        payload = hit.get("payload") or {}
        doc = payload.get("document") or ""
        score = hit.get("score", 0.0)
        blocks.append(f"[score={score:.3f}]\n{doc}")
    return "\n\n".join(blocks)


def select_top_tables(question: str, limit: int = 5) -> list[str]:
    hits = retrieve_tables(question, limit=limit)
    return [h["payload"]["fully_qualified"] for h in hits if h.get("payload")]
