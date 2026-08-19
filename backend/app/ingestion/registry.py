"""
Maps a file extension to its `DocumentLoader` implementation.
Adding a new file type only requires registering it here.
"""
from app.core.exceptions import UnsupportedFileTypeError
from app.ingestion.base import DocumentLoader
from app.ingestion.doc_loader import DOCLoader
from app.ingestion.docx_loader import DOCXLoader
from app.ingestion.pdf_loader import PDFLoader
from app.ingestion.txt_loader import TXTLoader

_LOADERS: dict[str, type[DocumentLoader]] = {
    "pdf": PDFLoader,
    "doc": DOCLoader,
    "docx": DOCXLoader,
    "txt": TXTLoader,
}


def get_loader(extension: str) -> DocumentLoader:
    ext = extension.lower().lstrip(".")
    loader_cls = _LOADERS.get(ext)
    if loader_cls is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{ext}'. Supported types: {', '.join(sorted(_LOADERS))}"
        )
    return loader_cls()
