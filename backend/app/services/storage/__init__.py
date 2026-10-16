from typing import Any, Optional
from app.config import settings
from app.services.storage.base import (
    StorageProvider,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
    compute_sha256,
)
from app.services.storage.local import LocalStorageAdapter
from app.services.storage.s3 import S3StorageAdapter

def get_storage_provider(config: Optional[Any] = None) -> StorageProvider:
    """
    Factory function to get the configured StorageProvider instance.
    Retains LocalStorageAdapter as the development default.
    """
    cfg = config or settings
    provider_type = (getattr(cfg, "STORAGE_PROVIDER", "local") or "local").lower().strip()

    if provider_type == "s3":
        return S3StorageAdapter(
            bucket_name=getattr(cfg, "S3_BUCKET_NAME", ""),
            region_name=getattr(cfg, "S3_REGION_NAME", "us-east-1"),
            endpoint_url=getattr(cfg, "S3_ENDPOINT_URL", None),
            access_key_id=getattr(cfg, "S3_ACCESS_KEY_ID", None),
            secret_access_key=getattr(cfg, "S3_SECRET_ACCESS_KEY", None),
            sse_algorithm=getattr(cfg, "S3_SSE_ALGORITHM", None),
            presigned_expiration_seconds=getattr(cfg, "S3_PRESIGNED_EXPIRATION_SECONDS", 900),
        )

    return LocalStorageAdapter(base_dir=getattr(cfg, "LOCAL_STORAGE_DIR", settings.LOCAL_STORAGE_DIR))

class StorageClientProxy:
    """
    Dynamic proxy that routes calls to the configured storage provider.
    Ensures that runtime config overrides immediately apply without stale instances.
    """
    def _get_provider(self) -> StorageProvider:
        return get_storage_provider()

    def save_file(self, relative_path: str, content: bytes, tenant_id: Optional[str] = None) -> str:
        return self._get_provider().save_file(relative_path, content, tenant_id=tenant_id)

    def get_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        return self._get_provider().get_file(relative_path, tenant_id=tenant_id)

    def read_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        return self._get_provider().read_file(relative_path, tenant_id=tenant_id)

    def file_exists(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        return self._get_provider().file_exists(relative_path, tenant_id=tenant_id)

    def delete_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        return self._get_provider().delete_file(relative_path, tenant_id=tenant_id)

    def get_download_url(self, relative_path: str, tenant_id: Optional[str] = None, expires_in: int = 900) -> Optional[str]:
        return self._get_provider().get_download_url(relative_path, tenant_id=tenant_id, expires_in=expires_in)

    def compute_sha256(self, content: bytes) -> str:
        return self._get_provider().compute_sha256(content)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_provider(), name)

storage_client = StorageClientProxy()

__all__ = [
    "StorageProvider",
    "StorageError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "LocalStorageAdapter",
    "S3StorageAdapter",
    "get_storage_provider",
    "storage_client",
    "compute_sha256",
]
