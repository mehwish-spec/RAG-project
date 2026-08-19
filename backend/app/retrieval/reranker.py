"""
Reranker abstraction.

Disabled by default (`RERANKING_ENABLED=false`), in which case results
pass straight through unchanged. When enabled, `LexicalOverlapReranker`
gives a lightweight, dependency-free re-scoring based on query/content
term overlap combined with the original vector similarity score. It is
intentionally simple to keep the default stack lightweight; a heavier
cross-encoder model can be dropped in behind the same `Reranker`
interface without touching the RAG pipeline.
"""
import re
from abc import ABC, abstractmethod

from app.vectorstore.base import VectorSearchResult

_WORD_RE = re.compile(r"[a-z0-9]+")


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: list[VectorSearchResult]) -> list[VectorSearchResult]:
        raise NotImplementedError


class NoopReranker(Reranker):
    def rerank(self, query: str, chunks: list[VectorSearchResult]) -> list[VectorSearchResult]:
        return chunks


class LexicalOverlapReranker(Reranker):
    def rerank(self, query: str, chunks: list[VectorSearchResult]) -> list[VectorSearchResult]:
        query_terms = set(_WORD_RE.findall(query.lower()))
        if not query_terms:
            return chunks

        def combined_score(chunk: VectorSearchResult) -> float:
            content_terms = set(_WORD_RE.findall(chunk.content.lower()))
            overlap = len(query_terms & content_terms) / max(len(query_terms), 1)
            return 0.5 * chunk.score + 0.5 * overlap

        return sorted(chunks, key=combined_score, reverse=True)


def get_reranker(enabled: bool) -> Reranker:
    return LexicalOverlapReranker() if enabled else NoopReranker()
