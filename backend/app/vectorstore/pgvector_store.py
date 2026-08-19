"""
PostgreSQL + pgvector implementation of `VectorStore`.

Uses cosine distance (`<=>`) via pgvector's SQLAlchemy comparator and
converts distance -> similarity score (`1 - distance`) so callers work
with an intuitive 0..1 "higher is better" score.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.core.logging import get_logger
from app.database.models import Document, DocumentChunk
from app.vectorstore.base import VectorSearchResult, VectorStore

logger = get_logger(__name__)


class PgVectorStore(VectorStore):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float = 0.0,
        document_id: uuid.UUID | None = None,
    ) -> list[VectorSearchResult]:
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(
                DocumentChunk,
                Document.filename,
                Document.original_filename,
                distance_expr.label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.status == "completed")
            .order_by(distance_expr.asc())
            .limit(top_k)
        )
        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        try:
            result = await self.session.execute(stmt)
            rows = result.all()
        except Exception as exc:  # noqa: BLE001
            raise DatabaseError(f"Vector similarity search failed: {exc}") from exc

        results: list[VectorSearchResult] = []
        for chunk, filename, original_filename, distance in rows:
            similarity = 1.0 - float(distance)
            if similarity < similarity_threshold:
                continue
            results.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    metadata=chunk.chunk_metadata or {},
                    score=round(similarity, 4),
                    filename=original_filename or filename,
                )
            )
        return results
