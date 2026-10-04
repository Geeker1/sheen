"""Raw snapshot archive (S3 in AWS, MinIO locally)."""

import boto3
import structlog
from botocore.exceptions import ClientError

from sheen.config import get_settings

log = structlog.get_logger()


def archive(key: str, body: bytes, content_type: str = "application/json") -> str | None:
    """Store bytes under `key`. Returns the s3:// URI, or None if storage is unavailable.

    Archiving is best-effort: the raw payload is also kept in Postgres, so a
    storage outage shouldn't block ingestion. It is logged loudly instead.
    """
    s = get_settings()
    client = boto3.client("s3", endpoint_url=s.s3_endpoint_url)
    try:
        # In AWS the bucket is owned by Terraform; only create it for local S3.
        if s.s3_endpoint_url:
            try:
                client.head_bucket(Bucket=s.s3_bucket)
            except ClientError:
                client.create_bucket(
                    Bucket=s.s3_bucket,
                    CreateBucketConfiguration={
                        "LocationConstraint": client.meta.region_name  # type: ignore[typeddict-item]
                    },
                )
        client.put_object(Bucket=s.s3_bucket, Key=key, Body=body, ContentType=content_type)
    except Exception as exc:
        log.warning("archive.failed", key=key, error=str(exc))
        return None
    return f"s3://{s.s3_bucket}/{key}"
