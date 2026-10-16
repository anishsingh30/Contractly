import hashlib
from typing import Optional, Protocol, runtime_checkable

class StorageError(Exception):
    """Base exception for all storage failures."""
    pass

class StorageNotFoundError(StorageError, FileNotFoundError):
    """Raised when an object or file cannot be located in the storage provider."""
    pass

class StoragePermissionError(StorageError, ValueError):
    """Raised when an object key attempts cross-tenant access or path traversal."""
    pass

def compute_sha256(content: bytes) -> str:
    """Computes SHA-256 hex digest for binary content."""
    hasher = hashlib.sha256()
    hasher.update(content)
    return hasher.hexdigest()

@runtime_checkable
class StorageProvider(Protocol):
    def save_file(self, relative_path: str, content: bytes, tenant_id: Optional[str] = None) -> str:
        """Saves binary file bytes and returns storage URI or identifier."""
        ...

    def get_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        """Retrieves binary bytes from storage."""
        ...

    def read_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        """Alias/convenience for get_file."""
        ...

    def file_exists(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        """Checks if file exists at path."""
        ...

    def delete_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        """Deletes file from storage."""
        ...

    def get_download_url(self, relative_path: str, tenant_id: Optional[str] = None, expires_in: int = 900) -> Optional[str]:
        """Generates a short-lived authorized download URL if supported by provider."""
        ...
