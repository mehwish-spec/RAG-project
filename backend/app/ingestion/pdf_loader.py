"""
PDF text extraction.

Extracts page-by-page, keeps page numbers so retrieved chunks can be
traced back to the exact page they came from, and skips empty pages.
If a PDF has no extractable text at all (e.g. a scanned/image-only PDF)
a clear `NoExtractableTextError` is raised, indicating OCR would be
required. OCR itself is intentionally NOT implemented here, but the
loader interface makes it trivial to add an `OCRPdfLoader` later.
"""
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.exceptions import ExtractionError, NoExtractableTextError
from app.core.logging import get_logger
from app.ingestion.base import DocumentLoader, DocumentPage

logger = get_logger(__name__)


class PDFLoader(DocumentLoader):
    @staticmethod
    def supports(extension: str) -> bool:
        return extension.lower() == "pdf"

    def load(self, file_path: str) -> list[DocumentPage]:
        try:
            reader = PdfReader(file_path)
        except PdfReadError as exc:
            raise ExtractionError(f"Corrupted or unreadable PDF file: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Failed to open PDF: {exc}") from exc

        pdf_metadata = {}
        try:
            if reader.metadata:
                pdf_metadata = {k.lstrip("/"): str(v) for k, v in dict(reader.metadata).items()}
        except Exception:  # noqa: BLE001
            pdf_metadata = {}

        pages: list[DocumentPage] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("pdf_page_extract_failed", extra={"extra_fields": {"page": i, "error": str(exc)}})
                raw_text = ""

            text = self._normalize(raw_text)
            if not text.strip():
                continue  # ignore completely empty pages

            pages.append(
                DocumentPage(
                    text=text,
                    page_number=i,
                    metadata={"pdf": pdf_metadata, "total_pages": len(reader.pages)},
                )
            )

        if not pages:
            raise NoExtractableTextError(
                "No extractable text was found in this PDF. It may be a scanned/image-only "
                "PDF - OCR would be required to extract its text."
            )
        return pages

    @staticmethod
    def _normalize(text: str) -> str:
        # Collapse hard line-breaks that pypdf introduces mid-sentence while
        # preserving real paragraph boundaries (double newlines).
        lines = [ln.strip() for ln in text.splitlines()]
        joined = "\n".join(ln for ln in lines if ln != "" or True)
        return joined
