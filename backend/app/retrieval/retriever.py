"""
Retriever: query -> query embedding -> vector search -> top-k candidate
chunks. Deduplicates by content and enforces the configured similarity
threshold so irrelevant chunks are never returned just to fill top_k.
"""
import uuid

from app.core.config import Settings
from app.core.exceptions import InvalidQueryError
from app.embeddings.embedding_service import EmbeddingService
from app.vectorstore.base import VectorSearchResult, VectorStore


class Retriever:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore, settings: Settings):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.settings = settings

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        document_id: uuid.UUID | None = None,
    ) -> list[VectorSearchResult]:
        if not query or not query.strip():
            raise InvalidQueryError("Query must not be empty.")

        k = top_k or self.settings.TOP_K
        threshold = self.settings.SIMILARITY_THRESHOLD if similarity_threshold is None else similarity_threshold

        query_embedding = self.embedding_service.embed_query(query.strip())
        candidates = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=max(k * 2, k),  # over-fetch a little so threshold/reranking has room to work
            similarity_threshold=threshold,
            document_id=document_id,
        )

        deduped = self._dedupe(candidates)
        return deduped[:k]

    @staticmethod
    def _dedupe(results: list[VectorSearchResult]) -> list[VectorSearchResult]:
        seen: set[str] = set()
        unique: list[VectorSearchResult] = []
        for r in results:
            key = r.content.strip()
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)
        return unique
