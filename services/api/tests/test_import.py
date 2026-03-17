"""Tests for import job endpoints."""

from unittest.mock import patch

from conftest import (
    MockImportJob,
    MockQuery,
    MockRecipeBook,
    MockRecipeBookUser,
)


class TestStartImport:
    """Tests for POST /v1/recipe-books/{book_id}/import."""

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_success(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        mock_task.delay.return_value = None

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url",
                "url": "https://example.com/recipe",
            }
        )
        assert response.status_code == 201

    def test_start_import_no_access(self, client, mock_db, mock_user):
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
    def test_start_import_photo_success(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

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
    def test_start_import_url_list_success(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

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

    def test_start_import_url_list_empty(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "url_list",
                "urls": [],
            }
        )
        assert response.status_code == 400

    def test_start_import_photo_no_texts(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={
                "source_type": "photo",
                "ocr_texts": [],
            }
        )
        assert response.status_code == 400


class TestGetImportJob:
    """Tests for GET /v1/import-jobs/{job_id}."""

    def test_get_import_job_success(self, client, mock_db, mock_user):
        """Test getting an import job."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    def test_get_import_job_not_found(self, client, mock_db, mock_user):
        """Test getting a nonexistent import job."""
        response = client.get("/v1/import-jobs/nonexistent")
        assert response.status_code == 404


class TestCancelImportJob:
    """Tests for DELETE /v1/import-jobs/{job_id}."""

    def test_cancel_import_job_success(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200

    def test_cancel_import_job_not_found(self, client, mock_db):
        """Test cancelling a nonexistent import job."""
        response = client.delete("/v1/import-jobs/nonexistent")
        assert response.status_code == 404


class TestListImportItems:
    """Tests for GET /v1/import-jobs/{job_id}/items."""

    def test_list_import_items_success(self, client, mock_db, mock_user):
        """Test listing import items."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
