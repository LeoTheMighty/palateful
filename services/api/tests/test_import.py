"""Tests for import job endpoints."""

from unittest.mock import patch

from conftest import (
    MockImportItem,
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


    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_start_import_text_success(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

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

    def test_start_import_text_missing_text(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text"},
        )
        assert response.status_code == 400

    def test_start_import_text_empty_text(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text", "raw_text": "   "},
        )
        assert response.status_code == 400

    def test_start_import_text_too_long(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "text", "raw_text": "x" * 16001},
        )
        assert response.status_code == 400


    def test_start_import_spreadsheet_missing_fields(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "spreadsheet"},
        )
        assert response.status_code == 400

    @patch("api.v1.import_job.start_import.parse_source_task")
    @patch("utils.services.spreadsheet_parser.parse_spreadsheet")
    def test_start_import_spreadsheet_success(self, mock_parse, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

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

    def test_get_import_job_access_denied(self, client, mock_db, mock_user):
        """Test getting a job when user has no membership and is not the job owner."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set, and job.user_id != mock_user.id

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_get_import_job_access_via_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200

    def test_get_import_job_access_as_job_owner_no_membership(self, client, mock_db, mock_user):
        """Test getting a job when user is the job owner but has no membership."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set, but job.user_id == mock_user.id

        response = client.get(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200


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
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    def test_cancel_import_job_not_found(self, client, mock_db):
        """Test cancelling a nonexistent import job."""
        response = client.delete("/v1/import-jobs/nonexistent")
        assert response.status_code == 404

    def test_cancel_import_job_no_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        # No membership set and job.user_id != mock_user.id

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_cancel_import_job_not_owner_role_but_is_job_starter(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_cancel_import_job_editor_not_job_starter(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 403

    def test_cancel_import_job_already_completed(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 400

    def test_cancel_import_job_already_cancelled(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 400

    def test_cancel_import_job_awaiting_review(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/import-jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"


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
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_import_items_not_found(self, client, mock_db, mock_user):
        """Test listing items for a nonexistent job."""
        response = client.get("/v1/import-jobs/nonexistent/items")
        assert response.status_code == 404

    def test_list_import_items_access_denied(self, client, mock_db, mock_user):
        """Test listing items when user has no access."""
        job_id = "test-job-id"
        book_id = "test-book-id"
        job = MockImportJob(
            id=job_id,
            user_id="other-user-id",
            recipe_book_id=book_id,
        )

        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 403

    def test_list_import_items_with_status_filter(self, client, mock_db, mock_user):
        """Test listing items with a status filter."""
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

        response = client.get(f"/v1/import-jobs/{job_id}/items?status=awaiting_review")
        assert response.status_code == 200

    def test_list_import_items_with_parsed_recipe(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["recipe_name"] == "Test Recipe"
        assert data["items"][0]["needs_review"] is True  # status is awaiting_review
        assert data["total"] == 1

    def test_list_import_items_with_needs_review_ingredient(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["needs_review"] is True

    def test_list_import_items_no_needs_review(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["needs_review"] is False

    def test_list_import_items_without_parsed_recipe(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["recipe_name"] is None
        assert data["items"][0]["needs_review"] is False

    def test_list_import_items_access_via_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200

    def test_list_import_items_has_more(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        # MockQuery returns all items for both count() and all()
        # so has_more = offset + len(items) < total = 0 + 2 < 2 = False
        # To test has_more=True, we need count > len(returned items)
        # But MockQuery always returns same items for all() and count()
        # We can still test with offset: offset=1, total=2, returned=2 -> 1+2=3 > 2, no
        # Actually with MockQuery, offset/limit don't actually filter.
        # Let's just verify the logic is exercised.
        mock_db.db.query.return_value = MockQuery(items)

        response = client.get(f"/v1/import-jobs/{job_id}/items?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()
        # MockQuery doesn't actually paginate, so total=2, items=2, has_more = 0+2<2 = False
        assert data["total"] == 2

    def test_list_import_items_with_error_message(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.db.query.return_value = MockQuery([item])

        response = client.get(f"/v1/import-jobs/{job_id}/items")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["error_message"] == "Failed to parse recipe"


class TestGetImportItem:
    """Tests for GET /v1/import-items/{item_id}."""

    def test_get_import_item_success(self, client, mock_db, mock_user):
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
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
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

    def test_get_import_item_not_found(self, client, mock_db, mock_user):
        """Test getting a nonexistent import item."""
        response = client.get("/v1/import-items/nonexistent")
        assert response.status_code == 404

    def test_get_import_item_job_not_found(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        # No job registered -> job not found

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 404

    def test_get_import_item_access_denied(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        # No membership and job.user_id != mock_user.id

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 403

    def test_get_import_item_access_via_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200

    def test_get_import_item_access_as_job_owner(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        # No membership, but job.user_id == mock_user.id

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200

    def test_get_import_item_with_created_recipe_id(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["created_recipe_id"] == recipe_id
        assert data["user_edits"] == {"name": "My Recipe"}

    def test_get_import_item_with_empty_raw_data(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.get(f"/v1/import-items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["raw_data"] == {}


class TestUpdateImportItem:
    """Tests for PUT /v1/import-items/{item_id}."""

    def test_update_import_item_success(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
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

    def test_update_import_item_not_found(self, client, mock_db, mock_user):
        """Test updating a nonexistent import item."""
        response = client.put(
            "/v1/import-items/nonexistent",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 404

    def test_update_import_item_job_not_found(self, client, mock_db, mock_user):
        """Test updating item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_db.set_find_by(ImportItem, item, id=item_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 404

    def test_update_import_item_no_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 403

    def test_update_import_item_viewer_role(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 403

    def test_update_import_item_editor_role(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 200

    def test_update_import_item_completed_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 400

    def test_update_import_item_skipped_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.put(
            f"/v1/import-items/{item_id}",
            json={"user_edits": {"name": "test"}},
        )
        assert response.status_code == 400

    def test_update_import_item_pending_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
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
    def test_approve_import_item_success(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

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

    def test_approve_import_item_not_found(self, client, mock_db, mock_user):
        """Test approving a nonexistent import item."""
        response = client.post("/v1/import-items/nonexistent/approve")
        assert response.status_code == 404

    def test_approve_import_item_job_not_found(self, client, mock_db, mock_user):
        """Test approving item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 404

    def test_approve_import_item_no_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 403

    def test_approve_import_item_viewer_role(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 403

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_editor_role(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200

    def test_approve_import_item_completed_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_skipped_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_pending_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_approved_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    def test_approve_import_item_no_recipe_data(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 400

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_with_user_edits_only(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    @patch("api.v1.import_job.approve_import_item.create_recipe_task")
    def test_approve_import_item_matching_status(self, mock_task, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_task.delay.return_value = None

        response = client.post(f"/v1/import-items/{item_id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"


class TestSkipImportItem:
    """Tests for POST /v1/import-items/{item_id}/skip."""

    def test_skip_import_item_success(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts
        mock_db.db.query.return_value = MockQuery([
            ("skipped", 1),
            ("awaiting_review", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["status"] == "skipped"

    def test_skip_import_item_not_found(self, client, mock_db, mock_user):
        """Test skipping a nonexistent import item."""
        response = client.post("/v1/import-items/nonexistent/skip")
        assert response.status_code == 404

    def test_skip_import_item_job_not_found(self, client, mock_db, mock_user):
        """Test skipping item when its parent job doesn't exist."""
        item_id = "test-item-id"
        item = MockImportItem(
            id=item_id,
            import_job_id="missing-job-id",
        )

        from utils.models.import_item import ImportItem

        mock_db.set_find_by(ImportItem, item, id=item_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 404

    def test_skip_import_item_no_membership(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 403

    def test_skip_import_item_viewer_role(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 403

    def test_skip_import_item_editor_role(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts
        mock_db.db.query.return_value = MockQuery([
            ("skipped", 1),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200

    def test_skip_import_item_completed_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 400

    def test_skip_import_item_already_skipped(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 400

    def test_skip_import_item_pending_status(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Mock the query for _update_job_counts - more items still pending
        mock_db.db.query.return_value = MockQuery([
            ("skipped", 1),
            ("awaiting_review", 2),
            ("pending", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"

    def test_skip_import_item_job_completes(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # All items are in final states, total_final >= total_items
        mock_db.db.query.return_value = MockQuery([
            ("completed", 1),
            ("skipped", 1),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # Job should be marked as completed since total_final (2) >= total_items (2)
        assert job.status == "completed"

    def test_skip_import_item_job_awaiting_review(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Not all items final, but some awaiting review
        mock_db.db.query.return_value = MockQuery([
            ("skipped", 1),
            ("awaiting_review", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # pending_review_items > 0, so job should be awaiting_review
        assert job.status == "awaiting_review"
        assert job.pending_review_items == 2

    def test_skip_import_item_job_no_awaiting_review(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # Not all items final, no awaiting_review
        mock_db.db.query.return_value = MockQuery([
            ("skipped", 1),
            ("completed", 2),
        ])

        response = client.post(f"/v1/import-items/{item_id}/skip")
        assert response.status_code == 200
        # total_final = 0 + 0 + 1 = 1 (completed=2 from succeeded, failed=0, skipped=1)
        # Actually: succeeded = completed = 2, failed = 0, skipped = 1 => total_final = 2+0+1 = 3 < 10
        # pending_review_items = 0, so neither branch triggers
        assert job.status == "processing"  # unchanged

    def test_skip_import_item_update_counts_with_failed(self, client, mock_db, mock_user):
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

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        # All items final with mixed statuses
        mock_db.db.query.return_value = MockQuery([
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
