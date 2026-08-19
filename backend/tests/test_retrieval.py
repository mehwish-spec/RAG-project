import uuid

from app.retrieval.reranker import LexicalOverlapReranker, NoopReranker, get_reranker
from app.vectorstore.base import VectorSearchResult


def _result(content: str, score: float) -> VectorSearchResult:
    return VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        page_number=1,
        section=None,
        metadata={},
        score=score,
        filename="doc.pdf",
    )


def test_noop_reranker_returns_input_unchanged():
    chunks = [_result("a", 0.5), _result("b", 0.9)]
    reranked = NoopReranker().rerank("query", chunks)
    assert reranked == chunks


def test_lexical_reranker_boosts_term_overlap_above_pure_vector_score():
    irrelevant_but_high_score = _result("completely unrelated filler content about cats", 0.85)
    relevant_but_lower_score = _result("refund policy allows returns within 30 days", 0.55)

    reranked = LexicalOverlapReranker().rerank(
        "what is the refund policy", [irrelevant_but_high_score, relevant_but_lower_score]
    )
    assert reranked[0] is relevant_but_lower_score


def test_get_reranker_factory_respects_enabled_flag():
    assert isinstance(get_reranker(False), NoopReranker)
    assert isinstance(get_reranker(True), LexicalOverlapReranker)
