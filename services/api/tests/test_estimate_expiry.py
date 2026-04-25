"""Tests for POST /pantries/{id}/estimate-expiry (pantry-6).

aam-15: EstimateExpiry is now an AsyncEndpoint that uses
`require_pantry_access_async`. Switch from mock_db to mock_async_db
and feed PantryUser membership through `mock_async_db.db.execute`
(the helper does `select(PantryUser)... .scalars().first()`).
"""

import uuid

from conftest import (
    MockExecuteResult,
    MockIngredient,
    MockPantry,
    MockPantryUser,
)


class TestEstimateExpiry:
    def test_happy_path_returns_datetime(self, client, mock_async_db, mock_user):
        from utils.models.ingredient import Ingredient
        from utils.models.pantry import Pantry

        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(mock_user.id), pantry_id=str(pantry.id))
        ingredient = MockIngredient(canonical_name="eggs")

        mock_async_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        mock_async_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))
        mock_async_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(ingredient.id),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 200
        assert response.json()["expires_at"] is not None

    def test_unknown_storage_returns_422(self, client, mock_async_db, mock_user):
        pantry_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "garage",
            },
        )
        assert response.status_code == 422

    def test_missing_pantry_access_returns_403(self, client, mock_async_db, mock_user):
        from utils.models.pantry import Pantry

        pantry = MockPantry()
        mock_async_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        # require_pantry_access_async: PantryUser membership absent → 403.
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 403

    def test_unknown_ingredient_returns_404(self, client, mock_async_db, mock_user):
        from utils.models.pantry import Pantry

        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(mock_user.id), pantry_id=str(pantry.id))
        mock_async_db.set_find_by(Pantry, pantry, id=str(pantry.id))
        mock_async_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            f"/v1/pantries/{pantry.id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 404
