import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_db, get_rag_pipeline, get_retriever
from app.main import app
from app.rag.pipeline import RAGResult, RAGSource
from app.vectorstore.base import VectorSearchResult


class _FakeSession:
    """Stand-in for an AsyncSession; only used so `get_db` can be overridden
    without requiring a live Postgres connection for tests that never
    actually touch the database (they raise validation errors first)."""

    async def close(self):
        pass


async def _fake_get_db():
    yield _FakeSession()


class _FakeRetriever:
    async def retrieve(self, query, top_k=None, similarity_threshold=None, document_id=None):
        return [
            VectorSearchResult(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Refunds are accepted within 30 days of purchase.",
                page_number=2,
                section="Refund Policy",
                metadata={},
                score=0.91,
                filename="policy.pdf",
            )
        ]


class _FakePipeline:
    async def run(self, query, top_k=None, document_id=None):
        return RAGResult(
            answer="Refunds are accepted within 30 days of purchase.",
            sources=[
                RAGSource(
                    document_id=uuid.uuid4(),
                    filename="policy.pdf",
                    page=2,
                    chunk_id=uuid.uuid4(),
                    score=0.91,
                )
            ],
        )


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_retriever] = lambda: _FakeRetriever()
    app.dependency_overrides[get_rag_pipeline] = lambda: _FakePipeline()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_rejects_unsupported_file_type(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malware.exe", b"binary content", "application/octet-stream")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_search_returns_ranked_chunks(client):
    response = client.post("/api/v1/search", json={"query": "refund policy", "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "refund policy"
    assert len(body["results"]) == 1
    assert body["results"][0]["filename"] == "policy.pdf"
    assert body["results"][0]["score"] == 0.91


def test_search_rejects_empty_query(client):
    response = client.post("/api/v1/search", json={"query": ""})
    assert response.status_code == 422  # pydantic min_length validation


def test_chat_returns_answer_with_sources(client):
    response = client.post("/api/v1/chat", json={"query": "What is the refund policy?"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "30 days" in body["data"]["answer"]
    assert len(body["data"]["sources"]) == 1
    assert body["data"]["sources"][0]["filename"] == "policy.pdf"
    assert body["data"]["sources"][0]["page"] == 2
