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
