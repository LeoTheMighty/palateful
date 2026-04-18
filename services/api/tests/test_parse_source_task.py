"""Tests for ParseSourceTask.s3_key branch (sbf-3).

The celery task itself is exercised in integration via /import tests,
but the s3_key-keyed fetch + parse branch has enough logic (three
source types, multi-recipe fanout, transcript cost accounting) to
warrant direct unit tests against mocks.
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from conftest import MockImportItem, MockImportJob


class _MockPdfType(Enum):
    text = "text"
    scanned = "scanned"


def _build_task(mock_db):
    """Instantiate a ParseSourceTask wired to the mock db."""
    from utils.tasks.import_tasks.parse_source_task import ParseSourceTask

    task = ParseSourceTask()
    task.database = mock_db
    return task


class TestParseS3KeyedAudio:
    """sbf-3: audio s3_key path in ParseSourceTask."""

    @patch("utils.services.recipe_extractors.audio_extractor.transcribe_audio")
    def test_rewrites_item_as_text_with_transcript(
        self, mock_transcribe, mock_db, mock_user,
    ):
        mock_transcribe.return_value = ("two cups of flour", 7)
        job = MockImportJob(
            id="job-id",
            source_type="audio",
            user_id=str(mock_user.id),
            total_items=1,
            total_ai_cost_cents=0,
        )
        item = MockImportItem(
            import_job_id="job-id",
            source_type="audio",
            s3_key=f"imports/{mock_user.id}/obj.m4a",
            raw_data={
                "s3_key": f"imports/{mock_user.id}/obj.m4a",
                "original_filename": "voice.m4a",
            },
            status="pending",
            ai_cost_cents=0,
        )
        query = MagicMock()
        query.filter.return_value.all.return_value = [item]
        mock_db.db.query.return_value = query

        task = _build_task(mock_db)
        with patch.object(
            task, "_aws_service",
            return_value=SimpleNamespace(read_object=lambda *_, **__: b"raw audio"),
        ):
            count = task._parse_s3_keyed_files(job)

        assert count == 1
        assert item.source_type == "text"
        assert item.raw_data["text"] == "two cups of flour"
        assert item.raw_data["is_audio_import"] is True
        assert item.raw_data["transcription_cost_cents"] == 7
        assert item.ai_cost_cents == 7
        assert job.total_ai_cost_cents == 7


class TestParseS3KeyedPdf:
    """sbf-3: multi-recipe PDF fanout from S3 bytes."""

    @patch("utils.services.recipe_extractors.pdf_extractor.detect_recipe_boundaries")
    @patch("utils.services.recipe_extractors.pdf_extractor.extract_text_from_pdf")
    @patch("utils.services.recipe_extractors.pdf_extractor.classify_pdf")
    def test_fans_out_one_item_per_recipe(
        self, mock_classify, mock_extract, mock_boundaries,
        mock_db, mock_user,
    ):
        mock_classify.return_value = (_MockPdfType.text, 4)
        mock_extract.return_value = "Recipe 1\n...\nRecipe 2\n...\nRecipe 3"
        mock_boundaries.return_value = [
            {"text": "Recipe 1 text", "title": "Recipe 1"},
            {"text": "Recipe 2 text", "title": "Recipe 2"},
            {"text": "Recipe 3 text", "title": "Recipe 3"},
        ]

        job = MockImportJob(
            id="job-id",
            source_type="pdf",
            user_id=str(mock_user.id),
            total_items=1,
        )
        first_item = MockImportItem(
            import_job_id="job-id",
            source_type="pdf",
            s3_key=f"imports/{mock_user.id}/deck.pdf",
            raw_data={
                "s3_key": f"imports/{mock_user.id}/deck.pdf",
                "original_filename": "cookbook.pdf",
            },
            status="pending",
        )
        query = MagicMock()
        query.filter.return_value.all.return_value = [first_item]
        mock_db.db.query.return_value = query
        # Track sibling creation by wrapping `create`.
        created: list = []
        real_create = mock_db.create

        def _tracking_create(model):
            created.append(model)
            return real_create(model)

        mock_db.create = _tracking_create

        task = _build_task(mock_db)
        with patch.object(
            task, "_aws_service",
            return_value=SimpleNamespace(read_object=lambda *_, **__: b"%PDF-1.4..."),
        ):
            count = task._parse_s3_keyed_files(job)

        assert count == 3
        # Original item was rewritten to the first recipe.
        assert first_item.source_type == "text"
        assert first_item.raw_data["text"] == "Recipe 1 text"
        assert first_item.raw_data["pdf_recipe_title"] == "Recipe 1"
        # Two siblings created for recipes 2 and 3.
        assert len(created) == 2
        assert created[0].raw_data["text"] == "Recipe 2 text"
        assert created[1].raw_data["text"] == "Recipe 3 text"

    @patch("utils.services.recipe_extractors.pdf_extractor.detect_recipe_boundaries")
    @patch("utils.services.recipe_extractors.pdf_extractor.extract_text_from_pdf")
    @patch("utils.services.recipe_extractors.pdf_extractor.classify_pdf")
    def test_scanned_pdf_is_one_text_item(
        self, mock_classify, mock_extract, mock_boundaries,
        mock_db, mock_user,
    ):
        mock_classify.return_value = (_MockPdfType.scanned, 2)
        mock_extract.return_value = "OCRed scan body"

        job = MockImportJob(id="job-id", source_type="pdf", total_items=1)
        item = MockImportItem(
            import_job_id="job-id",
            source_type="pdf",
            s3_key=f"imports/{mock_user.id}/scan.pdf",
            raw_data={"s3_key": f"imports/{mock_user.id}/scan.pdf"},
            status="pending",
        )
        query = MagicMock()
        query.filter.return_value.all.return_value = [item]
        mock_db.db.query.return_value = query

        task = _build_task(mock_db)
        with patch.object(
            task, "_aws_service",
            return_value=SimpleNamespace(read_object=lambda *_, **__: b"..."),
        ):
            count = task._parse_s3_keyed_files(job)

        # detect_recipe_boundaries is never called for scanned PDFs.
        mock_boundaries.assert_not_called()
        assert count == 1
        assert item.source_type == "text"
        assert item.raw_data["text"] == "OCRed scan body"
        assert item.raw_data["is_scanned_pdf"] is True
