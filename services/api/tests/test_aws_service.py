"""Tests for AWSService helpers (sbf-2 + later).

Verifies that `presign_put_url` produces a real boto3-signed URL whose
host, path, signed-headers list, and query parameters match what the
client (iOS URLSession, Android HttpClient, Flutter http) needs to
upload a 50 MB payload without a SignatureDoesNotMatch.

We don't actually round-trip bytes through S3 — that requires real
AWS creds or moto, neither of which is available in CI. Instead we
parse the signed URL and assert the contract surface that callers
depend on: bucket / key / SignedHeaders / SHA256 hash header / Tagging
query parameter.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

# Ensure dummy AWS creds are available so boto3 will sign offline.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
os.environ.setdefault(
    "AWS_SECRET_ACCESS_KEY",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from utils.services.aws import AWSService  # noqa: E402


class TestPresignPutUrl:
    """sbf-2: AWSService.presign_put_url contract."""

    def _aws(self) -> AWSService:
        return AWSService(
            region="us-east-1",
            parser_inputs_bucket="palateful-parser-inputs-test",
            parser_outputs_bucket="palateful-parser-outputs-test",
        )

    def test_targets_explicit_bucket_not_parser_inputs(self):
        url, _ = self._aws().presign_put_url(
            s3_key="imports/abc/def.pdf",
            bucket="palateful-imports-test",
            content_type="application/pdf",
            content_length=1024,
        )
        host = urlparse(url).netloc
        assert host.startswith("palateful-imports-test.")
        assert "parser-inputs" not in host

    def test_signs_content_type_and_content_length(self):
        url, required = self._aws().presign_put_url(
            s3_key="imports/abc/def.mp4",
            bucket="palateful-imports-test",
            content_type="video/mp4",
            content_length=50 * 1024 * 1024,
        )
        # The required-headers map mirrors what was signed.
        assert required["Content-Type"] == "video/mp4"
        assert required["Content-Length"] == str(50 * 1024 * 1024)
        # Signed header set in the URL must include both — otherwise
        # client uploads will fail with SignatureDoesNotMatch.
        signed_headers = parse_qs(urlparse(url).query).get(
            "X-Amz-SignedHeaders", [""]
        )[0]
        assert "content-type" in signed_headers
        assert "content-length" in signed_headers
        assert "host" in signed_headers

    def test_signs_tagging_when_provided(self):
        url, required = self._aws().presign_put_url(
            s3_key="imports/abc/def.pdf",
            bucket="palateful-imports-test",
            content_type="application/pdf",
            content_length=1024,
            tagging="unclaimed=true",
        )
        assert required["x-amz-tagging"] == "unclaimed=true"
        signed_headers = parse_qs(urlparse(url).query).get(
            "X-Amz-SignedHeaders", [""]
        )[0]
        assert "x-amz-tagging" in signed_headers

    def test_omits_tagging_header_when_not_provided(self):
        _, required = self._aws().presign_put_url(
            s3_key="imports/abc/def.pdf",
            bucket="palateful-imports-test",
            content_type="application/pdf",
            content_length=1024,
        )
        assert "x-amz-tagging" not in required

    def test_url_carries_expires_in(self):
        url, _ = self._aws().presign_put_url(
            s3_key="imports/abc/def.pdf",
            bucket="palateful-imports-test",
            content_type="application/pdf",
            content_length=1024,
            expires_in=1800,
        )
        expires = parse_qs(urlparse(url).query).get(
            "X-Amz-Expires", [""]
        )[0]
        assert expires == "1800"

    def test_url_includes_key_path(self):
        url, _ = self._aws().presign_put_url(
            s3_key="imports/user-uuid/object-uuid.mov",
            bucket="palateful-imports-test",
            content_type="video/quicktime",
            content_length=50 * 1024 * 1024,
        )
        path = urlparse(url).path
        assert path.endswith("/imports/user-uuid/object-uuid.mov")

    def test_50mb_round_trip_readiness(self):
        """Surrogate for the URLSession 50 MB round-trip dev spike: prove
        the signed URL's required-headers set is exactly the set the
        client must send. iOS URLSession.uploadTask sets Content-Length
        + Content-Type automatically; the only "extra" header to wire
        through is x-amz-tagging."""
        url, required = self._aws().presign_put_url(
            s3_key="imports/u/o.mp4",
            bucket="palateful-imports-test",
            content_type="video/mp4",
            content_length=50 * 1024 * 1024,
            tagging="unclaimed=true",
        )
        # Client-side: every required header must be sent verbatim.
        # Signed header set in the URL must be a superset of the
        # required-headers map (boto3 also adds 'host', which is
        # implicit on every HTTP request).
        signed_headers = set(
            parse_qs(urlparse(url).query)
            .get("X-Amz-SignedHeaders", [""])[0]
            .split(";")
        )
        for header_name in required:
            assert header_name.lower() in signed_headers, header_name


class TestAsyncVariants:
    """aam-9: async wrappers forward to the sync boto3 methods via
    `run_in_threadpool` so async endpoints (post aam-18 / aam-29) can
    `await` them without blocking the event loop. Lands dark — no hot-
    path caller yet, so these tests are the only exercise of that code.
    """

    def _aws(self) -> AWSService:
        return AWSService(
            region="us-east-1",
            parser_inputs_bucket="in-bucket",
            parser_outputs_bucket="out-bucket",
            batch_job_queue="queue-x",
            batch_job_definition="def-x",
        )

    async def test_generate_presigned_upload_url_async(self):
        aws = self._aws()
        aws.generate_presigned_upload_url = MagicMock(return_value="URL")  # type: ignore[method-assign]
        out = await aws.generate_presigned_upload_url_async(
            s3_key="k", content_type="image/png", expires_in=10,
        )
        assert out == "URL"
        aws.generate_presigned_upload_url.assert_called_once_with(
            "k", "image/png", 10,
        )

    async def test_presign_put_url_async(self):
        aws = self._aws()
        aws.presign_put_url = MagicMock(return_value=("URL", {"h": "v"}))  # type: ignore[method-assign]
        url, headers = await aws.presign_put_url_async(
            s3_key="k",
            bucket="b",
            content_type="video/mp4",
            content_length=100,
            tagging="unclaimed=true",
            expires_in=60,
        )
        assert (url, headers) == ("URL", {"h": "v"})
        aws.presign_put_url.assert_called_once_with(
            "k", "b", "video/mp4", 100, "unclaimed=true", 60,
        )

    async def test_generate_presigned_download_url_async(self):
        aws = self._aws()
        aws.generate_presigned_download_url = MagicMock(return_value="URL")  # type: ignore[method-assign]
        out = await aws.generate_presigned_download_url_async(
            s3_key="k", bucket="b", expires_in=30,
        )
        assert out == "URL"
        aws.generate_presigned_download_url.assert_called_once_with(
            "k", "b", 30,
        )

    async def test_get_s3_object_async(self):
        aws = self._aws()
        aws.get_s3_object = MagicMock(return_value={"a": 1})  # type: ignore[method-assign]
        out = await aws.get_s3_object_async(s3_key="k", bucket="b")
        assert out == {"a": 1}
        aws.get_s3_object.assert_called_once_with("k", "b")

    async def test_read_object_async(self):
        aws = self._aws()
        aws.read_object = MagicMock(return_value=b"bytes")  # type: ignore[method-assign]
        out = await aws.read_object_async(s3_key="k", bucket="b")
        assert out == b"bytes"
        aws.read_object.assert_called_once_with("k", "b")

    async def test_head_object_async(self):
        aws = self._aws()
        aws.head_object = MagicMock(return_value={"ContentLength": 10})  # type: ignore[method-assign]
        out = await aws.head_object_async(s3_key="k", bucket="b")
        assert out == {"ContentLength": 10}
        aws.head_object.assert_called_once_with("k", "b")

    async def test_copy_object_async(self):
        aws = self._aws()
        aws.copy_object = MagicMock(return_value=None)  # type: ignore[method-assign]
        out = await aws.copy_object_async(
            source_key="src",
            dest_key="dst",
            source_bucket="sb",
            dest_bucket="db",
        )
        assert out is None
        aws.copy_object.assert_called_once_with("src", "dst", "sb", "db")

    async def test_submit_batch_job_async(self):
        aws = self._aws()
        aws.submit_batch_job = MagicMock(return_value="job-1")  # type: ignore[method-assign]
        out = await aws.submit_batch_job_async(
            job_name="name", input_s3_key="in", output_s3_key="out",
        )
        assert out == "job-1"
        aws.submit_batch_job.assert_called_once_with("name", "in", "out")

    async def test_submit_batch_manifest_job_async(self):
        aws = self._aws()
        aws.submit_batch_manifest_job = MagicMock(return_value="job-2")  # type: ignore[method-assign]
        items = [{"input_s3_key": "a", "output_s3_key": "b"}]
        out = await aws.submit_batch_manifest_job_async(
            job_name="name",
            items=items,
            manifest_s3_key="mkey",
            extra_environment={"K": "V"},
        )
        assert out == "job-2"
        aws.submit_batch_manifest_job.assert_called_once_with(
            "name", items, "mkey", {"K": "V"},
        )

    async def test_describe_batch_job_async(self):
        aws = self._aws()
        aws.describe_batch_job = MagicMock(return_value={"status": "RUNNING"})  # type: ignore[method-assign]
        out = await aws.describe_batch_job_async(job_id="jid")
        assert out == {"status": "RUNNING"}
        aws.describe_batch_job.assert_called_once_with("jid")

    async def test_get_batch_job_status_async(self):
        aws = self._aws()
        aws.get_batch_job_status = MagicMock(return_value="SUCCEEDED")  # type: ignore[method-assign]
        out = await aws.get_batch_job_status_async(job_id="jid")
        assert out == "SUCCEEDED"
        aws.get_batch_job_status.assert_called_once_with("jid")

    async def test_async_variant_propagates_sync_exception(self):
        """run_in_threadpool must surface a raised exception on the
        awaiting side — callers rely on try/except working as it would
        against the sync API."""
        aws = self._aws()

        class Boom(RuntimeError):
            pass

        def _raise(*_a, **_k):
            raise Boom("kaboom")

        aws.get_s3_object = _raise  # type: ignore[method-assign]
        import pytest
        with pytest.raises(Boom, match="kaboom"):
            await aws.get_s3_object_async(s3_key="k", bucket="b")
