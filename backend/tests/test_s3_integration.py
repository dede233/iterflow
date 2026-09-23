"""Real S3-compatible smoke; CI supplies an ephemeral MinIO endpoint."""

import os
from urllib.request import urlopen
from uuid import uuid4

import pytest

from app.services.storage.s3 import S3Storage


def test_real_s3_round_trip():
    endpoint = os.getenv("ITERFLOW_TEST_S3_ENDPOINT")
    if not endpoint:
        pytest.skip("ITERFLOW_TEST_S3_ENDPOINT is required for real S3 integration")
    bucket = f"iterflow-ci-{uuid4().hex[:24]}"
    storage = S3Storage(
        bucket=bucket,
        endpoint=endpoint,
        access_key=os.environ["ITERFLOW_TEST_S3_ACCESS_KEY"],
        secret_key=os.environ["ITERFLOW_TEST_S3_SECRET_KEY"],
    )
    key = f"smoke/{uuid4().hex}.txt"
    payload = b"iterflow-s3-smoke"
    try:
        storage.ensure_bucket()
        storage.check_ready()  # Read-only: head_bucket, never create_bucket.
        storage.upload(key, payload, content_type="text/plain")
        assert storage.exists(key)
        assert storage.get_metadata(key).size == len(payload)
        assert storage.get_metadata(key).content_type == "text/plain"
        with storage.open(key) as item:
            assert item.read() == payload
        signed_url = storage.generate_download_url(key, expires_seconds=60)
        assert signed_url is not None
        with urlopen(signed_url, timeout=10) as item:
            assert item.read() == payload
        storage.delete(key)
        assert not storage.exists(key)
    finally:
        storage.delete(key)
        storage._client.delete_bucket(Bucket=bucket)
