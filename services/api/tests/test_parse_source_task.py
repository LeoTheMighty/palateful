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


class TestParseS3KeyedVideoFile:
    """sbf-4: video_file → ffmpeg → Whisper → text rewrite."""

    @patch("utils.services.recipe_extractors.audio_extractor.transcribe_audio")
    @patch("utils.services.recipe_extractors.video_file_extractor.extract_audio_to_file")
    def test_happy_path_rewrites_item_as_text(
        self, mock_extract, mock_transcribe, mock_db, mock_user,
    ):
        from utils.services.recipe_extractors.video_file_extractor import (
            ExtractedAudio,
        )

        mock_extract.return_value = ExtractedAudio(
            path="/tmp/x.mp3", size_bytes=1234, stderr_tail="",
        )
        mock_transcribe.return_value = ("a pinch of salt", 9)

        job = MockImportJob(
            id="job-vf",
            source_type="video_file",
            user_id=str(mock_user.id),
            total_items=1,
            total_ai_cost_cents=0,
        )
        item = MockImportItem(
            import_job_id="job-vf",
            source_type="video_file",
            s3_key=f"imports/{mock_user.id}/clip.mp4",
            raw_data={
                "s3_key": f"imports/{mock_user.id}/clip.mp4",
                "original_filename": "clip.mp4",
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
            return_value=SimpleNamespace(read_object=lambda *_, **__: b"video bytes"),
        ):
            count = task._parse_s3_keyed_files(job)

        assert count == 1
        assert item.source_type == "text"
        assert item.raw_data["text"] == "a pinch of salt"
        assert item.raw_data["is_video_file_import"] is True
        assert item.ai_cost_cents == 9
        assert job.total_ai_cost_cents == 9
        mock_extract.assert_called_once()
        mock_transcribe.assert_called_once()

    @patch("utils.services.recipe_extractors.audio_extractor.transcribe_audio")
    @patch("utils.services.recipe_extractors.video_file_extractor.extract_audio_to_file")
    def test_ffmpeg_failure_marks_item_failed(
        self, mock_extract, mock_transcribe, mock_db, mock_user,
    ):
        from utils.services.recipe_extractors.video_file_extractor import (
            VideoDecodeError,
        )

        mock_extract.side_effect = VideoDecodeError(
            "Invalid data found when processing input"
        )

        job = MockImportJob(
            id="job-vf-bad",
            source_type="video_file",
            user_id=str(mock_user.id),
            total_items=1,
        )
        item = MockImportItem(
            import_job_id="job-vf-bad",
            source_type="video_file",
            s3_key=f"imports/{mock_user.id}/broken.mp4",
            raw_data={
                "s3_key": f"imports/{mock_user.id}/broken.mp4",
            },
            status="pending",
        )
        query = MagicMock()
        query.filter.return_value.all.return_value = [item]
        mock_db.db.query.return_value = query

        task = _build_task(mock_db)
        with patch.object(
            task, "_aws_service",
            return_value=SimpleNamespace(read_object=lambda *_, **__: b"not a video"),
        ):
            count = task._parse_s3_keyed_files(job)

        assert count == 1
        assert item.status == "failed"
        assert item.error_code == "video_decode_failed"
        assert "ffmpeg failed" in item.error_message
        assert job.status == "failed"
        # Transcription must NOT run when ffmpeg fails — Whisper spend
        # is the whole reason ffmpeg runs first.
        mock_transcribe.assert_not_called()


class TestParseImageIsNoOp:
    """share-img-1: parse stage is a no-op for `image`.

    Vision extraction is a single round-trip and runs in
    extract_recipe_task directly off the s3_key. The parse stage just
    leaves the item alone (status=pending, raw_data unchanged) and
    fans out to extract.
    """

    def test_image_does_not_call_s3_keyed_parser(self, mock_db, mock_user):
        from utils.tasks.import_tasks.parse_source_task import ParseSourceTask

        job = MockImportJob(
            id="job-img",
            source_type="image",
            user_id=str(mock_user.id),
            total_items=1,
        )
        item = MockImportItem(
            import_job_id="job-img",
            source_type="image",
            s3_key=f"imports/{mock_user.id}/photo.jpg",
            raw_data={"s3_key": f"imports/{mock_user.id}/photo.jpg"},
            status="pending",
        )
        # _dispatch_extraction_tasks reads pending items via this query.
        query = MagicMock()
        query.filter.return_value.all.return_value = [item]
        mock_db.db.query.return_value = query
        mock_db.find_by = lambda model, **_kw: job

        task = ParseSourceTask()
        task.database = mock_db

        # If the parse stage tried to fetch S3, _aws_service would be
        # called and the lambda below would record it. Assert it isn't.
        called_aws = []
        with patch.object(
            task, "_aws_service",
            side_effect=lambda: (called_aws.append(1), MagicMock())[1],
        ), patch(
            "utils.logging.log_stage_transition"
        ), patch(
            "utils.tasks.import_tasks.extract_recipe_task.extract_task"
        ) as mock_extract:
            task.execute(import_job_id="job-img")

        assert called_aws == []
        # Item was not touched: still source_type='image', still pending.
        assert item.source_type == "image"
        assert item.status == "pending"
        # Extract task fanned out.
        mock_extract.delay.assert_called_once()


class TestVideoFileExtractor:
    """sbf-4: ffmpeg subprocess wrapper unit tests."""

    @patch("utils.services.recipe_extractors.video_file_extractor.subprocess.Popen")
    @patch("utils.services.recipe_extractors.video_file_extractor.os.path.getsize")
    def test_happy_path_returns_extracted_audio(self, mock_size, mock_popen, tmp_path):
        from utils.services.recipe_extractors.video_file_extractor import (
            extract_audio_to_file,
        )

        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        proc.pid = 12345
        mock_popen.return_value = proc
        mock_size.return_value = 4096

        result = extract_audio_to_file(
            str(tmp_path / "in.mp4"), str(tmp_path / "out.mp3"),
        )
        assert result.size_bytes == 4096
        assert result.path.endswith("out.mp3")

        # Process-group signalling: preexec_fn must set our own group so
        # Celery's soft-time-limit can reap the whole tree.
        _args, kwargs = mock_popen.call_args
        assert "preexec_fn" in kwargs
        assert kwargs["preexec_fn"] is __import__("os").setsid

        # Duration cap is hard-coded; verify it shows up in the argv.
        cmd = mock_popen.call_args[0][0]
        assert "-t" in cmd
        assert cmd[cmd.index("-t") + 1] == "1200"

    @patch("utils.services.recipe_extractors.video_file_extractor.subprocess.Popen")
    def test_non_zero_exit_raises_video_decode_error(self, mock_popen, tmp_path):
        from utils.services.recipe_extractors.video_file_extractor import (
            VideoDecodeError,
            extract_audio_to_file,
        )

        proc = MagicMock()
        proc.communicate.return_value = (b"", b"Invalid data found")
        proc.returncode = 1
        proc.pid = 12345
        mock_popen.return_value = proc

        try:
            extract_audio_to_file(
                str(tmp_path / "in.mp4"), str(tmp_path / "out.mp3"),
            )
        except VideoDecodeError as exc:
            assert "Invalid data found" in exc.stderr_tail
        else:  # pragma: no cover
            raise AssertionError("expected VideoDecodeError")
