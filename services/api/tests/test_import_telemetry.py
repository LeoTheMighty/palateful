"""Tests for GET /v1/import-items/{id}/telemetry (irrd-2).

Covers the happy path (multi-stage rollup), the empty case (brand-new
item with no audit rows), auth denial, the preview-truncation contract,
and the legacy-rows filter (pre-irrd-2 `error_logs` rows without a
`stage` tag are invisible to the endpoint).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from conftest import (
    MockExecuteResult,
    MockImportItem,
    MockImportJob,
    MockModel,
    MockRecipeBookUser,
)


class MockErrorLog(MockModel):
    """Mock ErrorLog row, including the new irrd-2 fields."""

    def __init__(self, **kwargs):
        defaults = {
            "error_type": "StageTransition",
            "error_message": "matched:ok",
            "stack_trace": json.dumps({"status": "ok"}),
            "error_code": None,
            "method": None,
            "path": None,
            "status_code": None,
            "user_id": None,
            "service": "audit",
            "request_id": None,
            "import_item_id": None,
            "stage": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _audit(
    *,
    stage: str,
    status: str,
    created_at: datetime,
    import_item_id: str,
) -> MockErrorLog:
    return MockErrorLog(
        error_type="StageTransition",
        error_message=f"{stage}:{status}",
        stack_trace=json.dumps({"status": status}),
        service="audit",
        import_item_id=import_item_id,
        stage=stage,
        created_at=created_at,
    )


def _configure_owner(mock_async_db, mock_user, item, job, *, audit_rows=None):
    """Wire up the ownership + audit-row mocks for a telemetry GET."""
    from utils.models.import_item import ImportItem
    from utils.models.import_job import ImportJob
    from utils.models.recipe_book_user import RecipeBookUser

    mock_async_db.set_find_by(ImportItem, item, id=item.id)
    mock_async_db.set_find_by(ImportJob, job, id=item.import_job_id)
    mock_async_db.set_find_by(
        RecipeBookUser,
        MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=job.recipe_book_id,
            role="owner",
        ),
        user_id=str(mock_user.id),
        recipe_book_id=job.recipe_book_id,
    )

    # The telemetry endpoint makes exactly one db.execute call — a
    # `select(ErrorLog).where(...).order_by(...)` — so a single
    # return_value is enough. Future audit-row queries would land here.
    mock_async_db.db.execute.return_value = MockExecuteResult(
        items=list(audit_rows or [])
    )


class TestTelemetryEndpoint:
    """GET /v1/import-items/{item_id}/telemetry."""

    def test_happy_path_rolls_up_started_and_terminal_rows(
        self, client, mock_async_db, mock_user
    ):
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={"text": "1 cup flour"},
            parsed_recipe={"name": "Cookies", "ingredients": [{"text": "flour"}]},
            status="awaiting_review",
        )

        t0 = datetime(2026, 4, 18, 14, 0, 0, tzinfo=UTC)
        audit = [
            _audit(stage="parsed", status="ok", created_at=t0, import_item_id=item_id),
            _audit(
                stage="extracted",
                status="started",
                created_at=t0 + timedelta(seconds=1),
                import_item_id=item_id,
            ),
            _audit(
                stage="extracted",
                status="ok",
                created_at=t0 + timedelta(seconds=4),
                import_item_id=item_id,
            ),
            _audit(
                stage="matched",
                status="started",
                created_at=t0 + timedelta(seconds=5),
                import_item_id=item_id,
            ),
            _audit(
                stage="matched",
                status="failed",
                created_at=t0 + timedelta(seconds=6),
                import_item_id=item_id,
            ),
        ]
        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=audit)

        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200

        payload = response.json()
        stages = payload["stages"]
        assert [s["stage"] for s in stages] == [
            "parsed",
            "extracted",
            "matched",
            "created",
        ]

        assert stages[0]["status"] == "ok"
        assert stages[0]["raw_output_preview"] == "1 cup flour"
        assert stages[0]["truncated"] is False

        assert stages[1]["status"] == "ok"
        assert stages[1]["duration_ms"] == 3000
        assert "Cookies" in stages[1]["raw_output_preview"]

        assert stages[2]["status"] == "failed"
        assert stages[2]["duration_ms"] == 1000
        assert stages[2]["raw_output_preview"] is None

        assert stages[3]["status"] == "pending"
        assert stages[3]["started_at"] is None
        assert stages[3]["completed_at"] is None
        assert stages[3]["duration_ms"] is None

    def test_empty_telemetry_returns_all_pending(
        self, client, mock_async_db, mock_user
    ):
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={},
            parsed_recipe=None,
            status="pending",
        )

        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=[])
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200

        stages = response.json()["stages"]
        assert len(stages) == 4
        for entry in stages:
            assert entry["status"] == "pending"
            assert entry["started_at"] is None
            assert entry["completed_at"] is None
            assert entry["duration_ms"] is None
            assert entry["raw_output_preview"] is None
            assert entry["truncated"] is False

    def test_preview_truncation_caps_at_4096_and_sets_flag(
        self, client, mock_async_db, mock_user
    ):
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        # 10k chars of raw OCR text.
        oversized = "x" * 10_000
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={"text": oversized},
            parsed_recipe=None,
            status="extracting",
        )

        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=[])
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200

        parsed = response.json()["stages"][0]
        assert parsed["raw_output_preview"] is not None
        assert len(parsed["raw_output_preview"]) == 4096
        assert parsed["truncated"] is True

    def test_under_cap_preview_emits_truncated_false(
        self, client, mock_async_db, mock_user
    ):
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={"text": "short preview"},
            parsed_recipe={"name": "R"},
        )

        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=[])
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200
        stages = response.json()["stages"]
        assert stages[0]["truncated"] is False
        assert stages[1]["truncated"] is False

    def test_404_when_item_missing(self, client, mock_async_db, mock_user):
        item_id = str(uuid.uuid4())
        from utils.models.import_item import ImportItem

        mock_async_db.set_find_by(ImportItem, None, id=item_id)
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 404

    def test_403_when_caller_is_not_owner_or_member(
        self, client, mock_async_db, mock_user
    ):
        item_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        job = MockImportJob(user_id=other_user_id)
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={},
            parsed_recipe=None,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=item.import_job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            None,
            user_id=str(mock_user.id),
            recipe_book_id=job.recipe_book_id,
        )

        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 403

    def test_404_when_job_missing(self, client, mock_async_db, mock_user):
        """Item exists but its parent import_job was dropped — defensive 404
        instead of a 500 from dereferencing `job.recipe_book_id`."""
        item_id = str(uuid.uuid4())
        item = MockImportItem(
            id=item_id,
            import_job_id=str(uuid.uuid4()),
        )
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, None, id=item.import_job_id)

        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 404

    def test_parsed_preview_joins_multi_group_list(
        self, client, mock_async_db, mock_user
    ):
        """Parser-batch imports can land a list of OCR chunks under
        `raw_data.text` (one per page). Preview joins with `\\n---\\n` so
        the Flutter expansion can render page-by-page."""
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={"text": ["page 1", "page 2", "page 3"]},
            parsed_recipe=None,
        )
        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=[])
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200
        parsed = response.json()["stages"][0]
        assert parsed["raw_output_preview"] == "page 1\n---\npage 2\n---\npage 3"

    def test_extracted_preview_none_when_parsed_recipe_unserializable(
        self, client, mock_async_db, mock_user
    ):
        """A `parsed_recipe` JSONB that contains a raw bytes payload (or
        otherwise non-JSON-default-encodable object) must fall through to
        a null preview rather than 500 the endpoint. `default=str` covers
        the common case; the bare-except fallback is the belt-and-braces
        guard for anything that still chokes json.dumps."""
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))

        class _Unserializable:
            def __str__(self):
                raise TypeError("intentional — forces json.dumps failure")

        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={},
            parsed_recipe={"bad": _Unserializable()},
        )
        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=[])
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200
        extracted = response.json()["stages"][1]
        assert extracted["raw_output_preview"] is None

    def test_extract_status_tolerates_bad_stack_trace_payload(
        self, client, mock_async_db, mock_user
    ):
        """Audit rows whose `stack_trace` is null, empty, malformed JSON, or
        JSON-but-not-a-dict must not break the rollup — they just contribute
        no status signal (→ stage stays pending)."""
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id, import_job_id=job.id, raw_data={}, parsed_recipe=None
        )
        t0 = datetime(2026, 4, 18, tzinfo=UTC)
        rows = [
            _audit(
                stage="parsed",
                status="ok",
                created_at=t0,
                import_item_id=item_id,
            ),
            _audit(
                stage="extracted",
                status="ok",
                created_at=t0,
                import_item_id=item_id,
            ),
            _audit(
                stage="matched",
                status="ok",
                created_at=t0,
                import_item_id=item_id,
            ),
        ]
        # Corrupt each row's metadata in a different way.
        rows[0].stack_trace = None  # null payload
        rows[1].stack_trace = "not-json"  # malformed
        rows[2].stack_trace = "[1, 2, 3]"  # JSON but not a dict

        _configure_owner(mock_async_db, mock_user, item, job, audit_rows=rows)
        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200
        # None of the three rows should have contributed a terminal status
        # → all four stages still pending.
        for entry in response.json()["stages"]:
            assert entry["status"] == "pending"

    def test_legacy_rows_without_stage_are_filtered_out(
        self, client, mock_async_db, mock_user
    ):
        """Rows whose `stage` column is still NULL (pre-irrd-2) must not
        poison the telemetry rollup. The model-level `.in_(_STAGE_ORDER)`
        predicate handles this, but we assert the resulting shape so a
        future refactor can't silently drop that filter."""
        item_id = str(uuid.uuid4())
        job = MockImportJob(user_id=str(mock_user.id))
        item = MockImportItem(
            id=item_id,
            import_job_id=job.id,
            raw_data={},
            parsed_recipe=None,
        )
        # Feed a bare row with `stage=None` — the endpoint's accumulator
        # should ignore it (no stage key → no increment).
        legacy_row = _audit(
            stage="parsed",
            status="ok",
            created_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
            import_item_id=item_id,
        )
        legacy_row.stage = None  # Simulate a legacy pre-migration row.
        _configure_owner(
            mock_async_db,
            mock_user,
            item,
            job,
            audit_rows=[legacy_row],
        )

        response = client.get(f"/v1/import-items/{item_id}/telemetry")
        assert response.status_code == 200
        # All four stages stay pending — the legacy row was dropped.
        for entry in response.json()["stages"]:
            assert entry["status"] == "pending"


class TestLogStageTransitionHelper:
    """Unit-level checks on the helper itself."""

    def test_rejects_unknown_stage(self):
        from utils.logging.stage_logging import log_stage_transition

        with patch(
            "utils.logging.stage_logging.logger"
        ) as mock_logger:
            log_stage_transition(
                import_item_id=uuid.uuid4(),
                stage="bogus",
                status="ok",
            )
            assert mock_logger.warning.called

    def test_rejects_unknown_status(self):
        from utils.logging.stage_logging import log_stage_transition

        with patch(
            "utils.logging.stage_logging.logger"
        ) as mock_logger:
            log_stage_transition(
                import_item_id=uuid.uuid4(),
                stage="parsed",
                status="weird",
            )
            assert mock_logger.warning.called

    def test_rejects_non_uuid_item_id(self):
        from utils.logging.stage_logging import log_stage_transition

        with patch(
            "utils.logging.stage_logging.logger"
        ) as mock_logger:
            log_stage_transition(
                import_item_id="not-a-uuid",
                stage="parsed",
                status="ok",
            )
            assert mock_logger.warning.called

    def test_caller_kwargs_cannot_overwrite_reserved_metadata_keys(self):
        """An accidental metadata={'status': 'tampered'} must not override
        the canonical `status` kwarg — the telemetry reader trusts that
        key. Verified by inspecting the ErrorLog instance written to the
        mocked Database."""
        from utils.logging.stage_logging import log_stage_transition

        created_rows = []

        class FakeDB:
            def __init__(self):
                self.db = None

            def create(self, row):
                created_rows.append(row)

            def close(self):
                pass

        with patch(
            "utils.services.database.Database", return_value=FakeDB()
        ):
            log_stage_transition(
                import_item_id=uuid.uuid4(),
                stage="parsed",
                status="ok",
                metadata={"status": "tampered", "extra": "kept"},
            )

        assert len(created_rows) == 1
        row = created_rows[0]
        decoded = json.loads(row.stack_trace)
        assert decoded["status"] == "ok"
        assert decoded["extra"] == "kept"
