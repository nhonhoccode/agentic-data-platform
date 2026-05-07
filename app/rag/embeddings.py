from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


_FASTEMBED_DIMS = {
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "intfloat/multilingual-e5-large": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class FastEmbedProvider:
    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self._model_name = model_name
        self.dim = _FASTEMBED_DIMS.get(model_name, 384)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(vec) for vec in self._model.embed(texts)]


_GEMINI_DIMS = {
    "gemini-embedding-001": 3072,
    "gemini-embedding-2": 3072,
    "gemini-embedding-2-preview": 3072,
}


class GeminiEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str = "gemini-embedding-001") -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name
        self.dim = _GEMINI_DIMS.get(model_name, 768)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            result = self._client.models.embed_content(
                model=self._model_name,
                contents=text,
            )
            out.append(list(result.embeddings[0].values))
        return out


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.strip().lower()

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        return GeminiEmbeddingProvider(settings.gemini_api_key)

    if provider in {"fastembed", "local", ""}:
        default = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        model = settings.embedding_model or default
        if model not in _FASTEMBED_DIMS:
            model = default
        return FastEmbedProvider(model_name=model)

    if provider == "none":
        raise RuntimeError(
            "EMBEDDING_PROVIDER=none — set to 'fastembed' or 'gemini' to enable RAG"
        )

    raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {provider}")
