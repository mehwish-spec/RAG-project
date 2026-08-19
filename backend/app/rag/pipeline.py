"""
Central RAG pipeline.

    validate query -> embed query -> retrieve candidates -> similarity
    filter -> optional rerank -> select/format context -> build prompt
    -> call LLM -> extract citations -> return answer + sources

This is the ONLY place that orchestrates the full query flow - API
routes call `RAGPipeline.run()` and nothing else, keeping this logic
out of the HTTP layer entirely.
"""
import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import InvalidQueryError
from app.core.logging import get_logger
from app.llm.llm_service import LLMService
from app.llm.prompt import SYSTEM_PROMPT, build_user_prompt
from app.rag.context_builder import construct_context
from app.retrieval.reranker import Reranker
from app.retrieval.retriever import Retriever
from app.vectorstore.base import VectorSearchResult

logger = get_logger(__name__)


@dataclass
class RAGSource:
    document_id: uuid.UUID
    filename: str
    page: int | None
    chunk_id: uuid.UUID
    score: float


@dataclass
class RAGResult:
    answer: str
    sources: list[RAGSource]


class RAGPipeline:
    def __init__(self, retriever: Retriever, reranker: Reranker, llm_service: LLMService, settings: Settings):
        self.retriever = retriever
        self.reranker = reranker
        self.llm_service = llm_service
        self.settings = settings

    async def run(
        self,
        query: str,
        top_k: int | None = None,
        document_id: uuid.UUID | None = None,
    ) -> RAGResult:
        query = (query or "").strip()
        if not query:
            raise InvalidQueryError("Query must not be empty.")

        candidates = await self.retriever.retrieve(query=query, top_k=top_k, document_id=document_id)
        logger.info("retrieval_complete", extra={"extra_fields": {"query": query, "candidate_count": len(candidates)}})

        ranked = self.reranker.rerank(query, candidates)

        if not ranked:
            answer = "The information is not available in the uploaded documents."
            return RAGResult(answer=answer, sources=[])

        context = construct_context(ranked, self.settings.MAX_CONTEXT_CHARS)
        user_prompt = build_user_prompt(query, context)

        logger.info("llm_request", extra={"extra_fields": {"model": self.settings.LLM_MODEL, "context_chars": len(context)}})
        answer = await self.llm_service.generate(SYSTEM_PROMPT, user_prompt)

        sources = self._build_sources(ranked)
        return RAGResult(answer=answer or "The model did not return an answer.", sources=sources)

    @staticmethod
    def _build_sources(chunks: list[VectorSearchResult]) -> list[RAGSource]:
        sources: list[RAGSource] = []
        seen: set[tuple] = set()
        for c in chunks:
            key = (c.document_id, c.page_number)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                RAGSource(
                    document_id=c.document_id,
                    filename=c.filename,
                    page=c.page_number,
                    chunk_id=c.chunk_id,
                    score=c.score,
                )
            )
        return sources
