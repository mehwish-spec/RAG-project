"""
File storage abstraction. `LocalStorageService` is the default
implementation; an S3-backed implementation can be added later by
implementing the same interface without touching calling code.
"""
from abc import ABC, abstractmethod


class StorageService(ABC):
    @abstractmethod
    def save(self, content: bytes, filename: str) -> str:
        """Persist `content` under a storage-safe name derived from `filename`.
        Returns the storage path/key."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def full_path(self, storage_path: str) -> str:
        raise NotImplementedError
