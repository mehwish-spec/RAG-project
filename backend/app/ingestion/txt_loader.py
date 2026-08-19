"""
Plain-text (.txt) file extraction.

Reads the file safely as UTF-8 (falling back to latin-1 for files with
minor encoding issues rather than crashing outright), handles different
newline conventions, and rejects genuinely empty files with a clear
validation error.
"""
from app.core.exceptions import NoExtractableTextError
from app.ingestion.base import DocumentLoader, DocumentPage


class TXTLoader(DocumentLoader):
    @staticmethod
    def supports(extension: str) -> bool:
        return extension.lower() == "txt"

    def load(self, file_path: str) -> list[DocumentPage]:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        text = self._decode(raw_bytes)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        if not text.strip():
            raise NoExtractableTextError("The uploaded .txt file is empty.")

        return [
            DocumentPage(
                text=text,
                page_number=None,
                metadata={"encoding": "utf-8", "char_count": len(text)},
            )
        ]

    @staticmethod
    def _decode(raw_bytes: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        # Last resort: replace undecodable bytes rather than crash.
        return raw_bytes.decode("utf-8", errors="replace")
