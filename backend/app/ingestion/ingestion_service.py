"""
Ingestion orchestration service.

Ties together: file validation -> extraction (loader) -> cleaning ->
chunking -> embedding -> vector storage, and keeps `Document.status`
accurate throughout (uploaded -> processing -> completed/failed).

This is deliberately the ONLY place that sequences the full ingestion
flow; API routes just create the initial `Document` row and hand off
to `IngestionService.process_document()` (synchronously or via a
FastAPI BackgroundTask).
"""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NoExtractableTextError
from app.core.logging import get_logger
from app.database.models import Document, DocumentChunk, DocumentStatus
from app.embeddings.embedding_service import EmbeddingService
from app.ingestion.registry import get_loader
from app.processing.chunker import ChunkConfig, chunk_text
from app.processing.cleaner import clean_text
from app.processing.metadata import build_chunk_metadata
from app.storage.base import StorageService

logger = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        storage_service: StorageService,
        settings: Settings,
    ):
        self.embedding_service = embedding_service
        self.storage_service = storage_service
        self.settings = settings

    async def process_document(self, session: AsyncSession, document_id: uuid.UUID, file_path: str) -> None:
        """Run the full extraction -> chunk -> embed -> store pipeline for
        an already-created `Document` row, updating its status as it goes."""
        document = await session.get(Document, document_id)
        if document is None:
            logger.error("document_not_found_for_processing", extra={"extra_fields": {"document_id": str(document_id)}})
            return

        document.status = DocumentStatus.PROCESSING
        await session.commit()

        try:
            loader = get_loader(document.file_type)
            pages = loader.load(file_path)

            config = ChunkConfig(
                chunk_size=self.settings.CHUNK_SIZE,
                chunk_overlap=self.settings.CHUNK_OVERLAP,
                min_chunk_size=self.settings.MIN_CHUNK_SIZE,
                max_chunk_size=self.settings.MAX_CHUNK_SIZE,
            )

            all_chunks: list[tuple[str, int | None, str | None]] = []
            for page in pages:
                cleaned = clean_text(page.text)
                if not cleaned:
                    continue
                for c in chunk_text(cleaned, config=config, page_number=page.page_number, section=page.section):
                    all_chunks.append((c.content, c.page_number, c.section))

            if not all_chunks:
                raise NoExtractableTextError("No usable text remained after cleaning and chunking.")

            # Remove any pre-existing chunks (supports reindex/idempotent reprocessing).
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

            texts = [c[0] for c in all_chunks]
            embeddings = self._embed_in_batches(texts)

            chunk_rows = []
            for index, ((content, page_number, section), embedding) in enumerate(zip(all_chunks, embeddings)):
                chunk_rows.append(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        embedding=embedding,
                        page_number=page_number,
                        section=section,
                        chunk_metadata=build_chunk_metadata(
                            document_id=str(document.id),
                            chunk_index=index,
                            page_number=page_number,
                            section=section,
                        ),
                    )
                )
            session.add_all(chunk_rows)

            document.status = DocumentStatus.COMPLETED
            document.chunk_count = len(chunk_rows)
            document.error_message = None
            await session.commit()

            logger.info(
                "document_processing_complete",
                extra={"extra_fields": {"document_id": str(document.id), "chunk_count": len(chunk_rows)}},
            )

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            document = await session.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error_message = str(exc)[:2000]
                await session.commit()
            logger.error(
                "document_processing_failed",
                extra={"extra_fields": {"document_id": str(document_id), "error": str(exc)}},
            )

    def _embed_in_batches(self, texts: list[str]) -> list[list[float]]:
        batch_size = self.settings.EMBEDDING_BATCH_SIZE
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            vectors.extend(self.embedding_service.embed_texts(texts[i : i + batch_size]))
        return vectors
