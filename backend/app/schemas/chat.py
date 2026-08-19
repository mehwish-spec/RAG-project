import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    document_id: uuid.UUID | None = Field(default=None, description="Optional filter to a single document")


class SourceCitation(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int | None = None
    chunk_id: uuid.UUID
    score: float


class ChatData(BaseModel):
    answer: str
    sources: list[SourceCitation]


class ChatResponse(BaseModel):
    success: bool = True
    data: ChatData
