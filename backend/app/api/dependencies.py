"""
FastAPI dependency providers. Wires concrete provider implementations
(chosen from configuration) into the abstractions used by routes/services.
"""
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.database.connection import get_db
from app.embeddings.embedding_service import EmbeddingService, get_embedding_service
from app.ingestion.ingestion_service import IngestionService
from app.llm.llm_service import LLMService, get_llm_service
from app.rag.pipeline import RAGPipeline
from app.retrieval.reranker import get_reranker
from app.retrieval.retriever import Retriever
from app.storage.base import StorageService
from app.storage.local_storage import LocalStorageService
from app.vectorstore.pgvector_store import PgVectorStore


def get_app_settings() -> Settings:
    return get_settings()


def get_storage_service(settings: Settings = Depends(get_app_settings)) -> StorageService:
    return LocalStorageService(settings.STORAGE_PATH)


def get_embedding_service_dep(settings: Settings = Depends(get_app_settings)) -> EmbeddingService:
    return get_embedding_service()


def get_llm_service_dep(settings: Settings = Depends(get_app_settings)) -> LLMService:
    return get_llm_service()


def get_ingestion_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
    storage_service: StorageService = Depends(get_storage_service),
    settings: Settings = Depends(get_app_settings),
) -> IngestionService:
    return IngestionService(embedding_service, storage_service, settings)


async def get_rag_pipeline(
    session: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
    llm_service: LLMService = Depends(get_llm_service_dep),
    settings: Settings = Depends(get_app_settings),
) -> AsyncGenerator[RAGPipeline, None]:
    vector_store = PgVectorStore(session)
    retriever = Retriever(embedding_service, vector_store, settings)
    reranker = get_reranker(settings.RERANKING_ENABLED)
    yield RAGPipeline(retriever, reranker, llm_service, settings)


async def get_retriever(
    session: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
    settings: Settings = Depends(get_app_settings),
) -> Retriever:
    vector_store = PgVectorStore(session)
    return Retriever(embedding_service, vector_store, settings)
