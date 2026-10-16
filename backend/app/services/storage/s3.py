import logging
import os
from typing import Any, Optional
import botocore
import botocore.config
import botocore.exceptions
import boto3

from app.config import settings
from app.services.storage.base import (
    StorageProvider,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
    compute_sha256 as _compute_sha256,
)

logger = logging.getLogger("app.storage.s3")

class S3StorageAdapter(StorageProvider):
    """
    S3-compatible storage adapter for durable document management.
    Supports AWS S3, MinIO, LocalStack, and Ceph RGW.
    Enforces tenant boundaries, private object access, and short-lived presigned URLs.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        sse_algorithm: Optional[str] = None,
        presigned_expiration_seconds: int = 900,
        boto3_client: Optional[Any] = None,
    ):
        self.bucket_name = (bucket_name if bucket_name is not None else settings.S3_BUCKET_NAME).strip()
        self.region_name = region_name or settings.S3_REGION_NAME or "us-east-1"
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self.sse_algorithm = sse_algorithm or settings.S3_SSE_ALGORITHM
        self.presigned_expiration_seconds = presigned_expiration_seconds or settings.S3_PRESIGNED_EXPIRATION_SECONDS
        self._injected_client = boto3_client
        self._client = None

    def _get_client(self) -> Any:
        if self._injected_client is not None:
            return self._injected_client

        if self._client is None:
            if not self.bucket_name:
                raise StorageError(
                    "Configuration Error: S3_BUCKET_NAME is required when using the S3 storage provider."
                )

            client_kwargs: dict[str, Any] = {
                "service_name": "s3",
                "region_name": self.region_name,
                "config": botocore.config.Config(
                    connect_timeout=10,
                    read_timeout=30,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            }

            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            if self.access_key_id and self.secret_access_key:
                client_kwargs["aws_access_key_id"] = self.access_key_id
                client_kwargs["aws_secret_access_key"] = self.secret_access_key

            try:
                self._client = boto3.client(**client_kwargs)
            except Exception as e:
                logger.error("Failed to initialize S3 client: %s", type(e).__name__)
                raise StorageError(f"Failed to initialize S3 storage client: {type(e).__name__}") from e

        return self._client

    def _resolve_key(self, relative_path: str, expected_tenant_id: Optional[str] = None) -> str:
        """
        Normalizes and sanitizes S3 object keys.
        Rejects directory traversal, relative traversal, and enforces tenant isolation.
        """
        if not relative_path or not relative_path.strip():
            raise StoragePermissionError("Invalid storage path: empty path.")

        # Normalize path separators
        clean_key = relative_path.replace("\\", "/").strip().lstrip("/")
        parts = clean_key.split("/")

        if ".." in parts or "." in parts:
            raise StoragePermissionError("Invalid storage path: directory traversal prohibited.")

        if expected_tenant_id:
            expected_prefix = expected_tenant_id.strip().rstrip("/") + "/"
            if not clean_key.startswith(expected_prefix):
                raise StoragePermissionError(
                    "Cross-tenant storage access prohibited: path escapes tenant directory."
                )

        return clean_key

    def save_file(self, relative_path: str, content: bytes, tenant_id: Optional[str] = None) -> str:
        key = self._resolve_key(relative_path, expected_tenant_id=tenant_id)
        client = self._get_client()

        extra_args: dict[str, Any] = {}
        if self.sse_algorithm:
            extra_args["ServerSideEncryption"] = self.sse_algorithm

        sha256_hash = self.compute_sha256(content)
        extra_args["Metadata"] = {
            "sha256": sha256_hash,
            "size": str(len(content)),
        }

        try:
            client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                **extra_args,
            )
            return key
        except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
            logger.error("S3 upload failed for key %s: %s", key, type(e).__name__)
            raise StorageError(f"S3 upload failed: {type(e).__name__}") from e
        except Exception as e:
            logger.error("Unexpected error during S3 upload: %s", type(e).__name__)
            raise StorageError(f"Unexpected error during S3 upload: {type(e).__name__}") from e

    def get_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        key = self._resolve_key(relative_path, expected_tenant_id=tenant_id)
        client = self._get_client()

        try:
            response = client.get_object(Bucket=self.bucket_name, Key=key)
            body = response["Body"].read()
            return body
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                raise StorageNotFoundError(f"Storage object not found: {key}") from e
            logger.error("S3 download failed for key %s: %s", key, error_code)
            raise StorageError(f"S3 download failed with code {error_code}") from e
        except (botocore.exceptions.BotoCoreError, Exception) as e:
            logger.error("S3 download failed: %s", type(e).__name__)
            raise StorageError(f"S3 download failed: {type(e).__name__}") from e

    def read_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bytes:
        return self.get_file(relative_path, tenant_id=tenant_id)

    def file_exists(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        key = self._resolve_key(relative_path, expected_tenant_id=tenant_id)
        client = self._get_client()

        try:
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                return False
            logger.error("S3 head_object error for key %s: %s", key, error_code)
            raise StorageError(f"S3 existence check failed with code {error_code}") from e
        except Exception as e:
            logger.error("S3 head_object unexpected error: %s", type(e).__name__)
            raise StorageError(f"S3 existence check failed: {type(e).__name__}") from e

    def delete_file(self, relative_path: str, tenant_id: Optional[str] = None) -> bool:
        key = self._resolve_key(relative_path, expected_tenant_id=tenant_id)
        client = self._get_client()

        try:
            client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error("S3 delete failed for key %s: %s", key, error_code)
            raise StorageError(f"S3 delete failed with code {error_code}") from e
        except Exception as e:
            logger.error("S3 delete unexpected error: %s", type(e).__name__)
            raise StorageError(f"S3 delete failed: {type(e).__name__}") from e

    def get_download_url(
        self,
        relative_path: str,
        tenant_id: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generates a short-lived, pre-signed download URL.
        Only called AFTER server-side tenant authentication and authorization have succeeded.
        """
        key = self._resolve_key(relative_path, expected_tenant_id=tenant_id)
        client = self._get_client()
        expiry = expires_in or self.presigned_expiration_seconds

        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiry,
            )
            return url
        except Exception as e:
            logger.error("Failed to generate presigned S3 URL: %s", type(e).__name__)
            raise StorageError(f"Failed to generate presigned URL: {type(e).__name__}") from e

    def compute_sha256(self, content: bytes) -> str:
        return _compute_sha256(content)
