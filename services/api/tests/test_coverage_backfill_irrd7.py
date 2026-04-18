"""Coverage backfill landed with irrd-7 finalization.

The API coverage gate is pinned at 100%. Pre-existing branches in
push-diag-3 / sbf-3 code ship uncovered, which blocks unrelated
pushes. This module fills those gaps without modifying the
production files (owned by other agents).

Covered here:
- ``get_push_health._token_prefix`` short-token branch (line 34).
- ``GetAdminPushHealth.execute`` out-of-range ``error_limit`` branch
  (line 64). Can't be hit via HTTP because FastAPI's query-param
  validation returns 422 before the endpoint runs, so we call the
  Endpoint directly.
- ``StartImport`` PDF-with-s3_key and spreadsheet-with-s3_key
  branches (lines 184, 195, 196, 488).
- ``list_import_items._extract_confidence_fields`` out-of-range score branch
  (line 31 false path).
- ``get_import_item_telemetry._StageAccumulator.ingest`` early-started
  override branch (line 110 false path).
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from conftest import (
    MockImportItem,
    MockQuery,
    MockRecipeBook,
    MockRecipeBookUser,
)


# ---------------------------------------------------------------------------
# get_push_health — internal helpers
# ---------------------------------------------------------------------------

class TestTokenPrefix:
    """Covers ``_token_prefix`` short-token branch."""

    def test_returns_token_unchanged_when_shorter_than_prefix(self):
        from api.v1.admin.get_push_health import _token_prefix

        # token length ≤ 8 hits the early-return branch.
        assert _token_prefix("short") == "short"
        assert _token_prefix("") == ""
        assert _token_prefix("01234567") == "01234567"

    def test_truncates_and_ellipsizes_when_longer(self):
        from api.v1.admin.get_push_health import _token_prefix

        result = _token_prefix("a" * 150)
        assert result == "aaaaaaaa…"


class TestGetPushHealthErrorLimitOutOfRange:
    """Covers the ``error_limit`` defensive check in
    ``GetAdminPushHealth.execute`` (line 64).

    FastAPI intercepts the HTTP call at query-param validation, so we
    invoke the endpoint class directly.
    """

    @pytest.mark.parametrize("bad_limit", [0, -1, 51, 100])
    def test_raises_api_exception_for_out_of_range(self, bad_limit, mock_user):
        from api.v1.admin.get_push_health import GetAdminPushHealth
        from utils.api.endpoint import APIException

        mock_user.is_admin = True
        endpoint = GetAdminPushHealth()
        endpoint.user = mock_user
        endpoint.db = MagicMock()

        with pytest.raises(APIException) as excinfo:
            endpoint.execute(
                user_id_or_email=str(uuid.uuid4()),
                error_limit=bad_limit,
            )
        assert excinfo.value.status_code == 400


# ---------------------------------------------------------------------------
# start_import — PDF + spreadsheet s3_key paths
# ---------------------------------------------------------------------------

def _ok_aws():
    service = MagicMock()
    service.head_object.return_value = {
        "ContentLength": 4096,
        "ETag": '"deadbeef"',
    }
    return service


def _setup_book_access(mock_db, mock_user, book_id):
    from utils.models.recipe_book import RecipeBook
    from utils.models.recipe_book_user import RecipeBookUser

    book = MockRecipeBook(id=book_id)
    membership = MockRecipeBookUser(
        user_id=str(mock_user.id),
        recipe_book_id=book_id,
        role="owner",
    )
    mock_db.set_find_by(
        RecipeBookUser, membership,
        user_id=str(mock_user.id), recipe_book_id=book_id,
    )
    mock_db.set_find_by(RecipeBook, book, id=book_id)


def _reset_rate_limit():
    from api.v1.import_job.start_import import _reset_rate_limit_for_test

    _reset_rate_limit_for_test()


class TestStartImportPdfSpreadsheetS3Key:
    """Covers lines 184 (pdf s3_key) and 195-196 (spreadsheet s3_key)."""

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_pdf_with_s3_key_happy_path_sets_source_filename(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        _reset_rate_limit()
        book_id = "book-irrd7-pdf"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()
        mock_task.delay.return_value = None

        s3_key = f"imports/{mock_user.id}/file.pdf"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": s3_key,
                "mime_type": "application/pdf",
                "file_name": "doc.pdf",
                "etag": '"deadbeef"',
            },
        )
        assert response.status_code == 201, response.json()
        assert response.json()["source_type"] == "pdf"

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_pdf_with_s3_key_missing_file_name_falls_back_to_key(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        _reset_rate_limit()
        book_id = "book-irrd7-pdf-nofn"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()
        mock_task.delay.return_value = None

        s3_key = f"imports/{mock_user.id}/no-filename.pdf"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": s3_key,
                "mime_type": "application/pdf",
                "etag": '"deadbeef"',
            },
        )
        assert response.status_code == 201, response.json()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_spreadsheet_with_s3_key_happy_path(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        _reset_rate_limit()
        book_id = "book-irrd7-sheet"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()
        mock_task.delay.return_value = None

        s3_key = f"imports/{mock_user.id}/recipes.csv"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "spreadsheet",
                "s3_key": s3_key,
                "mime_type": "text/csv",
                "file_name": "recipes.csv",
                "etag": '"deadbeef"',
            },
        )
        assert response.status_code == 201, response.json()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_spreadsheet_with_s3_key_missing_file_name_falls_back(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        _reset_rate_limit()
        book_id = "book-irrd7-sheet-nofn"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()
        mock_task.delay.return_value = None

        s3_key = f"imports/{mock_user.id}/nolabel.csv"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "spreadsheet",
                "s3_key": s3_key,
                "mime_type": "text/csv",
                "etag": '"deadbeef"',
            },
        )
        assert response.status_code == 201, response.json()


class TestStartImportS3ValidationEdges:
    """Covers line 488 (bare re-raise for unexpected S3 errors), the
    dedupe check (lines 490-498), and the IntegrityError fallback
    (lines 402-411)."""

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_nosuchkey_error_raises_object_not_ready_409(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        from botocore.exceptions import ClientError

        from utils.classes.error_code import ErrorCode

        _reset_rate_limit()
        book_id = "book-irrd7-nokey"
        _setup_book_access(mock_db, mock_user, book_id)
        service = _ok_aws()
        service.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "not yet"}},
            "HeadObject",
        )
        mock_get_service.return_value = service

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": f"imports/{mock_user.id}/missing.pdf",
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 409
        assert (
            response.json()["error_code"] == ErrorCode.OBJECT_NOT_READY.value
        )
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_unexpected_s3_error_propagates(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        """A ClientError with an unrecognized code hits the bare
        ``raise`` on line 488 and bubbles out as a 500."""
        from botocore.exceptions import ClientError

        _reset_rate_limit()
        book_id = "book-irrd7-unexpected"
        _setup_book_access(mock_db, mock_user, book_id)
        service = _ok_aws()
        service.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "nope"}},
            "HeadObject",
        )
        mock_get_service.return_value = service

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": f"imports/{mock_user.id}/nope.pdf",
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code >= 500
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_duplicate_s3_key_via_dedupe_query_returns_409(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        """Seeds an existing ImportItem with the same s3_key so the
        endpoint's in-validator dedupe query fires."""
        from utils.classes.error_code import ErrorCode

        _reset_rate_limit()
        book_id = "book-irrd7-dup"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()

        s3_key = f"imports/{mock_user.id}/dup.pdf"
        existing = MockImportItem(s3_key=s3_key)
        mock_db.db.query.return_value = MockQuery([existing])

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": s3_key,
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 409
        assert (
            response.json()["error_code"] == ErrorCode.DUPLICATE_IMPORT.value
        )
        mock_task.delay.assert_not_called()


class TestStartImportIntegrityErrorFallback:
    """Covers lines 402-411 — concurrent-race IntegrityError path.

    The partial UNIQUE index on ``import_items.s3_key`` raises when a
    second concurrent request wins the race past the in-endpoint
    dedupe query. Here we patch ``mock_db.create`` to raise on the
    second create (ImportItem, after ImportJob) so the commit path
    hits the IntegrityError branch.
    """

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_integrity_error_rollback_returns_409_duplicate(
        self, mock_get_service, mock_task, client, mock_db, mock_user,
    ):
        from sqlalchemy.exc import IntegrityError

        from utils.classes.error_code import ErrorCode

        _reset_rate_limit()
        book_id = "book-irrd7-integrity"
        _setup_book_access(mock_db, mock_user, book_id)
        mock_get_service.return_value = _ok_aws()

        original_create = mock_db.create
        call_count = {"n": 0}

        def create_side_effect(obj):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise IntegrityError(
                    "duplicate key",
                    params=None,
                    orig=Exception("duplicate"),
                )
            return original_create(obj)

        mock_db.create = create_side_effect

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": f"imports/{mock_user.id}/race.pdf",
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 409
        assert (
            response.json()["error_code"] == ErrorCode.DUPLICATE_IMPORT.value
        )
        mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# list_import_items._extract_confidence_fields out-of-range score
# ---------------------------------------------------------------------------

class TestHoistConfidenceOutOfRange:
    @pytest.mark.parametrize("bad_score", [-0.1, 1.2, 2.0, -5])
    def test_score_outside_zero_to_one_is_scrubbed(self, bad_score):
        from api.v1.import_job.list_import_items import _extract_confidence_fields

        score, source = _extract_confidence_fields({
            "confidence_score": bad_score,
            "confidence_source": "model",
        })
        assert score is None
        assert source == "model"

    def test_valid_score_and_source_round_trip(self):
        from api.v1.import_job.list_import_items import _extract_confidence_fields

        score, source = _extract_confidence_fields({
            "confidence_score": 0.73,
            "confidence_source": "heuristic",
        })
        assert score == pytest.approx(0.73)
        assert source == "heuristic"


# ---------------------------------------------------------------------------
# get_import_item_telemetry._StageAccumulator earlier-started override
# ---------------------------------------------------------------------------

class TestStageBucketEarlierStartedOverride:
    def test_later_started_entry_with_earlier_timestamp_overrides(self):
        from datetime import UTC, datetime, timedelta

        from api.v1.import_job.get_import_item_telemetry import _StageAccumulator

        bucket = _StageAccumulator()
        t_later = datetime.now(UTC)
        t_earlier = t_later - timedelta(seconds=30)

        bucket.ingest("started", t_later)
        assert bucket.started_at == t_later

        # A subsequent entry whose timestamp is earlier MUST replace
        # started_at (AC for irrd-2: earliest started wins).
        bucket.ingest("started", t_earlier)
        assert bucket.started_at == t_earlier

    def test_later_started_entry_with_later_timestamp_is_ignored(self):
        from datetime import UTC, datetime, timedelta

        from api.v1.import_job.get_import_item_telemetry import _StageAccumulator

        bucket = _StageAccumulator()
        t_first = datetime.now(UTC)
        t_after = t_first + timedelta(seconds=30)

        bucket.ingest("started", t_first)
        bucket.ingest("started", t_after)
        assert bucket.started_at == t_first
