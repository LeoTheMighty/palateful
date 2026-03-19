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

    def test_search_by_tag(self, client, mock_db, mock_user):
        """Test searching by tag term returns 200 with expected response shape.

        Due to mock abstraction the tag-match SQL expression cannot be
        executed, but we verify: (a) the endpoint processes a tag-like query
        without errors, (b) all three result sections are present, and
        (c) the DB execute path was actually invoked (proving _recipe_matches
        and _search_users ran their query logic, not just returning early).
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        response = client.get("/v1/search?q=vegetarian")

        assert response.status_code == 200
        data = response.json()
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        # Verify DB was actually queried (not a no-op early return)
        assert mock_db.db.execute.call_count >= 1

    def test_search_fuzzy_returns_200(self, client, mock_db, mock_user):
        """Test that a misspelled query returns 200 and preserves the query string.

        The pg_trgm fuzzy tier is wrapped in try/except so the mock DB (which
        returns empty results for the text() SQL) exercises the degraded path
        successfully. Key assertions beyond test_search_success:
        - data["query"] must equal the original misspelled string (not autocorrected)
        - The fuzzy tier must not crash the endpoint even without real pg_trgm
        """
        mock_db.db.query.return_value = MockQuery([])
        mock_db.db.execute.return_value = MockExecuteResult([])
        mock_db.db.execute.reset_mock()

        # 'chiken' is an intentional typo — fuzzy tier should not crash
        response = client.get("/v1/search?q=chiken")

        assert response.status_code == 200
        data = response.json()
        # Verify original misspelled query is preserved in response (not autocorrected)
        assert data["query"] == "chiken"
        assert "my_recipes" in data
        assert "public_recipes" in data
        assert "users" in data
        assert mock_db.db.execute.call_count >= 1
