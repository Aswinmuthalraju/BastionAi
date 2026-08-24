import time
from typing import Any, Dict, List

from pydantic import BaseModel


class EvidenceCitation(BaseModel):
    citation_id: str
    source_doc: str
    page_number: int
    bounding_box: Dict[str, float]
    chunk_id: str
    snippet: str
    similarity: float
    model_used: str
    timestamp: str


class EvidenceLedger:
    """Pairs real RAG vector-search results with the generation model used to format verifiable inline citations."""

    @staticmethod
    def generate_ledger(retrieved_chunks: List[Dict[str, Any]], model_used: str) -> List[Dict[str, Any]]:
        citations = []
        for idx, chunk in enumerate(retrieved_chunks):
            citation = EvidenceCitation(
                citation_id=f"CIT-{idx + 1}",
                source_doc=chunk["source_doc"],
                page_number=chunk["page_number"],
                bounding_box=chunk.get("bounding_box", {"x1": 0, "y1": 0, "x2": 1, "y2": 1}),
                chunk_id=chunk["chunk_id"],
                snippet=chunk["content"][:160] + ("..." if len(chunk["content"]) > 160 else ""),
                similarity=chunk.get("similarity", 0.0),
                model_used=model_used,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            )
            citations.append(citation.model_dump())
        return citations


evidence_ledger = EvidenceLedger()
