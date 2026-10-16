import os
import hashlib
from typing import Optional
from app.config import settings
from app.services.storage.base import (
    StorageProvider,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
    compute_sha256 as _compute_sha256,
)

class LocalStorageAdapter(StorageProvider):
    def __init__(self, base_dir: str = settings.LOCAL_STORAGE_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_path(self, relative_path: str, expected_tenant_id: Optional[str] = None) -> str:
        # Sanitize path to prevent directory traversal
        normalized = os.path.normpath(relative_path)
        parts = normalized.replace("\\", "/").split("/")
        if ".." in parts:
            raise StoragePermissionError("Invalid storage path: directory traversal prohibited.")

        clean_rel = normalized.lstrip(r"\/")
        full_path = os.path.join(self.base_dir, clean_rel)
        if not full_path.startswith(self.base_dir):
            raise StoragePermissionError("Invalid storage path: directory traversal prohibited.")
        if expected_tenant_id:
            expected_prefix = os.path.join(self.base_dir, expected_tenant_id)
            if not full_path.startswith(expected_prefix):
                raise StoragePermissionError("Cross-tenant storage access prohibited: path escapes tenant directory.")
        return full_path

    def save_file(self, relative_path: str, content: bytes, tenant_id: Optional[str] = None) -> str:
        target_path = self._resolve_path(relative_path, expected_tenant_id=tenant_id)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            with open(target_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise StorageError(f"Failed to write local storage file: {e}") from e
        return target_path

    def get_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        target_path = self._resolve_path(relative_path, expected_tenant_id=tenant_id)
        if not os.path.exists(target_path):
            raise StorageNotFoundError(f"Storage object not found: {relative_path}")
        try:
            with open(target_path, "rb") as f:
                return f.read()
        except Exception as e:
            raise StorageError(f"Failed to read local storage file: {e}") from e

    def read_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        """Alias for get_file."""
        return self.get_file(relative_path, tenant_id=tenant_id)

    def file_exists(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        target_path = self._resolve_path(relative_path, expected_tenant_id=tenant_id)
        return os.path.exists(target_path)

    def delete_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        target_path = self._resolve_path(relative_path, expected_tenant_id=tenant_id)
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                return True
            except Exception as e:
                raise StorageError(f"Failed to delete local storage file: {e}") from e
        return False

    def get_download_url(self, relative_path: str, tenant_id: Optional[str] = None, expires_in: int = 900) -> Optional[str]:
        """Local adapter serves files via server endpoints, not direct public/presigned URLs."""
        return None

    def compute_sha256(self, content: bytes) -> str:
        return _compute_sha256(content)

def compute_sha256(content: bytes) -> str:
    return _compute_sha256(content)

class _StorageClientWrapper:
    """Delegates to the active configured StorageProvider (Local or S3)."""
    def __getattr__(self, name: str):
        from app.services.storage import storage_client as active_client
        return getattr(active_client, name)

storage_client = _StorageClientWrapper()
