"""
FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, health, search
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.database.connection import ensure_vector_extension

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup", extra={"extra_fields": {"environment": settings.ENVIRONMENT}})
    try:
        await ensure_vector_extension()
    except Exception as exc:  # noqa: BLE001
        logger.warning("vector_extension_check_failed", extra={"extra_fields": {"error": str(exc)}})
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-ready Retrieval-Augmented Generation API supporting PDF, DOC, DOCX, "
        "TXT and raw text ingestion with pgvector-backed semantic search and citation-aware "
        "LLM answers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(documents.router, prefix=settings.API_PREFIX)
app.include_router(search.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)

# Also expose /health at the root, since orchestrators (Docker, k8s) commonly
# probe it there rather than under the API prefix.
app.include_router(health.router)
