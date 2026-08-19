"""
Vector store abstraction. `PgVectorStore` is the default implementation;
swapping to a different vector database means implementing this same
interface without touching the retrieval/RAG layers above it.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorSearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_number: int | None
    section: str | None
    metadata: dict[str, Any]
    score: float
    filename: str


class VectorStore(ABC):
    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float = 0.0,
        document_id: uuid.UUID | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError
