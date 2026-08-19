from fastapi import APIRouter, Depends

from app.api.dependencies import get_retriever
from app.retrieval.retriever import Retriever
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic search",
    description="Runs similarity search over ingested document chunks and returns the matching chunks.",
)
async def search(payload: SearchRequest, retriever: Retriever = Depends(get_retriever)):
    results = await retriever.retrieve(
        query=payload.query, top_k=payload.top_k, document_id=payload.document_id
    )
    return SearchResponse(
        query=payload.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                filename=r.filename,
                page=r.page_number,
                section=r.section,
                content=r.content,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ],
    )
