"""Tests for POST /v1/meals/{meal_id}/share (msa-1)."""

import re
from datetime import UTC, datetime

from conftest import (
    MockModel,
    MockQuery,
    MockRecipeBookUser,
)


class _MockMeal(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "id": "meal-1",
            "name": "Kale Salad Meal",
            "description": None,
            "recipe_book_id": "book-1",
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _owner():
    return MockRecipeBookUser(role="owner")


def _editor():
    return MockRecipeBookUser(role="editor")


def _viewer():
    return MockRecipeBookUser(role="viewer")


class TestShareMealFirstTime:
    """POST /v1/meals/{id}/share with no existing token → 201 + new token."""

    def test_happy_generates_token(self, client, mock_db, mock_user):
        meal = _MockMeal(share_token=None)
        # Query order: 1) get_with_components 2) user_has_book_write
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 201
        data = response.json()
        # `secrets.token_urlsafe(15)` emits 20 URL-safe chars.
        assert re.fullmatch(r"[A-Za-z0-9_-]{20}", data["token"]) is not None
        assert data["deep_link"] == f"palateful://meal-public/{data['token']}"
        assert meal.share_token == data["token"]

    def test_editor_can_share(self, client, mock_db, mock_user):
        meal = _MockMeal(share_token=None)
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_editor()]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 201


class TestShareMealIdempotent:
    """Re-sharing returns the existing token with 200 (no rotation)."""

    def test_returns_same_token_with_200(self, client, mock_db, mock_user):
        existing = "abcd" * 5  # 20 chars
        meal = _MockMeal(share_token=existing)
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == existing
        assert data["deep_link"] == f"palateful://meal-public/{existing}"
        # Token is NOT rotated.
        assert meal.share_token == existing


class TestShareMealAuth:
    """Permission + not-found paths."""

    def test_viewer_403(self, client, mock_db, mock_user):
        meal = _MockMeal()
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_viewer()]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 403

    def test_non_member_403(self, client, mock_db, mock_user):
        meal = _MockMeal()
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 403

    def test_missing_meal_404(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.post("/v1/meals/nope/share")
        assert response.status_code == 404

    def test_archived_meal_404(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=datetime.now(UTC))
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/share")
        assert response.status_code == 404
