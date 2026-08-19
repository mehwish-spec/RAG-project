from fastapi import APIRouter

from app.core.config import get_settings
from app.database.connection import check_database_connection, check_vector_extension

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check", description="Returns ok if the API process is running.")
async def health():
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness check",
    description="Checks database connectivity, the pgvector extension, and required configuration.",
)
async def readiness():
    settings = get_settings()
    db_ok = await check_database_connection()
    vector_ok = await check_vector_extension() if db_ok else False

    config_ok = True
    config_issues: list[str] = []
    if settings.EMBEDDING_PROVIDER == "openai" and not settings.EMBEDDING_API_KEY:
        config_ok = False
        config_issues.append("EMBEDDING_API_KEY is required for EMBEDDING_PROVIDER=openai")
    if settings.LLM_PROVIDER == "openai" and not settings.LLM_API_KEY:
        config_ok = False
        config_issues.append("LLM_API_KEY is required for LLM_PROVIDER=openai")

    overall_ok = db_ok and vector_ok and config_ok
    return {
        "status": "ok" if overall_ok else "degraded",
        "checks": {
            "database": "ok" if db_ok else "unreachable",
            "vector_extension": "ok" if vector_ok else "missing",
            "configuration": "ok" if config_ok else "invalid",
        },
        "issues": config_issues,
    }
