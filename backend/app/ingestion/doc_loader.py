"""
Legacy .doc (binary Microsoft Word 97-2003) extraction.

python-docx and pypdf cannot read the old binary .doc format at all, so
direct extraction is not reliable in pure Python. As a clear fallback
mechanism, this loader shells out to LibreOffice (`soffice --headless`)
to convert the .doc file to .docx, then reuses `DOCXLoader` on the
result. If LibreOffice is not available in the runtime environment, a
clear, actionable error is raised instead of failing silently.

This keeps the fallback mechanism swappable: `antiword`, `catdoc`, or a
cloud conversion service could be substituted here without touching
any other part of the ingestion pipeline.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.exceptions import ExtractionError
from app.core.logging import get_logger
from app.ingestion.base import DocumentLoader, DocumentPage
from app.ingestion.docx_loader import DOCXLoader

logger = get_logger(__name__)


class DOCLoader(DocumentLoader):
    @staticmethod
    def supports(extension: str) -> bool:
        return extension.lower() == "doc"

    def load(self, file_path: str) -> list[DocumentPage]:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise ExtractionError(
                "Legacy .doc extraction requires LibreOffice ('soffice'), which is not "
                "installed in this environment. Install libreoffice, or convert the file "
                "to .docx and re-upload it."
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                subprocess.run(
                    [
                        soffice,
                        "--headless",
                        "--norestore",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        tmp_dir,
                        file_path,
                    ],
                    check=True,
                    capture_output=True,
                    timeout=90,
                )
            except subprocess.TimeoutExpired as exc:
                raise ExtractionError("Timed out converting legacy .doc file to .docx.") from exc
            except subprocess.CalledProcessError as exc:
                logger.error(
                    "doc_conversion_failed",
                    extra={"extra_fields": {"stderr": exc.stderr.decode(errors="ignore")[:500]}},
                )
                raise ExtractionError(f"Failed to convert legacy .doc file: {exc}") from exc

            converted = list(Path(tmp_dir).glob("*.docx"))
            if not converted:
                raise ExtractionError("LibreOffice conversion did not produce an output file.")

            pages = DOCXLoader().load(str(converted[0]))
            for p in pages:
                p.metadata["converted_from"] = "doc"
            return pages
