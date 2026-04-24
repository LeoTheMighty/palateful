"""Tests for pantry CRUD endpoints (aam-15 async rewrite).

All five handlers are `AsyncEndpoint` subclasses on `get_async_database`.
Tests drive them via the sync `client` fixture (async deps are already
overridden in conftest) and configure `mock_async_db` with either
`set_find_by` (for `await database.find_by(...)` lookups) or
`db.execute.side_effect` (for `await self.db.execute(select(...))`).

The call shape per endpoint (determines `execute.side_effect` sizing):

| Endpoint                | executes                         | find_by registry       |
| ----------------------- | -------------------------------- | ---------------------- |
| GetDefaultPantry        | 2 (existing) / 3 (lazy-create)   | Pantry                 |
| AddPantryIngredient     | 2 (access + upsert lookup)       | Pantry, Ingredient     |
| UpdatePantryIngredient  | 2 (access + row lookup)          | Pantry                 |
| DeletePantryIngredient  | 2 (access + row lookup)          | Pantry                 |
| EstimateExpiry          | 1 (access)                       | Pantry, Ingredient     |
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from conftest import (
    MockExecuteResult,
    MockIngredient,
    MockPantry,
    MockPantryIngredient,
    MockPantryUser,
)


class TestGetDefaultPantry:
    """Tests for GET /v1/pantries/default."""

    def test_lazy_creates_pantry_when_missing(self, client, mock_async_db, mock_user):
        """When the caller has no pantry, the endpoint creates one with role=owner."""
        # Executes:
        # 1. _find_default_membership_async → empty
        # 2. _find_default_membership_async (inside lock) → still empty
        # 3. list PantryIngredient → empty (fresh pantry)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[]),
        ]

        response = client.get("/v1/pantries/default")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "owner"
        assert data["name"] == "My Pantry"
        assert data["items"] == []

    def test_returns_existing_pantry_with_ingredients(
        self, client, mock_async_db, mock_user
    ):
        """Existing pantry is returned with non-archived ingredients."""
        from utils.models.pantry import Pantry

        pantry = MockPantry(id=str(uuid.uuid4()))
        membership = MockPantryUser(
            user_id=str(mock_user.id),
            pantry_id=str(pantry.id),
            role="owner",
        )
        ingredient = MockIngredient(canonical_name="flour")
        pi = MockPantryIngredient(
            pantry_id=str(pantry.id),
            ingredient_id=str(ingredient.id),
            ingredient=ingredient,
            quantity_display=Decimal("2.000"),
            unit_display="cups",
            quantity_normalized=Decimal("240.000"),
            unit_normalized="g",
        )

        mock_async_db.set_find_by(Pantry, pantry, id=pantry.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),  # membership lookup
            MockExecuteResult(items=[pi]),          # PantryIngredient list
        ]

        response = client.get("/v1/pantries/default")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(pantry.id)
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["ingredient_name"] == "flour"
        assert item["quantity_display"] == "2.000"


class TestAddPantryIngredient:
    """Tests for POST /v1/pantries/{pantry_id}/ingredients."""

    def _setup_access(self, mock_async_db, mock_user, pantry_id, *, role="owner"):
        from utils.models.pantry import Pantry

        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role=role
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)
        return pantry, membership

    def test_insert_new_pantry_ingredient(self, client, mock_async_db, mock_user):
        """Happy path: a new ingredient is inserted and 201 is returned."""
        from utils.models.ingredient import Ingredient

        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(mock_async_db, mock_user, pantry_id)
        ingredient = MockIngredient(canonical_name="onion")
        mock_async_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),  # require_pantry_access_async
            MockExecuteResult(items=[]),            # upsert existing lookup — none
        ]

        body = {
            "ingredient_id": str(ingredient.id),
            "quantity_display": "2.000",
            "unit_display": "each",
            "quantity_normalized": "2.000",
            "unit_normalized": "each",
            "storage_location": "pantry",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_id"] == str(ingredient.id)
        assert data["storage_location"] == "pantry"

    def test_upsert_sums_quantities(self, client, mock_async_db, mock_user):
        """If an active row exists, the normalized quantity is summed."""
        from utils.models.ingredient import Ingredient

        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(mock_async_db, mock_user, pantry_id)
        ingredient = MockIngredient(canonical_name="milk")
        mock_async_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))

        existing = MockPantryIngredient(
            pantry_id=pantry_id,
            ingredient_id=str(ingredient.id),
            quantity_normalized=Decimal("1.000"),
            unit_normalized="L",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[existing]),
        ]

        body = {
            "ingredient_id": str(ingredient.id),
            "quantity_display": "0.5",
            "unit_display": "liters",
            "quantity_normalized": "0.500",
            "unit_normalized": "L",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 200
        assert existing.quantity_normalized == Decimal("1.500")

    def test_viewer_cannot_add(self, client, mock_async_db, mock_user):
        """A viewer-role member cannot add ingredients."""
        from utils.models.ingredient import Ingredient

        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(
            mock_async_db, mock_user, pantry_id, role="viewer"
        )
        ingredient = MockIngredient()
        mock_async_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
        ]

        body = {
            "ingredient_id": str(ingredient.id),
            "quantity_display": "1",
            "unit_display": "each",
            "quantity_normalized": "1",
            "unit_normalized": "each",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 403

    def test_invalid_storage_location_rejected(self, client, mock_async_db, mock_user):
        """Pydantic rejects storage_location values outside the enum."""
        pantry_id = str(uuid.uuid4())
        body = {
            "ingredient_id": str(uuid.uuid4()),
            "quantity_display": "1",
            "unit_display": "each",
            "quantity_normalized": "1",
            "unit_normalized": "each",
            "storage_location": "garage",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 422

    def test_unknown_ingredient_returns_404(self, client, mock_async_db, mock_user):
        """A valid pantry but a non-existent ingredient returns 404."""
        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(mock_async_db, mock_user, pantry_id)
        # Ingredient lookup returns None (not set in registry).
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
        ]

        body = {
            "ingredient_id": str(uuid.uuid4()),
            "quantity_display": "1",
            "unit_display": "each",
            "quantity_normalized": "1",
            "unit_normalized": "each",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 404

    def test_missing_pantry_returns_404(self, client, mock_async_db, mock_user):
        """A mutate call on a non-existent pantry returns 404."""
        pantry_id = str(uuid.uuid4())
        # No Pantry in registry → require_pantry_access_async raises 404
        # before any execute() is needed.
        body = {
            "ingredient_id": str(uuid.uuid4()),
            "quantity_display": "1",
            "unit_display": "each",
            "quantity_normalized": "1",
            "unit_normalized": "each",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 404

    def test_name_only_creates_fresh_ingredient_row(
        self, client, mock_async_db, mock_user
    ):
        """Post-str-ing-2: supplying only `name` stages a fresh Ingredient
        row — no find-or-create. The new row ID then feeds the upsert."""
        from utils.models.ingredient import Ingredient

        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(mock_async_db, mock_user, pantry_id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[]),  # upsert existing lookup
        ]

        body = {
            "name": "Olive Oil",
            "quantity_display": "1",
            "unit_display": "tbsp",
            "quantity_normalized": "15",
            "unit_normalized": "ml",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 201
        # Confirm exactly one Ingredient instance was staged with the
        # lowercased + stripped canonical name (find-or-create would have
        # added zero — it hits find_by first).
        staged = [
            call.args[0]
            for call in mock_async_db.db.add.call_args_list
            if isinstance(call.args[0], Ingredient)
        ]
        assert len(staged) == 1
        assert staged[0].canonical_name == "olive oil"

    def test_neither_id_nor_name_returns_400(self, client, mock_async_db, mock_user):
        """Missing both `ingredient_id` and `name` is a structured 400."""
        pantry_id = str(uuid.uuid4())
        _pantry, membership = self._setup_access(mock_async_db, mock_user, pantry_id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
        ]

        body = {
            "quantity_display": "1",
            "unit_display": "each",
            "quantity_normalized": "1",
            "unit_normalized": "each",
        }
        response = client.post(f"/v1/pantries/{pantry_id}/ingredients", json=body)
        assert response.status_code == 400


class TestUpdatePantryIngredient:
    """Tests for PATCH /v1/pantries/{pantry_id}/ingredients/{ingredient_id}."""

    def test_partial_update_changes_only_provided_fields(
        self, client, mock_async_db, mock_user
    ):
        """Only provided fields are updated; others are preserved."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="editor"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        row = MockPantryIngredient(
            pantry_id=pantry_id,
            ingredient_id=ingredient_id,
            quantity_display=Decimal("1.000"),
            unit_display="kg",
            quantity_normalized=Decimal("1000.000"),
            unit_normalized="g",
            storage_location="pantry",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[row]),
        ]

        response = client.patch(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}",
            json={"storage_location": "fridge"},
        )
        assert response.status_code == 200
        assert row.storage_location == "fridge"
        assert row.quantity_display == Decimal("1.000")

    def test_clamp_to_zero_auto_archives(self, client, mock_async_db, mock_user):
        """PATCH with negative quantity clamps to 0 and archives the row."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        row = MockPantryIngredient(
            pantry_id=pantry_id,
            ingredient_id=ingredient_id,
            quantity_normalized=Decimal("5.000"),
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[row]),
        ]

        response = client.patch(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}",
            json={"quantity_normalized": "-2"},
        )
        assert response.status_code == 200
        assert row.quantity_normalized == Decimal(0)
        assert row.archived_at is not None

    def test_updates_all_optional_fields(self, client, mock_async_db, mock_user):
        """Covers the remaining conditional branches in update_ingredient."""
        from datetime import UTC, datetime

        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        row = MockPantryIngredient(
            pantry_id=pantry_id,
            ingredient_id=ingredient_id,
            quantity_display=Decimal("1.000"),
            unit_display="kg",
            quantity_normalized=Decimal("1000.000"),
            unit_normalized="g",
            storage_location="pantry",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[row]),
        ]

        future = datetime(2027, 1, 1, tzinfo=UTC).isoformat()
        response = client.patch(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}",
            json={
                "quantity_display": "5",
                "unit_display": "g",
                "quantity_normalized": "500",
                "unit_normalized": "g",
                "storage_location": "freezer",
                "expires_at": future,
            },
        )
        assert response.status_code == 200
        assert row.quantity_display == Decimal(5)
        assert row.unit_display == "g"
        assert row.quantity_normalized == Decimal(500)
        assert row.storage_location == "freezer"

    def test_archived_row_returns_404(self, client, mock_async_db, mock_user):
        """PATCH on an archived ingredient returns 404."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[]),
        ]

        response = client.patch(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}",
            json={"quantity_normalized": "5"},
        )
        assert response.status_code == 404


class TestDeletePantryIngredient:
    """Tests for DELETE /v1/pantries/{pantry_id}/ingredients/{ingredient_id}."""

    def test_soft_delete_sets_archived_at(self, client, mock_async_db, mock_user):
        """Delete sets archived_at on an active row."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        row = MockPantryIngredient(
            pantry_id=pantry_id, ingredient_id=ingredient_id, archived_at=None
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[row]),
        ]

        response = client.delete(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}"
        )
        assert response.status_code == 200
        assert row.archived_at is not None

    def test_idempotent_on_already_archived(self, client, mock_async_db, mock_user):
        """A second delete on an already archived row is a no-op 200."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        already_archived = datetime.now(UTC)
        row = MockPantryIngredient(
            pantry_id=pantry_id,
            ingredient_id=ingredient_id,
            archived_at=already_archived,
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
            MockExecuteResult(items=[row]),
        ]

        response = client.delete(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}"
        )
        assert response.status_code == 200
        # archived_at is unchanged
        assert row.archived_at == already_archived

    def test_viewer_cannot_delete(self, client, mock_async_db, mock_user):
        """A viewer cannot soft-delete items."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="viewer"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
        ]

        response = client.delete(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}"
        )
        assert response.status_code == 403

    def test_non_member_cannot_delete(self, client, mock_async_db, mock_user):
        """A user with no membership at all gets 403."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),  # no membership
        ]

        response = client.delete(
            f"/v1/pantries/{pantry_id}/ingredients/{ingredient_id}"
        )
        assert response.status_code == 403


class TestEstimateExpiry:
    """Tests for POST /v1/pantries/{pantry_id}/estimate-expiry."""

    def test_estimate_returns_expires_at(self, client, mock_async_db, mock_user):
        """Happy path: any member can estimate; ingredient hits registry."""
        from utils.models.ingredient import Ingredient
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="viewer"
        )
        ingredient = MockIngredient(canonical_name="milk")
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)
        mock_async_db.set_find_by(Ingredient, ingredient, id=str(ingredient.id))

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),  # require_pantry_access_async
        ]

        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(ingredient.id),
                "storage_location": "fridge",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # shelf_life_service returns an ISO string or None — just confirm the key exists.
        assert "expires_at" in data

    def test_missing_pantry_returns_404(self, client, mock_async_db, mock_user):
        """No Pantry in registry — require_pantry_access_async raises 404 first."""
        pantry_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "pantry",
            },
        )
        assert response.status_code == 404

    def test_unknown_ingredient_returns_404(self, client, mock_async_db, mock_user):
        """Pantry + membership resolve, but the ingredient lookup misses."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=pantry_id, role="owner"
        )
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[membership]),
        ]

        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "pantry",
            },
        )
        assert response.status_code == 404

    def test_non_member_cannot_estimate(self, client, mock_async_db, mock_user):
        """require_pantry_access_async rejects non-members with 403."""
        from utils.models.pantry import Pantry

        pantry_id = str(uuid.uuid4())
        pantry = MockPantry(id=pantry_id)
        mock_async_db.set_find_by(Pantry, pantry, id=pantry_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),  # no membership
        ]

        response = client.post(
            f"/v1/pantries/{pantry_id}/estimate-expiry",
            json={
                "ingredient_id": str(uuid.uuid4()),
                "storage_location": "pantry",
            },
        )
        assert response.status_code == 403
