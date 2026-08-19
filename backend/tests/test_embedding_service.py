import pytest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.exceptions import VectorDimensionMismatchError, EmbeddingError
from app.embeddings.embedding_service import (
    EmbeddingService,
    LocalEmbeddingService,
    OllamaEmbeddingService,
    OpenAIEmbeddingService,
    get_embedding_service,
)


def test_ollama_embedding_service_init():
    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
        LLM_BASE_URL="http://ollama:11434",
    )
    service = OllamaEmbeddingService(settings)
    assert service.model_name == "nomic-embed-text"
    assert service.dimension == 768
    assert service.base_url == "http://ollama:11434"


def test_get_embedding_service_returns_ollama_instance(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "768")
    
    # Reset lru_cache if any
    from app.core.config import get_settings
    get_settings.cache_clear()

    service = get_embedding_service()
    assert isinstance(service, OllamaEmbeddingService)
    assert service.dimension == 768


@patch("httpx.Client")
def test_ollama_embedding_service_embed_texts_success(mock_client_cls):
    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
        LLM_BASE_URL="http://ollama:11434",
    )
    service = OllamaEmbeddingService(settings)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "embeddings": [[0.1] * 768]
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    vectors = service.embed_texts(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 768


@patch("httpx.Client")
def test_ollama_embedding_service_dimension_mismatch(mock_client_cls):
    settings = Settings(
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
        LLM_BASE_URL="http://ollama:11434",
    )
    service = OllamaEmbeddingService(settings)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "embeddings": [[0.1] * 384]  # Wrong dimension (384 instead of 768)
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value.__enter__.return_value = mock_client

    with pytest.raises(VectorDimensionMismatchError):
        service.embed_texts(["hello world"])
