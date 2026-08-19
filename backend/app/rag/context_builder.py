"""
Thin wrapper around prompt.build_context so the pipeline module stays
focused on orchestration rather than string formatting.
"""
from app.llm.prompt import build_context
from app.vectorstore.base import VectorSearchResult


def construct_context(chunks: list[VectorSearchResult], max_chars: int) -> str:
    return build_context(chunks, max_chars)
