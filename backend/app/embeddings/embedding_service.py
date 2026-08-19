"""
Embedding provider abstraction.

`EmbeddingService` is the interface the rest of the application depends
on. Concrete providers (local sentence-transformers, OpenAI) are chosen
purely from `EMBEDDING_PROVIDER` in configuration - no other module
needs to know which one is active.

The embedding dimension is validated against `EMBEDDING_DIMENSION` in
configuration on every batch: if a provider ever returns a different
dimension than the database schema expects, we fail loudly rather than
silently corrupting the vector index.
"""
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings, get_settings
from app.core.exceptions import EmbeddingError, VectorDimensionMismatchError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService(ABC):
    dimension: int

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _validate_dimension(self, vectors: list[list[float]]) -> None:
        for v in vectors:
            if len(v) != self.dimension:
                raise VectorDimensionMismatchError(
                    f"Embedding provider returned dimension {len(v)}, but "
                    f"EMBEDDING_DIMENSION is configured as {self.dimension}. "
                    "Update EMBEDDING_DIMENSION to match the provider/model, "
                    "then re-run migrations before ingesting documents."
                )


class LocalEmbeddingService(EmbeddingService):
    """Runs a local sentence-transformers model. No document content ever
    leaves the container when this provider is active."""

    _model = None  # lazy-loaded, shared across instances

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dimension = settings.EMBEDDING_DIMENSION
        self.model_name = settings.EMBEDDING_MODEL

    def _get_model(self):
        if LocalEmbeddingService._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("loading_local_embedding_model", extra={"extra_fields": {"model": self.model_name}})
            LocalEmbeddingService._model = SentenceTransformer(self.model_name)
        return LocalEmbeddingService._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._get_model()
            batch_size = self.settings.EMBEDDING_BATCH_SIZE
            vectors = model.encode(
                texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True
            ).tolist()
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"Local embedding generation failed: {exc}") from exc

        self._validate_dimension(vectors)
        return vectors


class OllamaEmbeddingService(EmbeddingService):
    """Generates embeddings via an Ollama instance (e.g. nomic-embed-text)."""

    def __init__(self, settings: Settings):
        base = getattr(settings, "EMBEDDING_BASE_URL", None) or settings.LLM_BASE_URL
        self.base_url = base.rstrip("/")
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model_name,
            "input": batch,
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{self.base_url}/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            if not embeddings:
                raise EmbeddingError(f"Ollama returned no embeddings for model {self.model_name}")
            return embeddings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors: list[list[float]] = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                vectors.extend(self._embed_batch(batch))
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"Ollama embedding generation failed: {exc}") from exc

        self._validate_dimension(vectors)
        return vectors


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(self, settings: Settings):
        if not settings.EMBEDDING_API_KEY:
            from app.core.exceptions import ConfigurationError

            raise ConfigurationError("EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER=openai")
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.EMBEDDING_API_KEY)
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model_name, input=batch)
        return [item.embedding for item in response.data]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors: list[list[float]] = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                vectors.extend(self._embed_batch(batch))
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"OpenAI embedding generation failed: {exc}") from exc

        self._validate_dimension(vectors)
        return vectors


def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingService(settings)
    if settings.EMBEDDING_PROVIDER == "ollama":
        return OllamaEmbeddingService(settings)
    return LocalEmbeddingService(settings)
