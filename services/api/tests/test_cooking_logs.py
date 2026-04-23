"""Tests for cooking log endpoints.

aam-21: handler converted to `AsyncEndpoint`; the query switched from
`db.query(CookingLog, Recipe)...` to `await db.execute(select(...))`.
Tests now stub `mock_async_db.db.execute.return_value =
MockExecuteResult(items=[...])` with tuple rows (CookingLog, Recipe).
"""

from datetime import UTC, datetime

from conftest import MockExecuteResult, MockModel, MockRecipe


class _MockCookingLog(MockModel):
    """Lightweight mock for CookingLog used only in this file."""

    def __init__(self, **kwargs):
        defaults = {
            "recipe_id": "r1",
            "cooked_at": datetime.now(UTC),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestCookingLogs:
    """Tests for GET /v1/cooking-logs."""

    def test_list_cooking_logs_success(self, client, mock_async_db, mock_user):
        """Test listing cooking logs returns 200 with correct response shape."""
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_cooking_logs_with_limit(self, client, mock_async_db, mock_user):
        """Test that limit query param is accepted and returns 200."""
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.get("/v1/cooking-logs?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_cooking_logs_limit_too_high(self, client, mock_async_db, mock_user):
        """Test that limit above max (50) returns 422."""
        response = client.get("/v1/cooking-logs?limit=100")
        assert response.status_code == 422

    def test_list_cooking_logs_limit_too_low(self, client, mock_async_db, mock_user):
        """Test that limit below min (1) returns 422."""
        response = client.get("/v1/cooking-logs?limit=0")
        assert response.status_code == 422

    def test_list_cooking_logs_with_results(self, client, mock_async_db, mock_user):
        """Test listing cooking logs with actual results."""
        recipe1 = MockRecipe(name="Pasta", image_url="https://img.com/pasta.jpg")
        log1 = _MockCookingLog(recipe_id=str(recipe1.id), cooked_at=datetime(2026, 1, 15, tzinfo=UTC))

        mock_async_db.db.execute.return_value = MockExecuteResult(
            items=[(log1, recipe1)]
        )

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["recipe_name"] == "Pasta"
        assert data["items"][0]["recipe_image_url"] == "https://img.com/pasta.jpg"

    def test_list_cooking_logs_deduplication(self, client, mock_async_db, mock_user):
        """Test that duplicate recipes are deduplicated (most recent kept)."""
        recipe1 = MockRecipe(name="Pasta")
        log1 = _MockCookingLog(recipe_id=str(recipe1.id), cooked_at=datetime(2026, 1, 15, tzinfo=UTC))
        log2 = _MockCookingLog(recipe_id=str(recipe1.id), cooked_at=datetime(2026, 1, 10, tzinfo=UTC))

        mock_async_db.db.execute.return_value = MockExecuteResult(
            items=[(log1, recipe1), (log2, recipe1)]
        )

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        # Duplicate recipe should be deduplicated to 1
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_cooking_logs_dedup_respects_limit(self, client, mock_async_db, mock_user):
        """Test that deduplication respects the limit parameter."""
        recipe1 = MockRecipe(name="Pasta")
        recipe2 = MockRecipe(name="Pizza")
        recipe3 = MockRecipe(name="Salad")

        log1 = _MockCookingLog(recipe_id=str(recipe1.id), cooked_at=datetime(2026, 1, 15, tzinfo=UTC))
        log2 = _MockCookingLog(recipe_id=str(recipe2.id), cooked_at=datetime(2026, 1, 14, tzinfo=UTC))
        log3 = _MockCookingLog(recipe_id=str(recipe3.id), cooked_at=datetime(2026, 1, 13, tzinfo=UTC))

        mock_async_db.db.execute.return_value = MockExecuteResult(
            items=[(log1, recipe1), (log2, recipe2), (log3, recipe3)]
        )

        # Limit=2, should only return 2 items
        response = client.get("/v1/cooking-logs?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_cooking_logs_multiple_distinct_recipes(self, client, mock_async_db, mock_user):
        """Test listing logs with multiple different recipes."""
        recipe1 = MockRecipe(name="Pasta")
        recipe2 = MockRecipe(name="Salad")

        log1 = _MockCookingLog(recipe_id=str(recipe1.id), cooked_at=datetime(2026, 1, 15, tzinfo=UTC))
        log2 = _MockCookingLog(recipe_id=str(recipe2.id), cooked_at=datetime(2026, 1, 14, tzinfo=UTC))

        mock_async_db.db.execute.return_value = MockExecuteResult(
            items=[(log1, recipe1), (log2, recipe2)]
        )

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = [item["recipe_name"] for item in data["items"]]
        assert "Pasta" in names
        assert "Salad" in names

    def test_list_cooking_logs_recipe_without_image(self, client, mock_async_db, mock_user):
        """Test that recipes without images return null image_url."""
        recipe = MockRecipe(name="Simple Recipe", image_url=None)
        log = _MockCookingLog(recipe_id=str(recipe.id))

        mock_async_db.db.execute.return_value = MockExecuteResult(
            items=[(log, recipe)]
        )

        response = client.get("/v1/cooking-logs")

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["recipe_image_url"] is None
