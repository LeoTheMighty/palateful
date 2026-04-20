"""Tests for POST /pantries/{id}/estimate-expiry (pantry-6)."""

import uuid

from conftest import (
    MockIngredient,
    MockPantry,
    MockPantryUser,
    MockQuery,
)


def _query_router(mock_db, by_model: dict):
    def side_effect(model_class, *args, **kwargs):
        items = by_model.get(model_class)
        if items is None:
            return MockQuery([])
        return MockQuery(items if isinstance(items, list) else [items])
    mock_db.db.query.side_effect = side_effect


class TestEstimateExpiry:
    def test_happy_path_returns_datetime(self, client, mock_db, mock_user):
        from utils.models.ingredient import Ingredient
        from utils.models.pantry import Pantry
        from utils.models.pantry_user import PantryUser

        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(mock_user.id), pantry_id=str(pantry.id))
        ingredient = MockIngredient(canonical_name="eggs")

        mock_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        mock_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))
        _query_router(mock_db, {PantryUser: [membership]})

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(ingredient.id),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 200
        assert response.json()["expires_at"] is not None

    def test_unknown_storage_returns_422(self, client, mock_db, mock_user):
        pantry_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "garage",
            },
        )
        assert response.status_code == 422

    def test_missing_pantry_access_returns_403(self, client, mock_db, mock_user):
        from utils.models.pantry import Pantry
        from utils.models.pantry_user import PantryUser

        pantry = MockPantry()
        mock_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        _query_router(mock_db, {PantryUser: []})

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 403

    def test_unknown_ingredient_returns_404(self, client, mock_db, mock_user):
        from utils.models.pantry import Pantry
        from utils.models.pantry_user import PantryUser

        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(mock_user.id), pantry_id=str(pantry.id))
        mock_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        _query_router(mock_db, {PantryUser: [membership]})

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 404
