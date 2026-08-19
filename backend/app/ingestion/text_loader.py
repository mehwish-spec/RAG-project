"""
Loader for raw text submitted directly via the API (no file upload).

Reuses the same `DocumentPage` normalization as file-based loaders so
the rest of the pipeline (cleaning/chunking/embedding) treats raw text
identically to an extracted file.
"""
from app.core.exceptions import NoExtractableTextError
from app.ingestion.base import DocumentPage


class RawTextLoader:
    @staticmethod
    def load(text: str, extra_metadata: dict | None = None) -> list[DocumentPage]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if not normalized.strip():
            raise NoExtractableTextError("Submitted text is empty.")
        return [
            DocumentPage(
                text=normalized,
                page_number=None,
                metadata={"source_type": "raw_text", **(extra_metadata or {})},
            )
        ]
