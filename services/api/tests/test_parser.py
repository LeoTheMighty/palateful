"""Tests for parser endpoints."""

from unittest.mock import MagicMock, patch

from conftest import MockParserJob


class TestGetUploadUrl:
    """Tests for POST /v1/parser/upload-url."""

    @patch("api.v1.parser.get_upload_url.AWSService")
    def test_get_upload_url_success(self, mock_aws_cls, client, mock_db, mock_user):
        """Test generating a presigned upload URL."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.generate_presigned_upload_url.return_value = "https://s3.example.com/presigned"

        response = client.post(
            "/v1/parser/upload-url",
            json={"filename": "recipe.jpg"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "s3_key" in data


class TestSubmitParserJob:
    """Tests for POST /v1/parser/jobs."""

    @patch("api.v1.parser.submit_parser_job.AWSService")
    def test_submit_parser_job_success(self, mock_aws_cls, client, mock_db, mock_user):
        """Test submitting a parser job."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_job.return_value = "batch-123"

        response = client.post(
            "/v1/parser/jobs",
            json={"s3_key": "uploads/test.jpg"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["batch_job_id"] == "batch-123"


class TestGetParserJob:
    """Tests for GET /v1/parser/jobs/{job_id}."""

    def test_get_parser_job_success(self, client, mock_db, mock_user):
        """Test getting a parser job."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="succeeded",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    def test_get_parser_job_not_found(self, client, mock_db, mock_user):
        """Test getting a nonexistent parser job."""
        response = client.get("/v1/parser/jobs/nonexistent")
        assert response.status_code == 404

    def test_get_parser_job_wrong_user(self, client, mock_db, mock_user):
        """Test getting another user's parser job."""
        job_id = "test-job-id"
        job = MockParserJob(id=job_id, user_id="other-user-id")

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 403
