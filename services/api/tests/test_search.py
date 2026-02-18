"""Tests for search endpoints."""

from conftest import MockExecuteResult, MockQuery


class TestUnifiedSearch:
    """Tests for GET /v1/search."""

    def test_search_success(self, client, mock_db, mock_user):
        """Test searching."""
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/search?q=pasta")
        assert response.status_code == 200

    def test_search_short_query(self, client, mock_db, mock_user):
        """Test search with query shorter than min_length."""
        response = client.get("/v1/search?q=a")
        assert response.status_code == 422

    def test_search_missing_query(self, client, mock_db, mock_user):
        """Test search without query parameter."""
        response = client.get("/v1/search")
        assert response.status_code == 422
