import math
from typing import List

import httpx

from app import config


class EmbeddingUnavailableError(RuntimeError):
    pass


class EmbeddingProvider:
    """Real embedding vectors via Ollama's /api/embed. Powers both RAG retrieval and drift cosine similarity."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def embed(self, text: str) -> List[float]:
        url = config.EMBEDDING_BASE_URL.rstrip("/") + "/api/embed"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, json={"model": config.EMBEDDING_MODEL, "input": text})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise EmbeddingUnavailableError(f"Embedding endpoint {url} unreachable: {exc}") from exc

        vectors = data.get("embeddings")
        if not vectors or not vectors[0]:
            raise EmbeddingUnavailableError(f"Embedding model '{config.EMBEDDING_MODEL}' returned no vector.")
        return vectors[0]

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


embedding_provider = EmbeddingProvider()
