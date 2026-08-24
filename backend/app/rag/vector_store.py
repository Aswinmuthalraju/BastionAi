import time
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app import config
from app.providers.embeddings import embedding_provider

COLLECTION = "document_chunks"
NAMESPACE = uuid.UUID("6f6a1e2e-9b1a-4b2e-9c1a-000ba5710a10")


class VectorStoreService:
    """
    Real embedded Qdrant vector store (HNSW cosine search, on-disk, persisted at
    config.QDRANT_PATH). Access control is enforced inside the query itself via
    Qdrant payload filters, not by post-filtering results in Python.
    """

    def __init__(self):
        self.client = QdrantClient(path=config.QDRANT_PATH)
        self._ensure_collection()

    def _ensure_collection(self):
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                COLLECTION,
                vectors_config=VectorParams(size=config.EMBEDDING_DIM, distance=Distance.COSINE),
            )

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(NAMESPACE, chunk_id))

    def add_chunk(
        self,
        chunk_id: str,
        content: str,
        source_doc: str,
        page_number: int,
        data_scope: str,
        allowed_roles: List[str],
        doc_id: str,
        bounding_box: Optional[Dict[str, float]] = None,
    ) -> None:
        vector = embedding_provider.embed(content)
        payload = {
            "chunk_id": chunk_id,
            "content": content,
            "source_doc": source_doc,
            "page_number": page_number,
            "data_scope": data_scope,
            "allowed_roles": allowed_roles,
            "doc_id": doc_id,
            "bounding_box": bounding_box or {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "ingestion_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        }
        self.client.upsert(
            COLLECTION,
            points=[PointStruct(id=self._point_id(chunk_id), vector=vector, payload=payload)],
        )

    def delete_document_chunks(self, doc_id: str) -> None:
        self.client.delete(
            COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
        )

    def search(
        self,
        query: str,
        user_scopes: List[str],
        user_role: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Embeds the query and runs real HNSW cosine search, filtered server-side by ACL."""
        query_vector = embedding_provider.embed(query)

        must: List[FieldCondition] = []
        if "*" not in user_scopes:
            must.append(FieldCondition(key="data_scope", match=MatchAny(any=user_scopes)))
        if "admin" not in user_role:
            must.append(FieldCondition(key="allowed_roles", match=MatchValue(value=user_role)))

        query_filter = Filter(must=must) if must else None

        results = self.client.query_points(
            COLLECTION, query=query_vector, query_filter=query_filter, limit=top_k
        ).points

        return [
            {
                "chunk_id": r.payload["chunk_id"],
                "content": r.payload["content"],
                "source_doc": r.payload["source_doc"],
                "page_number": r.payload["page_number"],
                "data_scope": r.payload["data_scope"],
                "allowed_roles": r.payload["allowed_roles"],
                "bounding_box": r.payload["bounding_box"],
                "ingestion_timestamp": r.payload["ingestion_timestamp"],
                "similarity": round(r.score, 4),
            }
            for r in results
        ]

    def count(self) -> int:
        return self.client.count(COLLECTION).count


vector_store_service = VectorStoreService()
