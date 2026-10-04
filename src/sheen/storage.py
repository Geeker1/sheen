"""Raw snapshot archive: S3 on AWS, LocalStack locally."""

import boto3
import structlog
from botocore.exceptions import ClientError

from sheen.config import get_settings

log = structlog.get_logger()


def archive(key: str, body: bytes) -> str | None:
    """Store a JSON snapshot. Returns its s3:// URI, or None on failure.

    Best-effort: the payload is also in Postgres, so an S3 outage logs a
    warning instead of failing the ingest.
    """
    s = get_settings()
    client = boto3.client("s3", endpoint_url=s.s3_endpoint_url)
    try:
        # On AWS, Terraform owns the bucket.
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
        client.put_object(Bucket=s.s3_bucket, Key=key, Body=body, ContentType="application/json")
    except Exception as exc:
        log.warning("archive.failed", key=key, error=str(exc))
        return None
    return f"s3://{s.s3_bucket}/{key}"
