from __future__ import annotations

from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=30,
    )


def ensure_collection(name: str, dim: int) -> None:
    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
    )


def upsert_points(
    collection: str,
    ids: list[int | str],
    vectors: list[list[float]],
    payloads: list[dict[str, Any]],
) -> None:
    client = get_qdrant()
    client.upsert(
        collection_name=collection,
        points=qmodels.Batch(ids=ids, vectors=vectors, payloads=payloads),
    )


def search(
    collection: str,
    vector: list[float],
    limit: int = 5,
    filter_must: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    client = get_qdrant()
    qfilter = None
    if filter_must:
        qfilter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v))
                for k, v in filter_must.items()
            ]
        )
    response = client.query_points(
        collection_name=collection,
        query=vector,
        limit=limit,
        query_filter=qfilter,
        with_payload=True,
    )
    return [{"score": h.score, "payload": h.payload, "id": h.id} for h in response.points]


def collection_count(name: str) -> int:
    client = get_qdrant()
    try:
        return client.count(collection_name=name, exact=True).count
    except Exception:  # noqa: BLE001
        return 0
