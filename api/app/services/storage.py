"""MinIO storage service."""

from __future__ import annotations

import io
from datetime import timedelta

import structlog
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Bucket constants
# ---------------------------------------------------------------------------

RAW_FILES_BUCKET = "raw-files"
EXPORTS_BUCKET = "exports"


# ---------------------------------------------------------------------------
# StorageService
# ---------------------------------------------------------------------------

class StorageService:
    """Thin wrapper around the MinIO Python SDK."""

    def __init__(self) -> None:
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload *data* to *bucket*/*key*. Returns the storage key."""
        self._ensure_bucket(bucket)
        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("storage_upload", bucket=bucket, key=key, size=len(data))
        return key

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_file(self, bucket: str, key: str) -> bytes:
        """Download the object at *bucket*/*key* and return its bytes."""
        response = self._client.get_object(bucket_name=bucket, object_name=key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_file(self, bucket: str, key: str) -> None:
        """Delete the object at *bucket*/*key*."""
        self._client.remove_object(bucket_name=bucket, object_name=key)
        logger.info("storage_delete", bucket=bucket, key=key)

    # ------------------------------------------------------------------
    # Presigned URL
    # ------------------------------------------------------------------

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_seconds: int = 3600,
    ) -> str:
        """Return a presigned GET URL valid for *expires_seconds* seconds."""
        url = self._client.presigned_get_object(
            bucket_name=bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_bucket(self, bucket: str) -> None:
        """Create *bucket* if it does not already exist."""
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                logger.info("storage_bucket_created", bucket=bucket)
        except S3Error as exc:
            logger.warning("storage_bucket_check_failed", bucket=bucket, error=str(exc))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_storage: StorageService | None = None


def get_storage() -> StorageService:
    """Return the application-level StorageService singleton."""
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage
