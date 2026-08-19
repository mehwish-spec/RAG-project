from fastapi import APIRouter, Depends

from app.api.dependencies import get_rag_pipeline
from app.rag.pipeline import RAGPipeline
from app.schemas.chat import ChatData, ChatRequest, ChatResponse, SourceCitation

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question over ingested documents",
    description="Runs the full RAG pipeline: retrieval, optional reranking, context construction, "
    "LLM generation, and returns the answer with source citations.",
)
async def chat(payload: ChatRequest, pipeline: RAGPipeline = Depends(get_rag_pipeline)):
    result = await pipeline.run(query=payload.query, top_k=payload.top_k, document_id=payload.document_id)
    return ChatResponse(
        data=ChatData(
            answer=result.answer,
            sources=[
                SourceCitation(
                    document_id=s.document_id,
                    filename=s.filename,
                    page=s.page,
                    chunk_id=s.chunk_id,
                    score=s.score,
                )
                for s in result.sources
            ],
        )
    )
