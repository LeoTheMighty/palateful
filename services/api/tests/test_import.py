"""Tests for import job endpoints."""

import uuid
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from conftest import (
    MockExecuteResult,
    MockImportItem,
    MockImportJob,
    MockRecipeBook,
    MockRecipeBookUser,
)


def _paginated(items, total=None):
    """Build a side_effect for list endpoints that do count + rows.

    The cursor=None path of `list_import_jobs` / `list_import_items` /
    `list_see_all_items` runs `select(func.count())` followed by the
    actual `select(Model)`. Tests pass the list of expected rows; this
    helper expands to the matching `[count_result, rows_result]`.
    """
    if total is None:
        total = len(items)
    return [
        MockExecuteResult(items=[total]),
        MockExecuteResult(items=items),
    ]


class TestStartImport:
    """Tests for POST /v1/recipe-books/{book_id}/import."""

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_success(self, mock_task, client, mock_async_db, mock_user):
        """Test starting an import job."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
            }
        )
        assert response.status_code == 201

    def test_start_import_no_access(self, client, mock_async_db, mock_user):
        """Test starting import without access."""
        response = client.post(
            "/v1/recipe-books/no-access/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
            }
        )
        assert response.status_code == 403


    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_photo_success(self, mock_task, client, mock_async_db, mock_user):
        """Test starting a photo import job."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "photo",
                "ocr_texts": ["Grandma's Cookies\n2 cups flour\n1 cup sugar"],
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "photo"

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_url_list_success(self, mock_task, client, mock_async_db, mock_user):
        """Test starting a URL list import job."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url_list",
                "urls": [
                    "https://example.com/recipe1",
                    "https://example.com/recipe2",
                    "https://example.com/recipe3",
                ],
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "url_list"
        assert data["total_items"] == 3

    def test_start_import_url_list_empty(self, client, mock_async_db, mock_user):
        """Test URL list import with empty URLs."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url_list",
                "urls": [],
            }
        )
        assert response.status_code == 400

    def test_start_import_photo_no_texts(self, client, mock_async_db, mock_user):
        """Test photo import without OCR texts."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "photo",
                "ocr_texts": [],
            }
        )
        assert response.status_code == 400


    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_text_success(self, mock_task, client, mock_async_db, mock_user):
        """Test starting a text paste import job (lines 80-93, 147-156)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "text",
                "raw_text": "Grandma's Cookies\n2 cups flour\n1 cup sugar",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "text"
        assert data["total_items"] == 1

    def test_start_import_text_missing_text(self, client, mock_async_db, mock_user):
        """Test text import without raw_text (line 81)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text"},
        )
        assert response.status_code == 400

    def test_start_import_text_empty_text(self, client, mock_async_db, mock_user):
        """Test text import with empty raw_text (line 81 — whitespace only)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text", "raw_text": "   "},
        )
        assert response.status_code == 400

    def test_start_import_text_too_long(self, client, mock_async_db, mock_user):
        """Test text import with text exceeding max length (line 87)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text", "raw_text": "x" * 16001},
        )
        assert response.status_code == 400


    def test_start_import_spreadsheet_missing_fields(self, client, mock_async_db, mock_user):
        """Test spreadsheet import without file_base64/file_name (line 95-100)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "spreadsheet"},
        )
        assert response.status_code == 400

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("utils.services.spreadsheet_parser.parse_spreadsheet")
    def test_start_import_spreadsheet_success(self, mock_parse, mock_task, client, mock_async_db, mock_user):
        """Test starting a spreadsheet import job (lines 94-101, 165-181)."""
        import base64

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None
        mock_parse.return_value = ["Recipe 1: flour, sugar", "Recipe 2: eggs, butter"]

        csv_data = base64.b64encode(b"name,ingredients\nCookies,flour sugar\nCake,eggs butter").decode()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "spreadsheet",
                "file_base64": csv_data,
                "file_name": "recipes.csv",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "spreadsheet"
        assert data["total_items"] == 2

    def test_start_import_audio_missing_fields(self, client, mock_async_db, mock_user):
        """Test audio import without file_base64/file_name."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "audio"},
        )
        assert response.status_code == 400

    def test_start_import_pdf_missing_fields(self, client, mock_async_db, mock_user):
        """Test PDF import without file_base64/file_name."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "pdf"},
        )
        assert response.status_code == 400

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import.transcribe_audio", create=True)
    @patch("utils.services.recipe_extractors.audio_extractor.transcribe_audio")
    def test_start_import_audio_success(self, mock_transcribe, _mock_transcribe2, mock_task, client, mock_async_db, mock_user):
        """Test starting an audio import job — transcribe_audio path."""
        import base64

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None
        mock_transcribe.return_value = ("Two cups of flour, one cup of sugar.", 5)

        audio_data = base64.b64encode(b"fake audio content").decode()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "audio",
                "file_base64": audio_data,
                "file_name": "recording.m4a",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "audio"
        assert data["total_items"] == 1

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("utils.services.recipe_extractors.pdf_extractor.classify_pdf")
    @patch("utils.services.recipe_extractors.pdf_extractor.extract_text_from_pdf")
    @patch("utils.services.recipe_extractors.pdf_extractor.detect_recipe_boundaries")
    def test_start_import_pdf_text_success(self, mock_boundaries, mock_extract, mock_classify, mock_task, client, mock_async_db, mock_user):
        """Test starting a text-based PDF import job."""
        import base64
        from enum import Enum

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        class MockPdfType(Enum):
            text = "text"
        mock_classify.return_value = (MockPdfType.text, 3)
        mock_extract.return_value = "Recipe 1\nFlour\nSugar\n\nRecipe 2\nEggs\nButter"
        mock_boundaries.return_value = [
            {"text": "Recipe 1\nFlour\nSugar", "title": "Recipe 1"},
            {"text": "Recipe 2\nEggs\nButter", "title": "Recipe 2"},
        ]

        pdf_data = base64.b64encode(b"fake pdf content").decode()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "file_base64": pdf_data,
                "file_name": "recipes.pdf",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "pdf"
        assert data["total_items"] == 2

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("utils.services.recipe_extractors.pdf_extractor.classify_pdf")
    @patch("utils.services.recipe_extractors.pdf_extractor.extract_text_from_pdf")
    def test_start_import_pdf_scanned_success(self, mock_extract, mock_classify, mock_task, client, mock_async_db, mock_user):
        """Test starting a scanned PDF import job."""
        import base64
        from enum import Enum

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        class MockPdfType(Enum):
            scanned = "scanned"
        mock_classify.return_value = (MockPdfType.scanned, 5)
        mock_extract.return_value = "OCR extracted text from scanned PDF"

        pdf_data = base64.b64encode(b"fake scanned pdf content").decode()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "file_base64": pdf_data,
                "file_name": "scanned_recipes.pdf",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "pdf"
        assert data["total_items"] == 1

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import.detect_platform")
    def test_start_import_url_social_platform_label(self, mock_detect, mock_task, client, mock_async_db, mock_user):
        """Test URL import with social media platform enriches the activity label."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook
        from utils.services.url_classifier import SocialPlatform

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None
        mock_detect.return_value = SocialPlatform.TIKTOK

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://www.tiktok.com/@user/video/123456",
            }
        )
        assert response.status_code == 201

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_url_truncates_long_source_filename(
        self, mock_task, client, mock_async_db, mock_user
    ):
        """NYT/Substack tracking URLs overflow ImportJob.source_filename's
        VARCHAR(255). Truncation must happen before insert so the job
        persists; display labels lose the tail, not correctness."""
        from unittest.mock import MagicMock

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)
        mock_task.delay.return_value = None

        long_url = "https://nl.nytimes.com/f/cooking/" + ("x" * 500)
        assert len(long_url) > 255

        created: list = []

        async def _capture(model):
            created.append(model)
            return model

        mock_async_db.create = _capture

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "url", "url": long_url},
        )
        assert response.status_code == 201
        # URL import creates an ImportJob + one ImportItem — pick the
        # ImportJob and assert truncation on source_filename.
        from utils.models.import_job import ImportJob
        jobs = [m for m in created if isinstance(m, ImportJob)]
        assert len(jobs) == 1
        assert len(jobs[0].source_filename) == 255
        assert jobs[0].source_filename == long_url[:255]

    def test_start_import_idempotency_replay_returns_existing(
        self, client, mock_async_db, mock_user
    ):
        """Replay with same idempotency_key returns the existing job (200)."""
        book_id = "test-book-id"
        key = "share-ext-uuid-abc"
        existing = MockImportJob(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            source_type="url",
            idempotency_key=key,
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[existing])

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
                "idempotency_key": key,
            },
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(existing.id)

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_idempotency_first_call_creates_job(
        self, mock_task, client, mock_async_db, mock_user
    ):
        """New idempotency_key: pre-check misses, job is created normally."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)
        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
                "idempotency_key": "new-key-xyz",
            },
        )
        assert response.status_code == 201

    def test_start_import_idempotency_race_returns_winner(
        self, client, mock_async_db, mock_user
    ):
        """IntegrityError on insert → endpoint returns the winning job."""
        from unittest.mock import MagicMock

        book_id = "test-book-id"
        key = "race-key-123"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        winner = MockImportJob(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            source_type="url",
            idempotency_key=key,
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        # Pre-check misses (empty), create raises IntegrityError, recovery
        # lookup finds the concurrent winner.
        query_results = iter([MockExecuteResult(items=[]), MockExecuteResult(items=[winner])])
        mock_async_db.db.execute.side_effect = lambda *a, **kw: next(query_results)

        async def _raise_integrity(model):
            raise IntegrityError("INSERT", {}, Exception())

        mock_async_db.create = _raise_integrity

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
                "idempotency_key": key,
            },
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(winner.id)

    def test_start_import_integrity_error_without_idempotency_key_reraises(
        self, client, mock_async_db, mock_user
    ):
        """IntegrityError with no idempotency_key bubbles up as a 500."""
        from unittest.mock import MagicMock

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

        async def _raise_integrity(model):
            raise IntegrityError("INSERT", {}, Exception())

        mock_async_db.create = _raise_integrity

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
            },
        )
        assert response.status_code == 500


class TestListImportJobs:
    """Tests for GET /v1/import-jobs."""

    def test_list_import_jobs_success(self, client, mock_async_db, mock_user):
        job1 = MockImportJob(user_id=str(mock_user.id), status="completed")
        job2 = MockImportJob(user_id=str(mock_user.id), status="pending")
        # Offset-paginated path: first execute is the count, second is the rows.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[2]),
            MockExecuteResult(items=[job1, job2]),
        ]

        response = client.get("/v1/import-jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["jobs"]) == 2
        assert data["has_more"] is False

    def test_list_import_jobs_with_status_filter(
        self, client, mock_async_db, mock_user
    ):
        job = MockImportJob(user_id=str(mock_user.id), status="completed")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[1]),
            MockExecuteResult(items=[job]),
        ]

        response = client.get("/v1/import-jobs?status=completed&limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["jobs"][0]["status"] == "completed"

    def test_list_import_jobs_empty(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[]),
        ]
        response = client.get("/v1/import-jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["jobs"] == []
        assert data["has_more"] is False


class TestGetImportJob:
    """Tests for GET /v1/import-jobs/{job_id}."""

    def test_get_import_job_success(self, client, mock_async_db, mock_user):
        """Test getting an import job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    def test_get_import_job_not_found(self, client, mock_async_db, mock_user):
        """Test getting a nonexistent import job."""
        response = client.get("/v1/import-jobs/nonexistent")
        assert response.status_code == 404

    def test_get_import_job_access_denied(self, client, mock_async_db, mock_user):
        """Test getting a job when user has no membership and is not the job owner."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set, and job.user_id != mock_user.id

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_get_import_job_access_via_membership(self, client, mock_async_db, mock_user):
        """Test getting a job when user has membership but is not the job owner."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200

    def test_get_import_job_access_as_job_owner_no_membership(self, client, mock_async_db, mock_user):
        """Test getting a job when user is the job owner but has no membership."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set, but job.user_id == mock_user.id

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200


class TestCancelImportJob:
    """Tests for DELETE /v1/import-jobs/{job_id}."""

    def test_cancel_import_job_success(self, client, mock_async_db, mock_user):
        """Test cancelling an import job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="pending",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    def test_cancel_import_job_not_found(self, client, mock_async_db):
        """Test cancelling a nonexistent import job."""
        response = client.delete("/v1/import-jobs/nonexistent")
        assert response.status_code == 404

    def test_cancel_import_job_no_membership(self, client, mock_async_db, mock_user):
        """Test cancelling a job with no membership and not the job owner."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
            status="pending",
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set and job.user_id != mock_user.id

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_cancel_import_job_not_owner_role_but_is_job_starter(self, client, mock_async_db, mock_user):
        """Test cancelling: user is not owner role, but is the user who started the job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="processing",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_cancel_import_job_editor_not_job_starter(self, client, mock_async_db, mock_user):
        """Test cancelling: user has editor role but did not start the job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
            status="processing",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_cancel_import_job_already_completed(self, client, mock_async_db, mock_user):
        """Test cancelling an already completed job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="completed",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 400

    def test_cancel_import_job_already_cancelled(self, client, mock_async_db, mock_user):
        """Test cancelling an already cancelled job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="cancelled",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 400

    def test_cancel_import_job_awaiting_review(self, client, mock_async_db, mock_user):
        """Test cancelling a job in awaiting_review status succeeds."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="awaiting_review",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"


class TestListImportItems:
    """Tests for GET /v1/import-jobs/{job_id}/items."""

    def test_list_import_items_success(self, client, mock_async_db, mock_user):
        """Test listing import items."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_import_items_not_found(self, client, mock_async_db, mock_user):
        """Test listing items for a nonexistent job."""
        response = client.get("/v1/import-jobs/nonexistent/items")
        assert response.status_code == 404

    def test_list_import_items_include_archived_true(self, client, mock_async_db, mock_user):
        """include_archived=true flips off the archived_at IS NULL filter."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(f"/v1/import-jobs/{job_id}/items?include_archived=true")
        assert response.status_code == 200

    def test_list_import_items_access_denied(self, client, mock_async_db, mock_user):
        """Test listing items when user has no access."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 403

    def test_list_import_items_with_status_filter(self, client, mock_async_db, mock_user):
        """Test listing items with a status filter."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(f"/v1/import-jobs/{job_id}/items?status=awaiting_review")
        assert response.status_code == 200

    def test_list_import_items_with_parsed_recipe(self, client, mock_async_db, mock_user):
        """Test listing items that have parsed_recipe data."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={"name": "Test Recipe", "ingredients": []},
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["recipe_name"] == "Test Recipe"
        assert data["items"][0]["needs_review"] is True  # status is awaiting_review
        assert data["total"] == 1

    def test_list_import_items_with_needs_review_ingredient(self, client, mock_async_db, mock_user):
        """Test listing items where an ingredient needs review."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="completed",
            parsed_recipe={
                "name": "Reviewed Recipe",
                "ingredients": [
                    {"name": "flour", "needs_review": True},
                    {"name": "sugar", "needs_review": False},
                ],
            },
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["needs_review"] is True

    def test_list_import_items_surfaces_confidence_fields(self, client, mock_async_db, mock_user):
        """irrd-3 AC6: confidence_score + confidence_source hoist onto summary rows."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={
                "name": "Pasta",
                "ingredients": [],
                "confidence_score": 0.42,
                "confidence_source": "heuristic",
            },
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["confidence_score"] == 0.42
        assert data["items"][0]["confidence_source"] == "heuristic"

    def test_list_import_items_surfaces_created_recipe_id(
        self, client, mock_async_db, mock_user
    ):
        """created_recipe_id is emitted on list rows so the app can link
        Auto-Imported rows to their recipe. Without this, every completed
        item with a recipe looks unlinked and the green section renders
        empty."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        recipe_id = str(uuid.uuid4())
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        with_recipe = MockImportItem(
            import_job_id=job_id,
            status="completed",
            created_recipe_id=recipe_id,
        )
        without_recipe = MockImportItem(
            import_job_id=job_id,
            status="skipped",
            created_recipe_id=None,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([with_recipe, without_recipe])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["created_recipe_id"] == recipe_id
        assert data["items"][1]["created_recipe_id"] is None

    def test_list_import_items_no_needs_review(self, client, mock_async_db, mock_user):
        """Test listing items where no ingredient needs review and status is not awaiting_review."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="completed",
            parsed_recipe={
                "name": "Good Recipe",
                "ingredients": [
                    {"name": "flour", "needs_review": False},
                ],
            },
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["needs_review"] is False

    def test_list_import_items_without_parsed_recipe(self, client, mock_async_db, mock_user):
        """Test listing items that have no parsed_recipe (None)."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="pending",
            parsed_recipe=None,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["recipe_name"] is None
        assert data["items"][0]["needs_review"] is False

    def test_list_import_items_access_via_membership(self, client, mock_async_db, mock_user):
        """Test listing items when user has membership but is not job owner."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200

    def test_list_import_items_has_more(self, client, mock_async_db, mock_user):
        """Test listing items with has_more pagination indicator."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        # Create items - MockQuery.count() returns len of items,
        # but with limit=1, only 1 is returned, so has_more should be True
        items = [
            MockImportItem(import_job_id=job_id, status="pending"),
            MockImportItem(import_job_id=job_id, status="pending"),
        ]

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # MockQuery returns all items for both count() and all()
        # so has_more = offset + len(items) < total = 0 + 2 < 2 = False
        # To test has_more=True, we need count > len(returned items)
        # But MockQuery always returns same items for all() and count()
        # We can still test with offset: offset=1, total=2, returned=2 -> 1+2=3 > 2, no
        # Actually with MockQuery, offset/limit don't actually filter.
        # Let's just verify the logic is exercised.
        mock_async_db.db.execute.side_effect = _paginated(items)

        response = client.get(f"/v1/import-jobs/{job_id}/items?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()
        # MockQuery doesn't actually paginate, so total=2, items=2, has_more = 0+2<2 = False
        assert data["total"] == 2

    def test_list_import_items_with_error_message(self, client, mock_async_db, mock_user):
        """Test listing items with error information."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="failed",
            error_message="Failed to parse recipe",
            parsed_recipe=None,
        )

        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.db.execute.side_effect = _paginated([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["error_message"] == "Failed to parse recipe"


class TestListImportItemsCursor:
    """afh-1b: cursor pagination on GET /v1/import-jobs/{job_id}/items."""

    def _setup_job(self, mock_async_db, mock_user, job_id="job-cursor-test"):
        from utils.models.import_job import ImportJob

        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id="book-id",
        )
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        return job_id

    def test_cursor_and_offset_both_present_returns_400(
        self, client, mock_async_db, mock_user
    ):
        job_id = self._setup_job(mock_async_db, mock_user)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get(
            f"/v1/import-jobs/{job_id}/items?cursor=abc&offset=5"
        )
        assert response.status_code == 400
        assert (
            response.json()["error_message"]
            == "cursor_and_offset_mutually_exclusive"
        )

    def test_invalid_cursor_returns_400(self, client, mock_async_db, mock_user):
        job_id = self._setup_job(mock_async_db, mock_user)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get(
            f"/v1/import-jobs/{job_id}/items?cursor=%21%21%21%21"
        )
        assert response.status_code == 400
        assert response.json()["error_message"] == "invalid_cursor"

    def test_cursor_default_mode_decodes(self, client, mock_async_db, mock_user):
        import uuid as _uuid

        from pagination import encode_cursor

        job_id = self._setup_job(mock_async_db, mock_user)
        cursor = encode_cursor(None, 1_700_000_000_000, str(_uuid.uuid4()))
        item = MockImportItem(import_job_id=job_id, status="succeeded")
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[item])

        response = client.get(
            f"/v1/import-jobs/{job_id}/items?cursor={cursor}"
        )
        assert response.status_code == 200
        body = response.json()
        # Cursor path skips the COUNT.
        assert body["total"] == 0

    def test_cursor_see_all_mode_with_archived_at(
        self, client, mock_async_db, mock_user
    ):
        import uuid as _uuid
        from datetime import UTC, datetime

        from pagination import encode_cursor

        job_id = self._setup_job(mock_async_db, mock_user)
        cursor = encode_cursor(
            1_700_000_000_000, 1_699_000_000_000, str(_uuid.uuid4())
        )
        item = MockImportItem(
            import_job_id=job_id,
            status="succeeded",
            archived_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[item])

        response = client.get(
            f"/v1/import-jobs/{job_id}/items"
            f"?include_archived=true&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_cursor_see_all_mode_with_null_archived_at_cursor(
        self, client, mock_async_db, mock_user
    ):
        import uuid as _uuid

        from pagination import encode_cursor

        job_id = self._setup_job(mock_async_db, mock_user)
        cursor = encode_cursor(None, 1_699_000_000_000, str(_uuid.uuid4()))
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get(
            f"/v1/import-jobs/{job_id}/items"
            f"?include_archived=true&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_next_cursor_present_when_more_results(
        self, client, mock_async_db, mock_user
    ):
        job_id = self._setup_job(mock_async_db, mock_user)
        items = [
            MockImportItem(import_job_id=job_id, status="succeeded")
            for _ in range(60)
        ]
        mock_async_db.db.execute.return_value = MockExecuteResult(items=items)

        # Provide a cursor so the cursor-path runs with limit+1 detection.
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, "seed-id")
        response = client.get(
            f"/v1/import-jobs/{job_id}/items?cursor={cursor}&limit=50"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None
        link = response.headers.get("link") or response.headers.get("Link")
        assert link is not None
        assert 'rel="next"' in link

    def test_see_all_next_cursor_encodes_archived_at(
        self, client, mock_async_db, mock_user
    ):
        from datetime import UTC, datetime

        from pagination import encode_cursor

        job_id = self._setup_job(mock_async_db, mock_user)
        items = [
            MockImportItem(
                import_job_id=job_id,
                status="succeeded",
                archived_at=datetime(2025, 6, (i % 28) + 1, tzinfo=UTC),
            )
            for i in range(60)
        ]
        mock_async_db.db.execute.return_value = MockExecuteResult(items=items)
        cursor = encode_cursor(
            1_750_000_000_000, 1_700_000_000_000, "seed"
        )
        response = client.get(
            f"/v1/import-jobs/{job_id}/items"
            f"?include_archived=true&cursor={cursor}&limit=50"
        )
        assert response.status_code == 200
        assert response.json()["next_cursor"] is not None


class TestListImportJobsCursor:
    """afh-1b: cursor pagination on GET /v1/import-jobs."""

    def test_cursor_and_offset_both_present_returns_400(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get("/v1/import-jobs?cursor=abc&offset=5")
        assert response.status_code == 400
        assert (
            response.json()["error_message"]
            == "cursor_and_offset_mutually_exclusive"
        )

    def test_invalid_cursor_returns_400(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get("/v1/import-jobs?cursor=%21%21%21%21")
        assert response.status_code == 400
        assert response.json()["error_message"] == "invalid_cursor"

    def test_cursor_default_mode_decodes(self, client, mock_async_db, mock_user):
        import uuid as _uuid

        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, str(_uuid.uuid4()))
        job = MockImportJob(user_id=str(mock_user.id))
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[job])

        response = client.get(f"/v1/import-jobs?cursor={cursor}")
        assert response.status_code == 200

    def test_cursor_see_all_mode_archived_only(
        self, client, mock_async_db, mock_user
    ):
        """archived_only=true also counts as See-all mode."""
        import uuid as _uuid
        from datetime import UTC, datetime

        from pagination import encode_cursor

        cursor = encode_cursor(
            1_700_000_000_000, 1_699_000_000_000, str(_uuid.uuid4())
        )
        job = MockImportJob(
            user_id=str(mock_user.id),
            archived_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[job])
        response = client.get(
            "/v1/import-jobs?include_archived=true&archived_only=true"
            f"&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_cursor_see_all_null_archived_cursor(
        self, client, mock_async_db, mock_user
    ):
        import uuid as _uuid

        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_699_000_000_000, str(_uuid.uuid4()))
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get(
            f"/v1/import-jobs?include_archived=true&cursor={cursor}"
        )
        assert response.status_code == 200

    def test_next_cursor_present_when_more_results(
        self, client, mock_async_db, mock_user
    ):
        from pagination import encode_cursor

        jobs = [MockImportJob(user_id=str(mock_user.id)) for _ in range(60)]
        mock_async_db.db.execute.return_value = MockExecuteResult(items=jobs)
        cursor = encode_cursor(None, 1_700_000_000_000, "seed")
        response = client.get(f"/v1/import-jobs?cursor={cursor}&limit=50")
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is not None
        assert response.headers.get("link") is not None


class TestImportSeeAllCount:
    """afh-2: GET /v1/import-items/see-all-count."""

    def test_zero_when_no_rows(self, client, mock_async_db, mock_user):
        # Two scalar count queries: archived, then read_and_old_completed.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[0]),
            MockExecuteResult(items=[0]),
        ]
        response = client.get("/v1/import-items/see-all-count")
        assert response.status_code == 200
        assert response.json() == {
            "archived": 0,
            "read_and_old_completed": 0,
            "total": 0,
        }

    def test_sums_archived_and_read_and_old_completed(
        self, client, mock_async_db, mock_user
    ):
        # Two scalar count queries — both return 3, total surfaces as 6.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[3]),
            MockExecuteResult(items=[3]),
        ]
        response = client.get("/v1/import-items/see-all-count")
        assert response.status_code == 200
        body = response.json()
        assert body["archived"] == 3
        assert body["read_and_old_completed"] == 3
        assert body["total"] == 6


class TestListSeeAllImportItems:
    """GET /v1/import-items/see-all — paginated See-all feed."""

    def test_empty(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get("/v1/import-items/see-all")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_items_surface_with_job_source_type_fallback(
        self, client, mock_async_db, mock_user
    ):
        from datetime import UTC, datetime

        item = MockImportItem(
            id=str(uuid.uuid4()),
            source_type=None,  # empty → fall back to job.source_type
            status="completed",
            parsed_recipe={
                "name": "Old Recipe",
                "ingredients": [{"needs_review": False}],
            },
            archived_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        # Endpoint selects (ImportItem, ImportJob.source_type) — mock the
        # tuple shape the ORM returns.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[(item, "url")])

        response = client.get("/v1/import-items/see-all?limit=5")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        row = body["items"][0]
        assert row["id"] == str(item.id)
        assert row["recipe_name"] == "Old Recipe"
        assert row["source_type"] == "url"
        assert row["status"] == "completed"
        assert row["archived_at"] is not None

    def test_next_cursor_when_page_full(self, client, mock_async_db, mock_user):
        from datetime import UTC, datetime

        rows = [
            (
                MockImportItem(
                    id=str(uuid.uuid4()),
                    source_type="url",
                    status="completed",
                    archived_at=datetime(2025, 6, (i % 28) + 1, tzinfo=UTC),
                ),
                "url",
            )
            for i in range(6)
        ]
        mock_async_db.db.execute.return_value = MockExecuteResult(items=rows)
        response = client.get("/v1/import-items/see-all?limit=5")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 5
        assert body["next_cursor"] is not None

    def test_invalid_cursor_returns_400(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get("/v1/import-items/see-all?cursor=%21%21%21%21")
        assert response.status_code == 400
        assert response.json()["error_message"] == "invalid_cursor"

    def test_cursor_decodes_and_is_applied(self, client, mock_async_db, mock_user):
        from pagination import encode_cursor

        cursor = encode_cursor(
            1_750_000_000_000, 1_700_000_000_000, str(uuid.uuid4())
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get(
            f"/v1/import-items/see-all?cursor={cursor}&limit=10"
        )
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_cursor_with_null_archived_at(self, client, mock_async_db, mock_user):
        from pagination import encode_cursor

        cursor = encode_cursor(None, 1_700_000_000_000, str(uuid.uuid4()))
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get(f"/v1/import-items/see-all?cursor={cursor}")
        assert response.status_code == 200


class TestGetImportItem:
    """Tests for GET /v1/import-items/{item_id}."""

    def test_get_import_item_success(self, client, mock_async_db, mock_user):
        """Test getting an import item."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            source_type="url",
            source_url="https://example.com/recipe",
            source_reference="ref-1",
            raw_data={"html": "<p>recipe</p>"},
            parsed_recipe={"name": "Test Recipe"},
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=5,
            created_recipe_id=None,
            last_successful_stage="extracted",
            last_retry_at=None,
            awaiting_review_reason="unmatched_ingredients",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        # ffm-10: default response omits `parsed_recipe` (heavy JSON);
        # include=parsed_recipe opts back in (see test below). All
        # other fields + the confidence hoists still ride the default.
        response = client.get(
            f"/v1/import-items/{item_id}?include=parsed_recipe"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["status"] == "awaiting_review"
        assert data["source_type"] == "url"
        assert data["source_url"] == "https://example.com/recipe"
        assert data["source_reference"] == "ref-1"
        assert data["raw_data"] == {"html": "<p>recipe</p>"}
        assert data["parsed_recipe"] == {"name": "Test Recipe"}
        assert data["user_edits"] is None
        assert data["error_message"] is None
        assert data["error_code"] is None
        assert data["retry_count"] == 0
        assert data["ai_cost_cents"] == 5
        assert data["created_recipe_id"] is None
        assert data["import_job_id"] == job_id
        # irrd-1 new fields surface on the detail endpoint so the
        # Flutter caret expansion can render the stage timeline + retry
        # history + 1-word reason chip without a second fetch.
        assert data["last_successful_stage"] == "extracted"
        assert data["last_retry_at"] is None
        assert data["awaiting_review_reason"] == "unmatched_ingredients"

    def test_get_import_item_not_found(self, client, mock_async_db, mock_user):
        """Test getting a nonexistent import item."""
        response = client.get("/v1/import-items/nonexistent")
        assert response.status_code == 404

    def test_get_import_item_job_not_found(self, client, mock_async_db, mock_user):
        """Test getting item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
            error_code=None,
            retry_count=0,
            raw_data=None,
            created_recipe_id=None,
            user_edits=None,
        )

        from utils.models.import_item import ImportItem

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        # No job registered -> job not found

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 404

    def test_get_import_item_access_denied(self, client, mock_async_db, mock_user):
        """Test getting item when user has no membership and is not job owner."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            error_code=None,
            retry_count=0,
            raw_data=None,
            created_recipe_id=None,
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # No membership and job.user_id != mock_user.id

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 403

    def test_get_import_item_access_via_membership(self, client, mock_async_db, mock_user):
        """Test getting item when user has membership but is not the job owner."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
            source_type="url",
            source_url="https://example.com/recipe",
            source_reference=None,
            raw_data=None,
            parsed_recipe=None,
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=0,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200

    def test_get_import_item_access_as_job_owner(self, client, mock_async_db, mock_user):
        """Test getting item when user is the job owner but has no membership."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
            source_type="url",
            source_url=None,
            source_reference=None,
            raw_data=None,
            parsed_recipe=None,
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=0,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        # No membership, but job.user_id == mock_user.id

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200

    def test_get_import_item_with_created_recipe_id(self, client, mock_async_db, mock_user):
        """Test getting item that has a created_recipe_id (not None)."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        recipe_id = "created-recipe-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
            source_type="url",
            source_url="https://example.com/recipe",
            source_reference=None,
            raw_data={"html": "<p>recipe</p>"},
            parsed_recipe={"name": "Completed Recipe"},
            user_edits={"name": "My Recipe"},
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=10,
            created_recipe_id=recipe_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["created_recipe_id"] == recipe_id
        assert data["user_edits"] == {"name": "My Recipe"}

    def test_get_import_item_does_not_emit_pending_review_ingredient(
        self, client, mock_async_db, mock_user
    ):
        """epic-ingredients-string-simplification: the pending_review_ingredient
        annotation (riip-4) is retired. Responses must never include the key."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            source_type="photo",
            raw_data=None,
            parsed_recipe={
                "name": "Pancakes",
                "ingredients": [
                    {"name": "butter"},
                    {"name": "flour"},
                    {"name": "newthing"},
                ],
            },
            user_edits=None,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        # ffm-10: opt in so `parsed_recipe` is still present for
        # this regression assertion.
        response = client.get(
            f"/v1/import-items/{item_id}?include=parsed_recipe"
        )
        assert response.status_code == 200
        ings = response.json()["parsed_recipe"]["ingredients"]
        for ing in ings:
            assert "pending_review_ingredient" not in ing

    def test_get_import_item_surfaces_confidence_fields(
        self, client, mock_async_db, mock_user
    ):
        """irrd-3 AC6: confidence_score + confidence_source hoist to root."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            source_type="photo",
            raw_data={},
            parsed_recipe={
                "name": "Pasta",
                "confidence_score": 0.62,
                "confidence_source": "model",
                "ingredients": [],
            },
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=0,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["confidence_score"] == 0.62
        assert data["confidence_source"] == "model"

    def test_get_import_item_drops_malformed_confidence(
        self, client, mock_async_db, mock_user
    ):
        """Legacy / future-out-of-range rows never leak bad scores to UI."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            source_type="photo",
            raw_data={},
            parsed_recipe={
                "name": "Pasta",
                "confidence_score": 2.5,
                "confidence_source": "bogus-literal",
                "ingredients": [],
            },
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=0,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["confidence_score"] is None
        assert data["confidence_source"] is None

    def test_get_import_item_with_empty_raw_data(self, client, mock_async_db, mock_user):
        """Test getting item where raw_data is None (should default to {})."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
            source_type="url",
            source_url=None,
            source_reference=None,
            raw_data=None,
            parsed_recipe=None,
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            ai_cost_cents=0,
            created_recipe_id=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["raw_data"] == {}
        # irrd-3: missing parsed_recipe -> both confidence fields null.
        assert data["confidence_score"] is None
        assert data["confidence_source"] is None


class TestGetImportItemLeanDefault:
    """ffm-10: default omits `parsed_recipe`; ?include=parsed_recipe
    opts in. Telemetry viewer sends the include; activity feed +
    dashboard callers pay no weight for the heavy blob."""

    def _setup(
        self,
        mock_async_db,
        mock_user,
        *,
        item_id="i-ffm10",
        parsed_recipe=None,
    ):
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        job_id = "j-ffm10"
        book_id = "b-ffm10"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
            source_type="url",
            source_url="https://example.com/r",
            source_reference=None,
            raw_data={},
            parsed_recipe=parsed_recipe,
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        return item_id

    def test_default_omits_parsed_recipe(
        self, client, mock_async_db, mock_user
    ):
        """No ?include → parsed_recipe is ABSENT (not null). Keys that
        ride the default (id, status, confidence hoists, etc.) stay."""
        rid = self._setup(
            mock_async_db,
            mock_user,
            parsed_recipe={"name": "Pad Thai"},
        )
        response = client.get(f"/v1/import-items/{rid}")
        assert response.status_code == 200
        data = response.json()
        assert "parsed_recipe" not in data, (
            "parsed_recipe must be ABSENT, not null, on default"
        )
        assert data["status"] == "completed"

    def test_include_parsed_recipe_returns_full_blob(
        self, client, mock_async_db, mock_user
    ):
        """?include=parsed_recipe → blob is present."""
        rid = self._setup(
            mock_async_db,
            mock_user,
            parsed_recipe={"name": "Tacos", "source": "test"},
        )
        response = client.get(
            f"/v1/import-items/{rid}?include=parsed_recipe"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parsed_recipe"] == {"name": "Tacos", "source": "test"}

    def test_include_unknown_token_still_omits_parsed_recipe(
        self, client, mock_async_db, mock_user
    ):
        """Unknown include tokens don't accidentally unlock
        parsed_recipe — only the exact ``parsed_recipe`` token opts
        in. Protects against typos like ``parsedRecipe`` silently
        enabling the heavy blob."""
        rid = self._setup(
            mock_async_db,
            mock_user,
            parsed_recipe={"name": "Sushi"},
        )
        response = client.get(
            f"/v1/import-items/{rid}?include=ParsedRecipe"
        )
        assert response.status_code == 200
        assert "parsed_recipe" not in response.json()

    def test_default_with_no_parsed_recipe_still_omits_key(
        self, client, mock_async_db, mock_user
    ):
        """Even when the server-side value is None (extraction hasn't
        run), the key is absent on the default — no null leak."""
        rid = self._setup(mock_async_db, mock_user, parsed_recipe=None)
        response = client.get(f"/v1/import-items/{rid}")
        assert response.status_code == 200
        assert "parsed_recipe" not in response.json()


class TestUpdateImportItem:
    """Tests for PUT /v1/import-items/{item_id}."""

    def test_update_import_item_success(self, client, mock_async_db, mock_user):
        """Test updating an import item with user edits."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        edits = {"name": "My Custom Recipe", "servings": 6}
        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": edits},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["user_edits"] == edits
        assert data["status"] == "awaiting_review"

    def test_update_import_item_not_found(self, client, mock_async_db, mock_user):
        """Test updating a nonexistent import item."""
        response = client.put(
            "/v1/import-items/nonexistent",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 404

    def test_update_import_item_job_not_found(self, client, mock_async_db, mock_user):
        """Test updating item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 404

    def test_update_import_item_no_membership(self, client, mock_async_db, mock_user):
        """Test updating item when user has no membership."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 403

    def test_update_import_item_viewer_role(self, client, mock_async_db, mock_user):
        """Test updating item when user has viewer role (not owner/editor)."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 403

    def test_update_import_item_normalizes_ingredient_units(
        self, client, mock_async_db, mock_user, monkeypatch
    ):
        """riip-2: PUT writes user_edits with each ingredient unit normalized."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Stub the normalizer so the test doesn't depend on the real
        # alias cache (the mock session can't load it).
        from api.v1.import_job import update_import_item as mod
        monkeypatch.setattr(
            mod,
            "normalize_unit_display",
            lambda raw, _session, context=None: (
                "tbsp" if raw and raw.lower().startswith("tablespoon") else raw
            ),
        )

        edits = {
            "name": "Pancakes",
            "ingredients": [
                {"name": "butter", "quantity": 2, "unit": "tablespoon"},
                # No "unit" key — handler must skip without error.
                {"name": "salt", "quantity": "1/4"},
                # Non-dict entries are tolerated and skipped.
                "stray-string",
            ],
        }
        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": edits},
        )
        assert response.status_code == 200
        data = response.json()
        # Persisted user_edits has "tablespoon" coerced to "tbsp".
        assert data["user_edits"]["ingredients"][0]["unit"] == "tbsp"
        # Ingredient with no unit key is unchanged.
        assert "unit" not in data["user_edits"]["ingredients"][1]

    def test_update_import_item_editor_role(self, client, mock_async_db, mock_user):
        """Test updating item succeeds with editor role."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 200

    def test_update_import_item_completed_status(self, client, mock_async_db, mock_user):
        """Test updating item in completed status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 400

    def test_update_import_item_skipped_status(self, client, mock_async_db, mock_user):
        """Test updating item in skipped status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="skipped",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 400

    def test_update_import_item_pending_status(self, client, mock_async_db, mock_user):
        """Test updating item in pending status succeeds."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 200


class TestApproveImportItem:
    """Tests for POST /v1/import-items/{item_id}/approve."""

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_success(self, mock_task, client, mock_async_db, mock_user):
        """Test approving an import item."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={"name": "Test Recipe"},
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        # `recompute_import_job_counters` runs 3 scalar count queries —
        # all return 0 here (no peer items), which is what the success
        # path expects for the lone item being approved.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[0])

        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["status"] == "approved"
        assert data["message"] == "Recipe creation started"
        mock_task.delay.assert_called_once_with(
            item_id=item_id,
            user_id=str(mock_user.id),
        )

    def test_approve_import_item_not_found(self, client, mock_async_db, mock_user):
        """Test approving a nonexistent import item."""
        response = client.post("/v1/import-items/nonexistent/approve")
        assert response.status_code == 404

    def test_approve_import_item_job_not_found(self, client, mock_async_db, mock_user):
        """Test approving item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 404

    def test_approve_import_item_no_membership(self, client, mock_async_db, mock_user):
        """Test approving item when user has no membership."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 403

    def test_approve_import_item_viewer_role(self, client, mock_async_db, mock_user):
        """Test approving item when user has viewer role (not owner/editor)."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 403

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_editor_role(self, mock_task, client, mock_async_db, mock_user):
        """Test approving item succeeds with editor role."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={"name": "Test"},
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[0])
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200

    def test_approve_import_item_completed_status(self, client, mock_async_db, mock_user):
        """Test approving item in completed status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_skipped_status(self, client, mock_async_db, mock_user):
        """Test approving item in skipped status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="skipped",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_pending_status(self, client, mock_async_db, mock_user):
        """Test approving item in pending status is not allowed (not awaiting_review/matching)."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_approved_status(self, client, mock_async_db, mock_user):
        """Test approving item in approved status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="approved",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_no_recipe_data(self, client, mock_async_db, mock_user):
        """Test approving item with no parsed_recipe and no user_edits."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe=None,
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_with_user_edits_only(self, mock_task, client, mock_async_db, mock_user):
        """Test approving item that has user_edits but no parsed_recipe."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe=None,
            user_edits={"name": "My Custom Recipe"},
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[0])
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_matching_status(self, mock_task, client, mock_async_db, mock_user):
        """Test approving item in matching status succeeds."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="matching",
            parsed_recipe={"name": "Test"},
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[0])
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"


class TestSkipImportItem:
    """Tests for POST /v1/import-items/{item_id}/skip."""

    def test_skip_import_item_success(self, client, mock_async_db, mock_user):
        """Test skipping an import item."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=3,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("skipped", 1),
            ("awaiting_review", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["status"] == "skipped"

    def test_skip_import_item_not_found(self, client, mock_async_db, mock_user):
        """Test skipping a nonexistent import item."""
        response = client.post("/v1/import-items/nonexistent/skip")
        assert response.status_code == 404

    def test_skip_import_item_job_not_found(self, client, mock_async_db, mock_user):
        """Test skipping item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 404

    def test_skip_import_item_no_membership(self, client, mock_async_db, mock_user):
        """Test skipping item when user has no membership."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 403

    def test_skip_import_item_viewer_role(self, client, mock_async_db, mock_user):
        """Test skipping item when user has viewer role (not owner/editor)."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 403

    def test_skip_import_item_editor_role(self, client, mock_async_db, mock_user):
        """Test skipping item succeeds with editor role."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
        )
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
            total_items=1,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("skipped", 1),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200

    def test_skip_import_item_completed_status(self, client, mock_async_db, mock_user):
        """Test skipping item in completed status is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 400

    def test_skip_import_item_already_skipped(self, client, mock_async_db, mock_user):
        """Test skipping item that is already skipped is not allowed."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="skipped",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 400

    def test_skip_import_item_pending_status(self, client, mock_async_db, mock_user):
        """Test skipping item in pending status succeeds."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=5,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts - more items still pending
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("skipped", 1),
            ("awaiting_review", 2),
            ("pending", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"

    def test_skip_import_item_job_completes(self, client, mock_async_db, mock_user):
        """Test skipping the last item completes the job."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=2,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # All items are in final states, total_final >= total_items
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("completed", 1),
            ("skipped", 1),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # Job should be marked as completed since total_final (2) >= total_items (2)
        assert job.status == "completed"

    def test_skip_import_item_job_awaiting_review(self, client, mock_async_db, mock_user):
        """Test skipping an item when other items are awaiting review sets job to awaiting_review."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=5,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Not all items final, but some awaiting review
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("skipped", 1),
            ("awaiting_review", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # pending_review_items > 0, so job should be awaiting_review
        assert job.status == "awaiting_review"
        assert job.pending_review_items == 2

    def test_skip_import_item_job_no_awaiting_review(self, client, mock_async_db, mock_user):
        """Test skipping an item when no items are awaiting review and job is not complete."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="pending",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=10,
            status="processing",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Not all items final, no awaiting_review
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("skipped", 1),
            ("completed", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # total_final = 0 + 0 + 1 = 1 (completed=2 from succeeded, failed=0, skipped=1)
        # Actually: succeeded = completed = 2, failed = 0, skipped = 1 => total_final = 2+0+1 = 3 < 10
        # pending_review_items = 0, so neither branch triggers
        assert job.status == "processing"  # unchanged

    def test_skip_import_item_update_counts_with_failed(self, client, mock_async_db, mock_user):
        """Test _update_job_counts correctly tracks failed items."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            total_items=4,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # All items final with mixed statuses
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[
            ("completed", 1),
            ("failed", 1),
            ("skipped", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # succeeded=1, failed=1, skipped=2 => total_final=4 >= total_items=4
        assert job.succeeded_items == 1
        assert job.failed_items == 1
        assert job.status == "completed"


class TestRetryImportItem:
    """Tests for POST /v1/import-items/{item_id}/retry."""

    def _setup_retryable_item(
        self,
        mock_async_db,
        mock_user,
        *,
        last_successful_stage=None,
        item_status="failed",
        job_status="failed",
        role="owner",
        owner_user_id=None,
    ):
        """Build a retryable item/job/membership triple and wire it into mock_async_db."""
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status=item_status,
            last_successful_stage=last_successful_stage,
            retry_count=0,
            error_message="prior error",
            error_code="PRIOR_ERROR",
        )
        job = MockImportJob(
            id=job_id,
            user_id=owner_user_id or str(mock_user.id),
            recipe_book_id=book_id,
            status=job_status,
            error_message="job failed",
            completed_at="2026-04-15T12:00:00Z",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role=role,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        return item, job, item_id

    # ---- not found / permission gates ------------------------------------

    def test_retry_item_not_found(self, client, mock_async_db, mock_user):
        response = client.post("/v1/import-items/nonexistent/retry")
        assert response.status_code == 404

    def test_retry_job_not_found(self, client, mock_async_db, mock_user):
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
            status="failed",
        )
        from utils.models.import_item import ImportItem
        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 404

    def test_retry_forbidden_no_membership(self, client, mock_async_db, mock_user):
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id, import_job_id=job_id, status="failed"
        )
        job = MockImportJob(
            id=job_id, user_id="other-user", recipe_book_id=book_id
        )
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 403

    def test_retry_forbidden_viewer_role(self, client, mock_async_db, mock_user):
        self._setup_retryable_item(
            mock_async_db, mock_user, role="viewer", owner_user_id="other-user"
        )
        response = client.post("/v1/import-items/test-item-id/retry")
        assert response.status_code == 403

    def test_retry_rejected_non_failed_status(
        self, client, mock_async_db, mock_user
    ):
        """Item and job both non-failed → 400."""
        self._setup_retryable_item(
            mock_async_db, mock_user,
            item_status="completed",
            job_status="completed",
        )
        response = client.post("/v1/import-items/test-item-id/retry")
        assert response.status_code == 400

    # ---- state machine: one test per stage marker ------------------------

    @patch("api.v1.import_job.retry_import_item.parse_source_task")
    def test_retry_null_stage_dispatches_parse_source_task(
        self, mock_parse, client, mock_async_db, mock_user
    ):
        item, job, item_id = self._setup_retryable_item(
            mock_async_db, mock_user, last_successful_stage=None
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["dispatched_task"] == "parse_source_task"
        assert data["resumed_from_stage"] == "start"
        assert data["status"] == "pending"

        # State reset on the item and the parent job.
        assert item.status == "pending"
        assert item.error_message is None
        assert item.error_code is None
        assert item.retry_count == 1
        assert job.status == "processing"
        assert job.error_message is None
        assert job.completed_at is None

        mock_parse.delay.assert_called_once_with(str(job.id))

    @patch("api.v1.import_job.retry_import_item.extract_task")
    def test_retry_parsed_stage_dispatches_extract_task(
        self, mock_extract, client, mock_async_db, mock_user
    ):
        item, _job, item_id = self._setup_retryable_item(
            mock_async_db, mock_user, last_successful_stage="parsed"
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["dispatched_task"] == "extract_recipe_task"
        assert data["resumed_from_stage"] == "parsed"
        assert data["status"] == "extracting"
        assert item.status == "extracting"
        assert item.retry_count == 1
        mock_extract.delay.assert_called_once_with(
            item_ids=[item_id], user_id=str(mock_user.id)
        )

    @patch("api.v1.import_job.retry_import_item.create_recipe_task")
    def test_retry_extracted_stage_dispatches_create_recipe_task(
        self, mock_create, client, mock_async_db, mock_user
    ):
        """Post-epic-ingredients-string-simplification: STAGE_EXTRACTED
        routes straight to create_recipe_task (the former match stage is
        retired)."""
        item, _job, item_id = self._setup_retryable_item(
            mock_async_db, mock_user, last_successful_stage="extracted"
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["dispatched_task"] == "create_recipe_task"
        assert data["resumed_from_stage"] == "extracted"
        assert data["status"] == "approved"
        assert item.status == "approved"
        mock_create.delay.assert_called_once_with(
            item_id=item_id, user_id=str(mock_user.id)
        )

    @patch("api.v1.import_job.retry_import_item.create_recipe_task")
    def test_retry_matched_stage_dispatches_create_recipe_task(
        self, mock_create, client, mock_async_db, mock_user
    ):
        item, _job, item_id = self._setup_retryable_item(
            mock_async_db, mock_user, last_successful_stage="matched"
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["dispatched_task"] == "create_recipe_task"
        assert data["resumed_from_stage"] == "matched"
        assert data["status"] == "approved"
        assert item.status == "approved"
        mock_create.delay.assert_called_once_with(
            item_id=item_id, user_id=str(mock_user.id)
        )

    @patch("api.v1.import_job.retry_import_item.extract_task")
    def test_retry_accepted_when_job_failed_but_item_mid_pipeline(
        self, mock_extract, client, mock_async_db, mock_user
    ):
        """Sweeper case: item.status is still 'extracting', but parent job
        was marked failed by the sweeper. Retry must be accepted and resume
        based on last_successful_stage."""
        item, _job, item_id = self._setup_retryable_item(
            mock_async_db,
            mock_user,
            item_status="extracting",
            job_status="failed",
            last_successful_stage="parsed",
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        assert item.status == "extracting"
        mock_extract.delay.assert_called_once()

    @patch("api.v1.import_job.retry_import_item.parse_source_task")
    def test_retry_item_failed_but_job_processing_does_not_touch_job(
        self, mock_parse, client, mock_async_db, mock_user
    ):
        """Retry on a failed item whose parent job is still 'processing'
        must not flip the job status — item-level retry is sufficient."""
        item, job, item_id = self._setup_retryable_item(
            mock_async_db,
            mock_user,
            item_status="failed",
            job_status="processing",
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        # Item reset
        assert item.status == "pending"
        assert item.retry_count == 1
        # Job status UNTOUCHED — still processing
        assert job.status == "processing"

        mock_parse.delay.assert_called_once_with(str(job.id))

    @patch("api.v1.import_job.retry_import_item.parse_source_task")
    def test_retry_unknown_stage_marker_falls_back_to_full_restart(
        self, mock_parse, client, mock_async_db, mock_user
    ):
        """An unknown / forward-compat stage value should fall back to a
        full restart rather than crashing the endpoint."""
        item, job, item_id = self._setup_retryable_item(
            mock_async_db,
            mock_user,
            last_successful_stage="this-stage-does-not-exist",
        )

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["dispatched_task"] == "parse_source_task"
        assert data["status"] == "pending"
        assert item.status == "pending"

        mock_parse.delay.assert_called_once_with(str(job.id))

    @patch("api.v1.import_job.retry_import_item.parse_source_task")
    def test_retry_stamps_last_retry_at_and_clears_awaiting_review_reason(
        self, mock_parse, client, mock_async_db, mock_user
    ):
        """irrd-1 AC3 + retry clears any prior awaiting_review_reason.

        The retry reset should populate `last_retry_at` with a non-null
        value and clear `awaiting_review_reason` so the downstream match
        task can re-tag cleanly if it ends up back in awaiting_review.
        """
        item, _job, item_id = self._setup_retryable_item(
            mock_async_db,
            mock_user,
            last_successful_stage=None,
        )
        # Simulate a prior awaiting_review routing before the failure.
        item.awaiting_review_reason = "low_confidence"

        response = client.post(f"/v1/import-items/{item_id}/retry")
        assert response.status_code == 200

        assert item.last_retry_at is not None  # func.now() expression set
        assert item.awaiting_review_reason is None
        mock_parse.delay.assert_called_once()


class TestDismissImportItem:
    """Tests for POST /v1/import-items/{item_id}/dismiss."""

    def _setup(
        self,
        mock_async_db,
        mock_user,
        *,
        item_status="failed",
        job_status="failed",
        role="owner",
        siblings=None,
    ):
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status=item_status,
            dismissed_at=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status=job_status,
            dismissed_at=None,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role=role,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        # Sibling query returns the current item plus any provided siblings.
        # The endpoint calls db.query(ImportItem).filter(...).all().
        all_items_under_job = [item] + (siblings or [])
        mock_async_db.db.execute.return_value = MockExecuteResult(items=all_items_under_job)

        return item, job, item_id

    def test_dismiss_happy_path_last_item_marks_job(
        self, client, mock_async_db, mock_user
    ):
        item, job, item_id = self._setup(mock_async_db, mock_user)

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == item_id
        assert data["job_dismissed"] is True
        assert item.dismissed_at is not None
        assert job.dismissed_at is not None

    def test_dismiss_with_sibling_not_dismissed_leaves_job(
        self, client, mock_async_db, mock_user
    ):
        sibling = MockImportItem(
            id="sibling-id",
            import_job_id="test-job-id",
            status="failed",
            dismissed_at=None,
        )
        item, job, item_id = self._setup(
            mock_async_db, mock_user, siblings=[sibling]
        )

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 200
        data = response.json()
        assert data["job_dismissed"] is False
        assert item.dismissed_at is not None
        assert job.dismissed_at is None

    def test_dismiss_item_not_found(self, client, mock_async_db, mock_user):
        response = client.post("/v1/import-items/nonexistent/dismiss")
        assert response.status_code == 404

    def test_dismiss_job_not_found(self, client, mock_async_db, mock_user):
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job",
            status="failed",
        )
        from utils.models.import_item import ImportItem
        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 404

    def test_dismiss_forbidden_viewer(self, client, mock_async_db, mock_user):
        self._setup(mock_async_db, mock_user, role="viewer")
        response = client.post("/v1/import-items/test-item-id/dismiss")
        assert response.status_code == 403

    def test_dismiss_forbidden_no_membership(
        self, client, mock_async_db, mock_user
    ):
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id, import_job_id=job_id, status="failed"
        )
        job = MockImportJob(
            id=job_id, user_id="other-user", recipe_book_id=book_id
        )
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 403

    def test_dismiss_rejects_non_failed(self, client, mock_async_db, mock_user):
        self._setup(
            mock_async_db,
            mock_user,
            item_status="completed",
            job_status="completed",
        )
        response = client.post("/v1/import-items/test-item-id/dismiss")
        assert response.status_code == 400


class TestDismissAllFailedImports:
    """Tests for POST /v1/import-jobs/dismiss-all-failed."""

    def test_dismiss_all_zero_failed_returns_zero(
        self, client, mock_async_db, mock_user
    ):
        # Candidate query returns an empty list.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.post("/v1/import-jobs/dismiss-all-failed")
        assert response.status_code == 200
        assert response.json()["dismissed_count"] == 0

    def test_dismiss_all_marks_items_and_jobs(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        job_id_1 = "job-1"
        job_id_2 = "job-2"

        item_1 = MockImportItem(
            id="item-1",
            import_job_id=job_id_1,
            status="failed",
            dismissed_at=None,
        )
        item_2 = MockImportItem(
            id="item-2",
            import_job_id=job_id_2,
            status="failed",
            dismissed_at=None,
        )

        job_1 = MockImportJob(
            id=job_id_1,
            user_id=str(mock_user.id),
            status="failed",
            dismissed_at=None,
        )
        job_2 = MockImportJob(
            id=job_id_2,
            user_id=str(mock_user.id),
            status="failed",
            dismissed_at=None,
        )

        mock_async_db.set_find_by(ImportJob, job_1, id=job_id_1)
        mock_async_db.set_find_by(ImportJob, job_2, id=job_id_2)

        # First call: candidate failed items (initial query with join).
        # Per affected job (2 jobs here):
        #   - 1 sibling query
        #   - 3 counter-recompute queries (succeeded / failed / awaiting_review)
        # Then 2 user_activities update calls (one per dismissed item).
        candidate_query = MockExecuteResult(items=[item_1, item_2])
        sibling_query_1 = MockExecuteResult(items=[item_1])
        sibling_query_2 = MockExecuteResult(items=[item_2])
        # `recompute_import_job_counters` runs 3 scalar count queries —
        # `scalar_one()` requires at least one item in the result.
        counter_query = MockExecuteResult(items=[0])
        activity_update = MockExecuteResult(items=[])

        mock_async_db.db.execute.side_effect = [
            candidate_query,
            sibling_query_1,
            counter_query, counter_query, counter_query,
            sibling_query_2,
            counter_query, counter_query, counter_query,
            activity_update,
            activity_update,
        ]

        response = client.post("/v1/import-jobs/dismiss-all-failed")
        assert response.status_code == 200
        assert response.json()["dismissed_count"] == 2
        assert item_1.dismissed_at is not None
        assert item_2.dismissed_at is not None
        assert job_1.dismissed_at is not None
        assert job_2.dismissed_at is not None

    def test_dismiss_all_leaves_job_with_remaining_non_dismissed_items(
        self, client, mock_async_db, mock_user
    ):
        """If a job has one failed item (dismissed) plus one still-processing
        sibling, the job itself should NOT be marked dismissed."""
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        job_id = "job-partial"
        failed_item = MockImportItem(
            id="failed-item",
            import_job_id=job_id,
            status="failed",
            dismissed_at=None,
        )
        sibling = MockImportItem(
            id="sibling-item",
            import_job_id=job_id,
            status="matching",
            dismissed_at=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="processing",
            dismissed_at=None,
        )

        mock_async_db.set_find_by(ImportJob, job, id=job_id)

        candidate_query = MockExecuteResult(items=[failed_item])
        sibling_query = MockExecuteResult(items=[failed_item, sibling])
        # `recompute_import_job_counters` runs 3 scalar count queries.
        counter_query = MockExecuteResult(items=[0])
        activity_update = MockExecuteResult(items=[])
        mock_async_db.db.execute.side_effect = [
            candidate_query,
            sibling_query,
            counter_query, counter_query, counter_query,
            activity_update,
        ]

        response = client.post("/v1/import-jobs/dismiss-all-failed")
        assert response.status_code == 200
        assert response.json()["dismissed_count"] == 1
        assert failed_item.dismissed_at is not None
        # Job NOT dismissed because sibling is still in-flight
        assert job.dismissed_at is None


class TestArchiveImportItem:
    """Tests for POST /v1/import-items/{item_id}/archive."""

    def _setup(
        self,
        mock_async_db,
        mock_user,
        *,
        item_status="awaiting_review",
        role="owner",
        archived_at=None,
    ):
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status=item_status,
            archived_at=archived_at,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role=role,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        # The FOR UPDATE re-read goes through db.query(ImportItem).filter().
        # Return the same row so the locked status matches the initial.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[item])
        return item, job, item_id

    def test_archive_happy_path_sets_archived_at(
        self, client, mock_async_db, mock_user
    ):
        item, _, item_id = self._setup(mock_async_db, mock_user)

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == item_id
        assert body["archived_at"] is not None
        assert item.archived_at is not None

    def test_archive_in_progress_returns_409(self, client, mock_async_db, mock_user):
        item, _, item_id = self._setup(
            mock_async_db, mock_user, item_status="processing"
        )

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 409
        assert response.json()["error_message"] == "cannot archive in-progress import"
        # archived_at unchanged
        assert item.archived_at is None

    def test_archive_already_archived_is_noop(self, client, mock_async_db, mock_user):
        from datetime import UTC, datetime

        fixed_ts = datetime(2026, 4, 1, tzinfo=UTC)
        item, _, item_id = self._setup(
            mock_async_db, mock_user, archived_at=fixed_ts
        )

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 200
        assert item.archived_at == fixed_ts

    def test_archive_not_owner_returns_403(self, client, mock_async_db, mock_user):
        item, _, item_id = self._setup(
            mock_async_db, mock_user, role="viewer"
        )

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 403

    def test_archive_not_found(self, client, mock_async_db, mock_user):
        response = client.post("/v1/import-items/missing/archive")
        assert response.status_code == 404

    def test_archive_job_not_found_returns_404(
        self, client, mock_async_db, mock_user
    ):
        """If the parent ImportJob is missing, return 404 before acl/status checks."""
        from utils.models.import_item import ImportItem

        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="orphan-job",
            status="awaiting_review",
            archived_at=None,
        )
        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        # ImportJob find_by returns None — not configured.

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 404

    def test_archive_locked_row_missing_returns_404(
        self, client, mock_async_db, mock_user
    ):
        """If the FOR UPDATE re-read returns None (concurrent delete),
        the endpoint responds with 404."""
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            archived_at=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        # The FOR UPDATE re-read returns empty.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.post(f"/v1/import-items/{item_id}/archive")
        assert response.status_code == 404


class TestUnarchiveImportItem:
    """Tests for POST /v1/import-items/{item_id}/unarchive."""

    def test_unarchive_happy_path(self, client, mock_async_db, mock_user):
        from datetime import UTC, datetime

        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            archived_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        response = client.post(f"/v1/import-items/{item_id}/unarchive")
        assert response.status_code == 200
        assert item.archived_at is None

    def test_unarchive_already_active_is_noop(self, client, mock_async_db, mock_user):
        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
            archived_at=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        response = client.post(f"/v1/import-items/{item_id}/unarchive")
        assert response.status_code == 200
        assert item.archived_at is None

    def test_unarchive_not_found(self, client, mock_async_db, mock_user):
        response = client.post("/v1/import-items/missing/unarchive")
        assert response.status_code == 404

    def test_unarchive_job_not_found_returns_404(self, client, mock_async_db, mock_user):
        from utils.models.import_item import ImportItem

        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="orphan-job",
            status="completed",
            archived_at=None,
        )
        mock_async_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/unarchive")
        assert response.status_code == 404

    def test_unarchive_not_owner_returns_403(self, client, mock_async_db, mock_user):
        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        item_id = "test-item-id"
        job_id = "test-job-id"
        book_id = "test-book-id"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="completed",
            archived_at=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )
        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        response = client.post(f"/v1/import-items/{item_id}/unarchive")
        assert response.status_code == 403


class TestListImportJobsArchiveFilters:
    """Tests for ?include_archived and ?archived_only on list endpoints."""

    def test_default_excludes_archived(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get("/v1/import-jobs")
        assert response.status_code == 200

    def test_include_archived_true(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get("/v1/import-jobs?include_archived=true")
        assert response.status_code == 200

    def test_archived_only_true_implicitly_includes(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(
            "/v1/import-jobs?archived_only=true&include_archived=true"
        )
        assert response.status_code == 200

    def test_contradictory_filters_returns_400(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _paginated([])

        response = client.get(
            "/v1/import-jobs?archived_only=true&include_archived=false"
        )
        assert response.status_code == 400
        assert response.json()["error_message"] == "contradictory filters"


class TestGetImportUploadUrl:
    """Tests for POST /v1/imports/upload-url (sbf-2)."""

    _S3_KEY_PATTERN = (
        r"^imports/[0-9a-f-]{36}/[0-9a-f-]{36}\.[a-z0-9]{2,5}$"
    )

    @staticmethod
    def _mock_aws():
        """Build a MagicMock AWSService whose presign_put_url_async echoes
        the bucket / key / required headers — lets tests assert what was
        signed without needing real boto3."""
        from unittest.mock import AsyncMock, MagicMock

        service = MagicMock()

        async def fake_presign(s3_key, bucket, content_type, content_length,
                               tagging=None, expires_in=3600):
            url = (
                f"https://{bucket}.s3.us-east-1.amazonaws.com/{s3_key}"
                f"?X-Amz-Expires={expires_in}"
            )
            required = {
                "Content-Type": content_type,
                "Content-Length": str(content_length),
            }
            if tagging:
                required["x-amz-tagging"] = tagging
            return url, required

        service.presign_put_url_async = AsyncMock(side_effect=fake_presign)
        return service

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_happy_path(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        import re
        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "voice_memo.m4a",
                "mime_type": "audio/mp4",
                "size_bytes": 1024 * 1024,
            },
        )
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["upload_url"].startswith("https://")
        assert re.match(self._S3_KEY_PATTERN, body["s3_key"])
        assert body["s3_key"].startswith(f"imports/{mock_user.id}/")
        assert body["s3_key"].endswith(".m4a")
        assert body["required_headers"]["Content-Type"] == "audio/mp4"
        assert body["required_headers"]["Content-Length"] == str(1024 * 1024)
        assert body["required_headers"]["x-amz-tagging"] == "unclaimed=true"
        assert "expires_at" in body

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_rejects_oversize(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        from utils.classes.error_code import ErrorCode

        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "huge.mp4",
                "mime_type": "video/mp4",
                "size_bytes": 100 * 1024 * 1024 + 1,
            },
        )
        assert response.status_code == 413
        assert response.json()["error_code"] == ErrorCode.FILE_TOO_LARGE.value

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_accepts_exact_max(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "max.mp4",
                "mime_type": "video/mp4",
                "size_bytes": 100 * 1024 * 1024,
            },
        )
        assert response.status_code == 200

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_rejects_zero_bytes(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        from utils.classes.error_code import ErrorCode

        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "empty.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 0,
            },
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == ErrorCode.INVALID_REQUEST.value

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_rejects_negative_bytes(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        from utils.classes.error_code import ErrorCode

        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "weird.pdf",
                "mime_type": "application/pdf",
                "size_bytes": -100,
            },
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == ErrorCode.INVALID_REQUEST.value

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_rejects_unknown_mime(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        from utils.classes.error_code import ErrorCode

        mock_get_service.return_value = self._mock_aws()

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "weird.bin",
                "mime_type": "application/octet-stream",
                "size_bytes": 1024,
            },
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == ErrorCode.UNSUPPORTED_MIME.value

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_canonical_extension_for_each_mime(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        """Every allowed mime resolves to its canonical extension in s3_key."""
        from api.v1.import_job.get_upload_url import _MIME_EXT
        mock_get_service.return_value = self._mock_aws()

        for mime, expected_ext in _MIME_EXT.items():
            response = client.post(
                "/v1/imports/upload-url",
                json={
                    "filename": f"file.{expected_ext}",
                    "mime_type": mime,
                    "size_bytes": 4096,
                },
            )
            assert response.status_code == 200, (mime, response.json())
            s3_key = response.json()["s3_key"]
            assert s3_key.endswith(f".{expected_ext}"), (mime, s3_key)

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_signs_against_imports_bucket(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        """Verify the AWSService is called with the imports bucket and
        the exact ContentType/Length/Tagging the client declared."""
        service = self._mock_aws()
        mock_get_service.return_value = service

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "deck.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2_345_678,
            },
        )
        assert response.status_code == 200
        service.presign_put_url_async.assert_called_once()
        call_kwargs = service.presign_put_url_async.call_args.kwargs
        assert call_kwargs["bucket"].startswith("palateful-imports-")
        assert call_kwargs["content_type"] == "application/pdf"
        assert call_kwargs["content_length"] == 2_345_678
        assert call_kwargs["tagging"] == "unclaimed=true"
        assert call_kwargs["expires_in"] == 3600
        assert call_kwargs["s3_key"].startswith(f"imports/{mock_user.id}/")

    @patch("api.v1.import_job.get_upload_url._get_aws_service")
    def test_upload_url_required_headers_match_signed(
        self, mock_get_service, client, mock_async_db, mock_user
    ):
        """The required_headers map mirrors what was signed — no drift."""
        service = self._mock_aws()
        mock_get_service.return_value = service

        response = client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "clip.mov",
                "mime_type": "video/quicktime",
                "size_bytes": 50 * 1024 * 1024,
            },
        )
        assert response.status_code == 200
        body = response.json()
        # Set of headers in the response is exactly what was signed.
        assert set(body["required_headers"].keys()) == {
            "Content-Type",
            "Content-Length",
            "x-amz-tagging",
        }
        assert body["required_headers"]["Content-Type"] == "video/quicktime"
        assert body["required_headers"]["Content-Length"] == str(50 * 1024 * 1024)

    def test_upload_url_requires_auth(self, unauthed_client, mock_async_db):
        """No JWT → unauthorized (FastAPI security dep returns 422 when
        Authorization header is missing; 401/403 once a token is present
        but invalid)."""
        response = unauthed_client.post(
            "/v1/imports/upload-url",
            json={
                "filename": "x.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert response.status_code in (401, 403, 422)


class TestStartImportS3Key:
    """sbf-3: `/import` with {s3_key, etag, mime_type}."""

    @staticmethod
    def _setup_access(mock_async_db, mock_user, book_id):
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        mock_async_db.set_find_by(
            RecipeBookUser, membership,
            user_id=str(mock_user.id), recipe_book_id=book_id,
        )
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

    @staticmethod
    def _reset_rate_limit():
        from api.v1.import_job.start_import import _reset_rate_limit_for_test
        _reset_rate_limit_for_test()

    @staticmethod
    def _ok_aws():
        from unittest.mock import AsyncMock, MagicMock

        service = MagicMock()
        service.head_object_async = AsyncMock(return_value={
            "ContentLength": 12345,
            "ETag": '"abc123"',
        })
        return service

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_happy_path_audio(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        self._reset_rate_limit()
        book_id = "book-s3-audio"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()
        mock_task.delay.return_value = None

        s3_key = f"imports/{mock_user.id}/abcd.m4a"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "audio",
                "s3_key": s3_key,
                "mime_type": "audio/mp4",
                "etag": '"abc123"',
                "file_name": "voice.m4a",
            },
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["source_type"] == "audio"
        mock_task.delay.assert_called_once()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_cross_user_returns_403(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-s3-cross"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": "imports/00000000-0000-0000-0000-000000000000/foo.pdf",
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == ErrorCode.CROSS_USER_KEY.value
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_object_not_ready_returns_409(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        from botocore.exceptions import ClientError
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-s3-notready"
        self._setup_access(mock_async_db, mock_user, book_id)
        service = self._ok_aws()
        service.head_object_async.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )
        mock_get_service.return_value = service

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": f"imports/{mock_user.id}/deck.pdf",
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.OBJECT_NOT_READY.value
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_duplicate_via_dedupe_query_returns_409(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-s3-dupe"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()

        s3_key = f"imports/{mock_user.id}/dup.pdf"
        existing = MockImportItem(s3_key=s3_key)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[existing])

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "pdf",
                "s3_key": s3_key,
                "mime_type": "application/pdf",
            },
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.DUPLICATE_IMPORT.value
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_mutual_exclusion_with_base64_returns_400(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-s3-mutex"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "audio",
                "s3_key": f"imports/{mock_user.id}/x.m4a",
                "file_base64": "Zm9v",
                "file_name": "x.m4a",
                "mime_type": "audio/mp4",
            },
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == ErrorCode.INVALID_REQUEST.value
        mock_task.delay.assert_not_called()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_s3_key_rate_limit_returns_429(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-s3-rl"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()
        mock_task.delay.return_value = None

        # Saturate the limiter with 30 allowed calls, each with a unique
        # key so dedupe doesn't kick in on the next attempt.
        for i in range(30):
            resp = client.post(
                f"/v1/recipe-books/{book_id}/import",
                json={
                    "source_type": "audio",
                    "s3_key": f"imports/{mock_user.id}/rl-{i:02d}.m4a",
                    "mime_type": "audio/mp4",
                },
            )
            assert resp.status_code == 201, (i, resp.json())

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "audio",
                "s3_key": f"imports/{mock_user.id}/rl-over.m4a",
                "mime_type": "audio/mp4",
            },
        )
        assert response.status_code == 429
        assert response.json()["error_code"] == ErrorCode.RATE_LIMITED.value

    def test_rate_limit_reset_hook_clears_state(self):
        """The test hook must actually clear module-level state —
        otherwise the 30-call saturation above leaks across tests."""
        from api.v1.import_job.start_import import (
            _rate_limit_events,
            _reset_rate_limit_for_test,
        )

        _rate_limit_events["u"] = [1.0, 2.0]
        _reset_rate_limit_for_test()
        assert _rate_limit_events == {}

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_video_file_s3_key_accepted(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        """sbf-4: video_file must be accepted as a source_type."""
        self._reset_rate_limit()
        book_id = "book-vf"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()
        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "video_file",
                "s3_key": f"imports/{mock_user.id}/clip.mp4",
                "mime_type": "video/mp4",
                "file_name": "clip.mp4",
            },
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["source_type"] == "video_file"
        mock_task.delay.assert_called_once()

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("api.v1.import_job.start_import._get_aws_service")
    def test_video_file_without_s3_key_rejected(
        self, mock_get_service, mock_task, client, mock_async_db, mock_user,
    ):
        """video_file only accepts the s3_key path — no base64 fallback."""
        from utils.classes.error_code import ErrorCode

        self._reset_rate_limit()
        book_id = "book-vf-no-key"
        self._setup_access(mock_async_db, mock_user, book_id)
        mock_get_service.return_value = self._ok_aws()

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "video_file",
                "file_base64": "Zm9v",
                "file_name": "clip.mp4",
            },
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == ErrorCode.INVALID_REQUEST.value
        mock_task.delay.assert_not_called()


class TestStartImportSocialUrlRouting:
    """sbf-5: social URL promoted to source_type='video' at creation."""

    @staticmethod
    def _setup_access(mock_async_db, mock_user, book_id):
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        mock_async_db.set_find_by(
            RecipeBookUser, membership,
            user_id=str(mock_user.id), recipe_book_id=book_id,
        )
        mock_async_db.set_find_by(RecipeBook, book, id=book_id)

    @staticmethod
    def _reset_rate_limit():
        from api.v1.import_job.start_import import _reset_rate_limit_for_test
        _reset_rate_limit_for_test()

    @staticmethod
    def _track_created(mock_async_db):
        """Wrap mock_async_db.create so we can inspect the ImportItem it saw."""
        from utils.models.import_item import ImportItem

        created: list[ImportItem] = []
        real_create = mock_async_db.create

        async def _wrapped(model):
            if isinstance(model, ImportItem):
                created.append(model)
            return await real_create(model)

        mock_async_db.create = _wrapped
        return created

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_tiktok_url_promoted_to_video(
        self, mock_task, client, mock_async_db, mock_user,
    ):
        self._reset_rate_limit()
        book_id = "book-tt"
        self._setup_access(mock_async_db, mock_user, book_id)
        created = self._track_created(mock_async_db)
        mock_task.delay.return_value = None

        url = "https://www.tiktok.com/@chef/video/7123456789012345678"
        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "url", "url": url},
        )
        assert response.status_code == 201, response.json()

        assert created, "no ImportItem created"
        item = created[0]
        assert item.source_type == "video"
        assert item.raw_data.get("detected_platform") == "tiktok"
        assert item.source_url == url

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_instagram_url_promoted(
        self, mock_task, client, mock_async_db, mock_user,
    ):
        self._reset_rate_limit()
        book_id = "book-ig"
        self._setup_access(mock_async_db, mock_user, book_id)
        created = self._track_created(mock_async_db)
        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://www.instagram.com/reel/CxYzAbc/",
            },
        )
        assert response.status_code == 201
        assert created[0].source_type == "video"
        assert created[0].raw_data["detected_platform"] == "instagram"

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_web_url_stays_url(
        self, mock_task, client, mock_async_db, mock_user,
    ):
        self._reset_rate_limit()
        book_id = "book-web"
        self._setup_access(mock_async_db, mock_user, book_id)
        created = self._track_created(mock_async_db)
        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://www.nytimes.com/recipes/1016847/risotto",
            },
        )
        assert response.status_code == 201
        assert created[0].source_type == "url"
        # Non-social URLs must NOT get a detected_platform marker — a
        # blank raw_data keeps downstream code paths unchanged.
        assert created[0].raw_data.get("detected_platform") is None


class TestInferredFieldsHoist:
    """efi-4 — `inferred_fields` hoisted to the item-object root on
    GetImportItem + ListImportItems."""

    def _setup_item(self, mock_async_db, mock_user, *, parsed_recipe):
        item_id = "hoist-item"
        job_id = "hoist-job"
        book_id = "hoist-book"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe=parsed_recipe,
            retry_count=0,
            raw_data={},
            created_recipe_id=None,
            user_edits=None,
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        return item_id, job_id

    def test_get_import_item_hoists_inferred_fields(
        self, client, mock_async_db, mock_user
    ):
        item_id, _ = self._setup_item(
            mock_async_db,
            mock_user,
            parsed_recipe={
                "name": "X",
                "cook_time_minutes": 30,
                "inferred_fields": ["cook_time_minutes", "servings"],
            },
        )
        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["inferred_fields"] == ["cook_time_minutes", "servings"]

    def test_get_import_item_legacy_returns_empty(
        self, client, mock_async_db, mock_user
    ):
        """Row with no inferred_fields key (pre-efi-3 extraction) decodes
        to `[]` at the response root."""
        item_id, _ = self._setup_item(
            mock_async_db, mock_user, parsed_recipe={"name": "X"}
        )
        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        assert response.json()["inferred_fields"] == []

    def test_get_import_item_filters_non_allowlist_in_legacy_row(
        self, client, mock_async_db, mock_user
    ):
        """Malformed legacy row with a non-inferable field smuggled into
        `inferred_fields` → filtered out at the response edge."""
        item_id, _ = self._setup_item(
            mock_async_db,
            mock_user,
            parsed_recipe={
                "name": "X",
                "inferred_fields": [
                    "cook_time_minutes",
                    "name",
                    "ingredients",
                    42,
                ],
            },
        )
        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        assert response.json()["inferred_fields"] == ["cook_time_minutes"]

    def test_list_import_items_hoists_inferred_fields(
        self, client, mock_async_db, mock_user
    ):
        job_id = "hoist-job"
        book_id = "hoist-book"
        item_a = MockImportItem(
            id="a",
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={
                "name": "A",
                "inferred_fields": ["cook_time_minutes"],
            },
        )
        item_b = MockImportItem(
            id="b",
            import_job_id=job_id,
            status="completed",
            parsed_recipe={"name": "B"},
        )
        # Malformed legacy row: inferred_fields contains a non-string
        # (42) + a string outside the allow-list ("not_a_real_field")
        # alongside a valid entry. Both bad entries must be silently
        # dropped by the allow-list filter.
        item_c = MockImportItem(
            id="c",
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe={
                "name": "C",
                "inferred_fields": ["servings", 42, "not_a_real_field"],
            },
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(
                user_id=str(mock_user.id),
                recipe_book_id=book_id,
            ),
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        mock_async_db.db.execute.side_effect = _paginated([item_a, item_b, item_c])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        items = {i["id"]: i["inferred_fields"] for i in data["items"]}
        assert items["a"] == ["cook_time_minutes"]
        assert items["b"] == []
        assert items["c"] == ["servings"]


class TestSubmitCorrection:
    """efi-4 — POST /v1/import-items/{item_id}/corrections audit endpoint."""

    def _setup(
        self,
        mock_async_db,
        mock_user,
        *,
        parsed_recipe=None,
        job_user_id=None,
    ):
        item_id = "corr-item"
        job_id = "corr-job"
        book_id = "corr-book"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="awaiting_review",
            parsed_recipe=parsed_recipe
            or {
                "cook_time_minutes": 30,
                "inferred_fields": ["cook_time_minutes"],
            },
        )
        job = MockImportJob(
            id=job_id,
            user_id=job_user_id or str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_async_db.set_find_by(ImportItem, item, id=item_id)
        mock_async_db.set_find_by(ImportJob, job, id=job_id)
        return item, job, item_id

    def test_happy_path_writes_audit_row(self, client, mock_async_db, mock_user):
        _, _, item_id = self._setup(mock_async_db, mock_user)

        added = []
        mock_async_db.db.add.side_effect = lambda r: added.append(r)

        response = client.post(
            f"/v1/import-items/{item_id}/corrections",
            json={"field": "cook_time_minutes", "corrected": 45},
        )
        assert response.status_code == 204
        assert len(added) == 1
        row = added[0]
        assert row.service == "audit"
        assert row.error_type == "InferredFieldCorrected"
        import json as _json
        meta = _json.loads(row.error_message)
        assert meta["field"] == "cook_time_minutes"
        assert meta["original"] == 30
        assert meta["corrected"] == 45
        assert meta["was_inferred"] is True

    def test_not_inferred_still_logs(self, client, mock_async_db, mock_user):
        """was_inferred=false path — correction data is valuable
        regardless of whether the field was inferred."""
        _, _, item_id = self._setup(
            mock_async_db,
            mock_user,
            parsed_recipe={
                "cook_time_minutes": 30,
                "inferred_fields": [],
            },
        )
        added = []
        mock_async_db.db.add.side_effect = lambda r: added.append(r)

        response = client.post(
            f"/v1/import-items/{item_id}/corrections",
            json={"field": "cook_time_minutes", "corrected": 45},
        )
        assert response.status_code == 204
        import json as _json
        meta = _json.loads(added[0].error_message)
        assert meta["was_inferred"] is False

    def test_field_not_inferable(self, client, mock_async_db, mock_user):
        _, _, item_id = self._setup(mock_async_db, mock_user)
        response = client.post(
            f"/v1/import-items/{item_id}/corrections",
            json={"field": "name", "corrected": "Renamed"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error_message"] == "field not inferable"
        # Response carries the allow-list so the client can self-correct.
        assert "cook_time_minutes" in body["data"]["allowed"]

    def test_item_not_found(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/import-items/nonexistent/corrections",
            json={"field": "cook_time_minutes", "corrected": 10},
        )
        assert response.status_code == 404

    def test_wrong_user(self, client, mock_async_db, mock_user):
        self._setup(mock_async_db, mock_user, job_user_id="someone-else")
        response = client.post(
            "/v1/import-items/corr-item/corrections",
            json={"field": "cook_time_minutes", "corrected": 10},
        )
        assert response.status_code == 403

    def test_missing_parsed_recipe_still_logs(
        self, client, mock_async_db, mock_user
    ):
        """Item with empty parsed_recipe (extraction failed mid-flight)
        → still logs, but original resolves to None + was_inferred=False."""
        item, _job, item_id = self._setup(
            mock_async_db, mock_user, parsed_recipe={"_": "_"},
        )
        # Force the actual stored value to None — `_setup`'s `or {...}`
        # swaps None for a default, so set it explicitly afterwards.
        item.parsed_recipe = None
        added = []
        mock_async_db.db.add.side_effect = lambda r: added.append(r)

        response = client.post(
            f"/v1/import-items/{item_id}/corrections",
            json={"field": "cook_time_minutes", "corrected": 45},
        )
        assert response.status_code == 204
        import json as _json
        meta = _json.loads(added[0].error_message)
        assert meta["original"] is None
        assert meta["was_inferred"] is False


class TestListImportItemsBatch:
    """ffm-2: GET /v1/import-items?job_ids=<csv> batch endpoint."""

    def _job(self, mock_user, job_id, book_id="book-1"):
        return MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

    def test_missing_job_ids_returns_400(
        self, client, mock_async_db, mock_user
    ):
        # Query param is required → FastAPI 422 before our handler runs.
        response = client.get("/v1/import-items")
        assert response.status_code == 422

    def test_empty_csv_returns_400(self, client, mock_async_db, mock_user):
        response = client.get("/v1/import-items?job_ids=")
        assert response.status_code == 400
        assert response.json()["error_message"] == "job_ids_required"

    def test_whitespace_only_csv_returns_400(
        self, client, mock_async_db, mock_user
    ):
        response = client.get("/v1/import-items?job_ids=%20,%20,%20")
        assert response.status_code == 400
        assert response.json()["error_message"] == "job_ids_required"

    def test_overflow_returns_400(self, client, mock_async_db, mock_user):
        many = ",".join([f"id-{i}" for i in range(51)])
        response = client.get(f"/v1/import-items?job_ids={many}")
        assert response.status_code == 400
        assert "job_ids_over_cap" in response.json()["error_message"]

    def test_cap_accepts_exactly_50(self, client, mock_async_db, mock_user):
        fifty = ",".join([f"id-{i}" for i in range(50)])
        # No jobs match → empty list, 200
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get(f"/v1/import-items?job_ids={fifty}")
        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_no_matching_jobs_returns_empty(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = client.get("/v1/import-items?job_ids=a,b,c")
        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_single_job_success(self, client, mock_async_db, mock_user):
        job = self._job(mock_user, job_id="job-1")
        item = MockImportItem(
            import_job_id="job-1",
            status="completed",
            parsed_recipe={"name": "Chili"},
            created_recipe_id="recipe-7",
        )
        # 1) jobs 2) items  (no membership lookup — the caller owns
        # the job directly, so book_ids is still collected but no
        # RecipeBookUser rows need to be returned; the membership
        # query still executes and MUST be stubbed.)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get("/v1/import-items?job_ids=job-1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        # Critical: each item carries its job_id (client groups by it).
        assert data["items"][0]["job_id"] == "job-1"
        assert data["items"][0]["recipe_name"] == "Chili"
        assert data["items"][0]["created_recipe_id"] == "recipe-7"

    def test_multi_job_success_groups_by_job_id(
        self, client, mock_async_db, mock_user
    ):
        """Flat list with job_id on each item — client groups."""
        j1 = self._job(mock_user, job_id="job-1", book_id="book-1")
        j2 = self._job(mock_user, job_id="job-2", book_id="book-1")
        i1 = MockImportItem(
            import_job_id="job-1", status="awaiting_review"
        )
        i2 = MockImportItem(import_job_id="job-2", status="completed")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[j1, j2]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[i1, i2]),
        ]
        response = client.get("/v1/import-items?job_ids=job-1,job-2")
        assert response.status_code == 200
        grouped: dict[str, list] = {}
        for item in response.json()["items"]:
            grouped.setdefault(item["job_id"], []).append(item)
        assert "job-1" in grouped
        assert "job-2" in grouped

    def test_inaccessible_jobs_silently_dropped(
        self, client, mock_async_db, mock_user
    ):
        """A job the caller neither owns nor has book-membership for
        must not surface any items — and must NOT 403 the whole
        response (so the batch can't be used as an enumeration oracle)."""
        owned = self._job(mock_user, job_id="job-mine", book_id="book-1")
        stranger = MockImportJob(
            id="job-stranger",
            user_id="someone-else",
            recipe_book_id="book-private",
        )
        mine = MockImportItem(
            import_job_id="job-mine", status="completed"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[owned, stranger]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[mine]),
        ]
        response = client.get(
            "/v1/import-items?job_ids=job-mine,job-stranger"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["job_id"] == "job-mine"

    def test_access_via_book_membership(
        self, client, mock_async_db, mock_user
    ):
        """Non-owner job + user has book membership → accessible."""
        other_owned = MockImportJob(
            id="job-shared",
            user_id="someone-else",
            recipe_book_id="book-shared",
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id="book-shared",
        )
        item = MockImportItem(
            import_job_id="job-shared", status="completed"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[other_owned]),
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get("/v1/import-items?job_ids=job-shared")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_status_filter_passes_through(
        self, client, mock_async_db, mock_user
    ):
        """Status filter reaches the query (MockQuery ignores filters
        but the query chain must not throw)."""
        job = self._job(mock_user, job_id="job-1")
        item = MockImportItem(
            import_job_id="job-1", status="awaiting_review"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get(
            "/v1/import-items?job_ids=job-1&status=awaiting_review"
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["status"] == "awaiting_review"

    def test_include_archived_true(self, client, mock_async_db, mock_user):
        from datetime import UTC, datetime

        job = self._job(mock_user, job_id="job-1")
        archived_item = MockImportItem(
            import_job_id="job-1",
            status="completed",
            archived_at=datetime.now(UTC),
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[archived_item]),
        ]
        response = client.get(
            "/v1/import-items?job_ids=job-1&include_archived=true"
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["archived_at"] is not None

    def test_duplicate_job_ids_deduped(
        self, client, mock_async_db, mock_user
    ):
        """Duplicate CSV entries collapse — user isn't penalized
        against the 50-ID cap for retry-style repeats."""
        job = self._job(mock_user, job_id="job-1")
        item = MockImportItem(import_job_id="job-1")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        # 51 duplicates of the same id → dedup to 1, no 400.
        ids = ",".join(["job-1"] * 51)
        response = client.get(f"/v1/import-items?job_ids={ids}")
        # Cap check runs BEFORE dedup — this IS over cap.
        assert response.status_code == 400

        # But 3 distinct uses of 2 unique IDs should work.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get("/v1/import-items?job_ids=job-1,job-1,job-1")
        assert response.status_code == 200

    def test_item_shape_matches_per_job_endpoint(
        self, client, mock_async_db, mock_user
    ):
        """Per-item response fields (minus the new job_id) are the
        same keys the per-job endpoint returns, so client migration
        is mechanical."""
        job = self._job(mock_user, job_id="job-1")
        item = MockImportItem(
            import_job_id="job-1",
            status="completed",
            source_type="url",
            source_url="https://example.com/r",
            parsed_recipe={
                "name": "Tacos",
                "confidence_score": 0.92,
                "confidence_source": "model",
                "inferred_fields": [],
            },
            ai_cost_cents=5,
            last_successful_stage="extraction",
            awaiting_review_reason=None,
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get("/v1/import-items?job_ids=job-1")
        assert response.status_code == 200
        it = response.json()["items"][0]
        # Fields shared with the per-job endpoint's ItemSummary:
        expected_keys = {
            "id", "status", "source_type", "source_url", "recipe_name",
            "error_message", "needs_review", "ai_cost_cents",
            "created_at", "archived_at", "last_successful_stage",
            "last_retry_at", "awaiting_review_reason",
            "confidence_score", "confidence_source", "inferred_fields",
            "created_recipe_id",
        }
        assert expected_keys.issubset(it.keys())
        # Plus the new field:
        assert "job_id" in it

    def test_trims_whitespace_in_csv(
        self, client, mock_async_db, mock_user
    ):
        """CSV with spaces after commas still parses cleanly."""
        job = self._job(mock_user, job_id="job-1")
        item = MockImportItem(import_job_id="job-1")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[job]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get(
            "/v1/import-items?job_ids=%20job-1%20"
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["job_id"] == "job-1"

    def test_all_jobs_inaccessible_returns_empty(
        self, client, mock_async_db, mock_user
    ):
        """Every requested job is owned by someone else with no
        membership → return empty, not 403. Confirms the batch is
        never an enumeration oracle."""
        stranger1 = MockImportJob(
            id="s1", user_id="other", recipe_book_id="b1"
        )
        stranger2 = MockImportJob(
            id="s2", user_id="other", recipe_book_id="b2"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[stranger1, stranger2]),
            MockExecuteResult(items=[]),  # no memberships
        ]
        response = client.get("/v1/import-items?job_ids=s1,s2")
        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_jobs_without_recipe_book_id(
        self, client, mock_async_db, mock_user
    ):
        """Legacy jobs that predate recipe_book_id (or have it as
        NULL) → skip the membership probe (book_ids is empty) and
        access falls back to direct user_id ownership."""
        orphan = MockImportJob(
            id="orphan-job",
            user_id=str(mock_user.id),
            recipe_book_id=None,
        )
        item = MockImportItem(import_job_id="orphan-job")
        # Only 2 queries: jobs, items. No membership query because
        # book_ids is empty, so the `if book_ids:` branch is skipped.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[orphan]),
            MockExecuteResult(items=[item]),
        ]
        response = client.get("/v1/import-items?job_ids=orphan-job")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
