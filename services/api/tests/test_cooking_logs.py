"""Tests for cooking log endpoints."""

from conftest import MockQuery


class TestCookingLogs:
    """Tests for GET /v1/cooking-logs."""

    def test_list_cooking_logs_success(self, client, mock_db, mock_user):
        """Test listing cooking logs returns 200 with correct response shape."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_cooking_logs_with_limit(self, client, mock_db, mock_user):
        """Test that limit query param is accepted and returns 200."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/cooking-logs?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_cooking_logs_limit_too_high(self, client, mock_db, mock_user):
        """Test that limit above max (50) returns 422."""
        response = client.get("/v1/cooking-logs?limit=100")
        assert response.status_code == 422

    def test_list_cooking_logs_limit_too_low(self, client, mock_db, mock_user):
        """Test that limit below min (1) returns 422."""
        response = client.get("/v1/cooking-logs?limit=0")
        assert response.status_code == 422
