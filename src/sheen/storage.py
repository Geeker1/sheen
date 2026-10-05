"""Keep a copy of each download in S3 (LocalStack when running locally)."""

import boto3
import structlog
from botocore.exceptions import ClientError

from sheen.config import get_settings

log = structlog.get_logger()


def archive(key: str, body: bytes) -> str | None:
    """Save a download to S3 and return its address, or None if that fails.

    The download is also saved in the database, so if S3 is down this only
    logs a warning.
    """
    s = get_settings()
    client = boto3.client("s3", endpoint_url=s.s3_endpoint_url)
    try:
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
