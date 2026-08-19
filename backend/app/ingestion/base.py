"""
Common document loader interface.

Every loader (pdf/doc/docx/txt/raw-text) implements `DocumentLoader.load()`
and returns a normalized `list[DocumentPage]`. This keeps file-format
extraction logic completely decoupled from cleaning, chunking and
embedding logic downstream.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentPage:
    """A single normalized unit of extracted text (one PDF page, one DOCX
    'document' since docx has no hard pages, one TXT file, etc.)."""

    text: str
    page_number: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentLoader(ABC):
    """Abstract interface every file-type loader must implement."""

    @abstractmethod
    def load(self, file_path: str) -> list[DocumentPage]:
        """Extract text from `file_path` and return normalized pages."""
        raise NotImplementedError

    @staticmethod
    def supports(extension: str) -> bool:
        raise NotImplementedError
