"""
Custom exception hierarchy and FastAPI exception handlers.

All application-raised errors should subclass `AppError`. This ensures
API consumers get a clean, consistent JSON error body and never see a
raw stack trace, while full details are still logged server-side.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "app_error"

    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class UnsupportedFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    error_code = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "file_too_large"


class EmptyFileError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "empty_file"


class ExtractionError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "extraction_failed"


class NoExtractableTextError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "no_extractable_text"


class DuplicateDocumentError(AppError):
    status_code = status.HTTP_200_OK
    error_code = "duplicate_document"


class DocumentNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "document_not_found"


class EmbeddingError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "embedding_failed"


class VectorDimensionMismatchError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "vector_dimension_mismatch"


class LLMError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "llm_failed"


class InvalidQueryError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "invalid_query"


class ConfigurationError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "configuration_error"


class DatabaseError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "database_error"


def _error_body(error_code: str, message: str) -> dict:
    return {"success": False, "error": {"code": error_code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("app_error", extra={"extra_fields": {
            "path": str(request.url), "error_code": exc.error_code, "message": exc.message
        }})
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.error_code, exc.message))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.error("unhandled_exception", exc_info=exc, extra={"extra_fields": {"path": str(request.url)}})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )
