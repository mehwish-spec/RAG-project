import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    content_hash: str
    status: str
    error_message: str | None = None
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentResponse]


class RawTextIngestRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw text content to ingest")
    filename: str = Field(default="raw_text.txt", description="Logical filename to store this text under")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool
    chunks_deleted: int


class ReindexResponse(BaseModel):
    id: uuid.UUID
    status: str
