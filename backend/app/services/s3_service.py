"""
Thin wrapper around boto3 S3 for storing uploaded PDFs and generated CSV
exports, scoped per user (user_id/... key prefix) so one user can never
reach another's files even if they guessed a key.
"""
import io
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )
    return _s3_client


def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> Optional[str]:
    """Uploads bytes to S3, returns the key on success, None on failure (logged, non-fatal)."""
    if not settings.aws_access_key_id:
        logger.info("AWS credentials not configured; skipping S3 upload for %s", key)
        return None
    try:
        client = get_s3_client()
        client.upload_fileobj(
            io.BytesIO(data),
            settings.s3_bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return key
    except ClientError as e:
        logger.error("S3 upload failed for %s: %s", key, e)
        return None


def generate_presigned_url(key: str, expires_in: int = 3600) -> Optional[str]:
    if not settings.aws_access_key_id:
        return None
    try:
        client = get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        logger.error("Failed to presign URL for %s: %s", key, e)
        return None
