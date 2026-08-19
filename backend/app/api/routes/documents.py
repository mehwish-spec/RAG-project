import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_app_settings, get_ingestion_service, get_storage_service
from app.core.config import Settings
from app.core.exceptions import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.logging import get_logger
from app.database.connection import db_session, get_db
from app.database.models import Document, DocumentChunk, DocumentStatus
from app.ingestion.ingestion_service import IngestionService
from app.ingestion.text_loader import RawTextLoader
from app.processing.chunker import ChunkConfig, chunk_text
from app.processing.cleaner import clean_text
from app.processing.metadata import build_chunk_metadata, build_document_metadata, compute_content_hash
from app.schemas.documents import (
    DeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    RawTextIngestRequest,
    ReindexResponse,
)
from app.storage.base import StorageService

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


async def _run_processing_in_background(document_id: uuid.UUID, file_path: str, ingestion_service: IngestionService):
    async with db_session() as session:
        await ingestion_service.process_document(session, document_id, file_path)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    summary="Upload a document",
    description="Accepts multipart PDF, DOC, DOCX, or TXT uploads and starts background ingestion.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_app_settings),
):
    extension = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if extension not in settings.allowed_extensions_list:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{extension}'. Allowed types: {', '.join(settings.allowed_extensions_list)}"
        )

    content = await file.read()
    if not content:
        raise EmptyFileError("Uploaded file is empty.")
    if len(content) > settings.max_upload_size_bytes:
        raise FileTooLargeError(
            f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    content_hash = compute_content_hash(content)

    existing = await session.scalar(select(Document).where(Document.content_hash == content_hash))
    if existing is not None:
        logger.info("duplicate_document_upload", extra={"extra_fields": {"document_id": str(existing.id)}})
        return _to_response(existing)

    storage_path = storage_service.save(content, file.filename or "upload")

    document = Document(
        filename=storage_path,
        original_filename=file.filename or "upload",
        file_type=extension,
        file_size=len(content),
        content_hash=content_hash,
        status=DocumentStatus.UPLOADED,
        doc_metadata=build_document_metadata(extension=extension),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    full_path = storage_service.full_path(storage_path)
    background_tasks.add_task(_run_processing_in_background, document.id, full_path, ingestion_service)

    return _to_response(document)


@router.post(
    "/text",
    response_model=DocumentResponse,
    summary="Ingest raw text",
    description="Accepts raw text (no file) and ingests it through the same pipeline as uploaded files.",
)
async def ingest_raw_text(
    payload: RawTextIngestRequest,
    session: AsyncSession = Depends(get_db),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_app_settings),
):
    content_bytes = payload.text.encode("utf-8")
    if not content_bytes:
        raise EmptyFileError("Submitted text is empty.")

    content_hash = compute_content_hash(content_bytes)
    existing = await session.scalar(select(Document).where(Document.content_hash == content_hash))
    if existing is not None:
        return _to_response(existing)

    document = Document(
        filename=payload.filename,
        original_filename=payload.filename,
        file_type="txt",
        file_size=len(content_bytes),
        content_hash=content_hash,
        status=DocumentStatus.PROCESSING,
        doc_metadata=build_document_metadata(extension="txt", source_type="raw_text", extra=payload.metadata),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Raw text is small enough to process synchronously and skips file I/O entirely.
    pages = RawTextLoader.load(payload.text, payload.metadata)
    config = ChunkConfig(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        min_chunk_size=settings.MIN_CHUNK_SIZE,
        max_chunk_size=settings.MAX_CHUNK_SIZE,
    )

    chunks = []
    for page in pages:
        cleaned = clean_text(page.text)
        chunks.extend(chunk_text(cleaned, config=config, page_number=page.page_number, section=page.section))

    embedding_service = ingestion_service.embedding_service
    texts = [c.content for c in chunks]
    vectors = embedding_service.embed_texts(texts) if texts else []

    for index, (c, vector) in enumerate(zip(chunks, vectors)):
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=c.content,
                embedding=vector,
                page_number=c.page_number,
                section=c.section,
                chunk_metadata=build_chunk_metadata(
                    document_id=str(document.id), chunk_index=index, page_number=c.page_number, section=c.section
                ),
            )
        )

    document.status = DocumentStatus.COMPLETED
    document.chunk_count = len(chunks)
    await session.commit()
    await session.refresh(document)

    return _to_response(document)


@router.get("", response_model=DocumentListResponse, summary="List documents")
async def list_documents(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    return DocumentListResponse(total=len(documents), documents=[_to_response(d) for d in documents])


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get a document")
async def get_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    document = await session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} was not found.")
    return _to_response(document)


@router.delete("/{document_id}", response_model=DeleteResponse, summary="Delete a document")
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    document = await session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} was not found.")

    chunks_deleted = document.chunk_count
    if storage_service.exists(document.filename):
        storage_service.delete(document.filename)

    await session.delete(document)  # cascades to document_chunks via ORM relationship
    await session.commit()

    return DeleteResponse(id=document_id, deleted=True, chunks_deleted=chunks_deleted)


@router.post("/{document_id}/reindex", response_model=ReindexResponse, summary="Reprocess/reindex a document")
async def reindex_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    document = await session.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} was not found.")

    if not storage_service.exists(document.filename):
        raise DocumentNotFoundError(
            "Original file is no longer available in storage and cannot be reindexed. "
            "This applies to raw-text documents, which have nothing to re-extract."
        )

    document.status = DocumentStatus.PROCESSING
    await session.commit()

    full_path = storage_service.full_path(document.filename)
    background_tasks.add_task(_run_processing_in_background, document.id, full_path, ingestion_service)

    return ReindexResponse(id=document_id, status=DocumentStatus.PROCESSING)


def _to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        content_hash=document.content_hash,
        status=document.status,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
        metadata=document.doc_metadata or {},
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
