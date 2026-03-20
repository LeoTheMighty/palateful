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

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_syncs_pending_status(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that pending job with batch_job_id triggers status sync from AWS Batch."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-456",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {"status": "RUNNING"}
        mock_aws.map_batch_status_to_parser_status.return_value = "running"

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        mock_aws.describe_batch_job.assert_called_once_with("batch-456")

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_syncs_succeeded_fetches_s3(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that succeeded batch status triggers S3 result fetch."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-789",
            output_s3_key="results/test.json",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {"status": "SUCCEEDED"}
        mock_aws.map_batch_status_to_parser_status.return_value = "succeeded"
        mock_aws.get_s3_object.return_value = {"extracted_markdown": "# Recipe\nStep 1"}

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"
        assert data["extracted_text"] == "# Recipe\nStep 1"
        assert data["completed_at"] is not None
        mock_aws.get_s3_object.assert_called_once_with("results/test.json")

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_syncs_succeeded_s3_failure(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that S3 fetch failure marks job as failed."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-101",
            output_s3_key="results/test.json",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {"status": "SUCCEEDED"}
        mock_aws.map_batch_status_to_parser_status.return_value = "succeeded"
        mock_aws.get_s3_object.side_effect = Exception("S3 bucket not found")

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "Failed to fetch results" in data["error_message"]
        assert data["completed_at"] is not None

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_syncs_failed_captures_reason(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that failed batch status captures status reason."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-fail",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {
            "status": "FAILED",
            "statusReason": "Container exited with code 1",
        }
        mock_aws.map_batch_status_to_parser_status.return_value = "failed"

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Container exited with code 1"
        assert data["completed_at"] is not None

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_syncs_failed_no_reason(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that failed batch status without statusReason uses default message."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-fail2",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {"status": "FAILED"}
        mock_aws.map_batch_status_to_parser_status.return_value = "failed"

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Unknown error"

    def test_get_parser_job_already_succeeded_no_sync(self, client, mock_db, mock_user):
        """Test that already-succeeded job does not trigger sync."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="succeeded",
            batch_job_id="batch-old",
            extracted_text="Some text",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"
        assert data["extracted_text"] == "Some text"

    def test_get_parser_job_already_failed_no_sync(self, client, mock_db, mock_user):
        """Test that already-failed job does not trigger sync."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="failed",
            batch_job_id="batch-old",
            error_message="Previous error",
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Previous error"

    def test_get_parser_job_pending_no_batch_job_id_no_sync(self, client, mock_db, mock_user):
        """Test that pending job without batch_job_id does not trigger sync."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="pending",
            batch_job_id=None,
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    @patch("api.v1.parser.get_parser_job.AWSService")
    def test_get_parser_job_succeeded_no_output_key(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that succeeded batch status with no output_s3_key skips S3 fetch."""
        job_id = "test-job-id"
        job = MockParserJob(
            id=job_id,
            user_id=str(mock_user.id),
            status="submitted",
            batch_job_id="batch-noout",
            output_s3_key=None,
        )

        from utils.models.parser_job import ParserJob

        mock_db.set_find_by(ParserJob, job, id=job_id)

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.describe_batch_job.return_value = {"status": "SUCCEEDED"}
        mock_aws.map_batch_status_to_parser_status.return_value = "succeeded"

        response = client.get(f"/v1/parser/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"
        # S3 object should NOT have been fetched since output_s3_key is None
        mock_aws.get_s3_object.assert_not_called()


class TestSubmitBatchParserJob:
    """Tests for POST /v1/parser/jobs/batch."""

    @patch("api.v1.parser.submit_batch_parser_job.AWSService")
    def test_submit_batch_success(self, mock_aws_cls, client, mock_db, mock_user):
        """Test submitting a batch parser job with multiple images."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job.return_value = "batch-multi-123"

        response = client.post(
            "/v1/parser/jobs/batch",
            json={"s3_keys": ["uploads/img1.jpg", "uploads/img2.jpg"]}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["batch_job_id"] == "batch-multi-123"
        assert len(data["jobs"]) == 2
        assert data["jobs"][0]["input_s3_key"] == "uploads/img1.jpg"
        assert data["jobs"][1]["input_s3_key"] == "uploads/img2.jpg"
        # Each job should have a unique ID
        assert data["jobs"][0]["id"] != data["jobs"][1]["id"]

    @patch("api.v1.parser.submit_batch_parser_job.AWSService")
    def test_submit_batch_single_image(self, mock_aws_cls, client, mock_db, mock_user):
        """Test submitting a batch parser job with a single image."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job.return_value = "batch-single-456"

        response = client.post(
            "/v1/parser/jobs/batch",
            json={"s3_keys": ["uploads/single.jpg"]}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["batch_job_id"] == "batch-single-456"
        assert len(data["jobs"]) == 1

    @patch("api.v1.parser.submit_batch_parser_job.AWSService")
    def test_submit_batch_aws_service_called_with_manifest(self, mock_aws_cls, client, mock_db, mock_user):
        """Test that AWS service is called with correct manifest structure."""
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws
        mock_aws.submit_batch_manifest_job.return_value = "batch-789"

        response = client.post(
            "/v1/parser/jobs/batch",
            json={"s3_keys": ["uploads/a.jpg", "uploads/b.jpg"]}
        )
        assert response.status_code == 201

        # Verify submit_batch_manifest_job was called
        mock_aws.submit_batch_manifest_job.assert_called_once()
        call_kwargs = mock_aws.submit_batch_manifest_job.call_args
        # Check items have input/output keys
        items = call_kwargs.kwargs.get("items") or call_kwargs[1].get("items") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        if items is None:
            # Try positional args
            items = call_kwargs.kwargs.get("items")
        if items is not None:
            assert len(items) == 2
            assert items[0]["input_s3_key"] == "uploads/a.jpg"
            assert items[1]["input_s3_key"] == "uploads/b.jpg"

    def test_submit_batch_missing_s3_keys(self, client, mock_db, mock_user):
        """Test that missing s3_keys field returns 422."""
        response = client.post(
            "/v1/parser/jobs/batch",
            json={}
        )
        assert response.status_code == 422
