"""
Helpers for building consistent document- and chunk-level metadata.
"""
import hashlib
from datetime import datetime, timezone
from typing import Any


def compute_content_hash(content: bytes) -> str:
    """SHA-256 hash used for document deduplication."""
    return hashlib.sha256(content).hexdigest()


def build_document_metadata(
    *,
    extension: str,
    source_type: str = "file",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "extension": extension,
        "source_type": source_type,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }


def build_chunk_metadata(
    *,
    document_id: str,
    chunk_index: int,
    page_number: int | None,
    section: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
        "page_number": page_number,
        "section": section,
        **(extra or {}),
    }
