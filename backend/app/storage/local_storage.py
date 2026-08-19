"""
Local filesystem storage implementation.

Filenames are sanitized and made unique to prevent path traversal and
overwrite issues; the original filename is preserved separately in the
database record for display purposes.
"""
import os
import re
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.storage.base import StorageService

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename)
    name = _UNSAFE_CHARS_RE.sub("_", name)
    return name[:255] or "file"


class LocalStorageService(StorageService):
    def __init__(self, base_path: str | None = None):
        settings = get_settings()
        self.base_path = Path(base_path or settings.STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, filename: str) -> str:
        safe_name = sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        target = self.base_path / unique_name
        with open(target, "wb") as f:
            f.write(content)
        return unique_name

    def delete(self, storage_path: str) -> None:
        target = self.base_path / storage_path
        if target.exists():
            target.unlink()

    def exists(self, storage_path: str) -> bool:
        return (self.base_path / storage_path).exists()

    def full_path(self, storage_path: str) -> str:
        return str(self.base_path / storage_path)
