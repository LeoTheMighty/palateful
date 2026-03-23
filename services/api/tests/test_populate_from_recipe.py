"""Tests for PopulateFromRecipe endpoint and router broadcast."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from conftest import (
    MockIngredient,
    MockRecipe,
    MockRecipeBookUser,
    MockRecipeIngredient,
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
)


def make_recipe_ingredient(ingredient_id, recipe_id, canonical_name="Flour", category="Baking"):
    """Helper to create a MockRecipeIngredient with a linked MockIngredient."""
    ingredient = MockIngredient(
        id=ingredient_id,
        canonical_name=canonical_name,
        category=category,
    )
    ri = MockRecipeIngredient(
        ingredient_id=ingredient_id,
        recipe_id=recipe_id,
        quantity_display=Decimal("2.000"),
        unit_display="cups",
    )
    ri.ingredient = ingredient
    return ri


class TestPopulateFromRecipeSuccess:
    """Core success path — items are added, counts are correct."""

    def test_populate_from_recipe_success(self, client, mock_db, mock_user):
        """Adds recipe ingredients and returns correct items_added count."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        recipe.ingredients = [ri]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1
        assert data["items_skipped"] == 0
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Flour"
        assert data["items"][0]["unit"] == "cups"
        assert data["items"][0]["category"] == "Baking"
        assert data["items"][0]["recipe_id"] == recipe_id
        assert data["items"][0]["ingredient_id"] == ingredient_id

    def test_populate_from_recipe_multiple_ingredients(self, client, mock_db, mock_user):
        """All non-archived ingredients are added."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = [
            make_recipe_ingredient(str(uuid.uuid4()), recipe_id, "Flour"),
            make_recipe_ingredient(str(uuid.uuid4()), recipe_id, "Sugar"),
            make_recipe_ingredient(str(uuid.uuid4()), recipe_id, "Eggs"),
        ]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 3
        assert data["items_skipped"] == 0

    def test_populate_from_recipe_with_scale_factor(self, client, mock_db, mock_user):
        """Quantities are scaled when scale_factor != 1.0."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        recipe.ingredients = [ri]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id, "scale_factor": 2.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1
        assert data["items_skipped"] == 0
        # Original quantity is 2.000, scaled by 2.0 = 4.00
        item = data["items"][0]
        assert Decimal(str(item["quantity"])) == Decimal("4")


class TestPopulateFromRecipeDeduplication:
    """Deduplication — already-added items from the same recipe are skipped."""

    def test_populate_from_recipe_skips_duplicates(self, client, mock_db, mock_user):
        """If same (ingredient_id, recipe_id) already in list, it is skipped."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        recipe.ingredients = [ri]

        # Existing item with same ingredient_id and recipe_id (string IDs match mock model defaults)
        existing_item = MockShoppingListItem(
            shopping_list_id=list_id,
            ingredient_id=ingredient_id,
            recipe_id=recipe_id,
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[existing_item])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 1

    def test_populate_from_recipe_skips_archived_ingredients(self, client, mock_db, mock_user):
        """Recipe ingredients with archived_at set are not added."""
        from datetime import datetime, timezone

        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        ri.archived_at = datetime.now(timezone.utc)  # Mark as archived
        recipe.ingredients = [ri]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 0


class TestPopulateFromRecipeErrors:
    """Error cases — 404 and 403 responses."""

    def test_populate_from_recipe_404_recipe(self, client, mock_db, mock_user):
        """Returns 404 when recipe is not found."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        # recipe not set in mock_db → find_by returns None

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 404

    def test_populate_from_recipe_403_no_recipe_access(self, client, mock_db, mock_user):
        """Returns 403 when user is not a member of the recipe's book."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = []

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        # RecipeBookUser not configured → find_by returns None → 403

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 403

    def test_populate_from_recipe_404_list(self, client, mock_db, mock_user):
        """Returns 404 when shopping list is not found."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = []

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        # ShoppingList not configured → find_by returns None → 404

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 404

    def test_populate_from_recipe_403_no_list_access(self, client, mock_db, mock_user):
        """Returns 403 when user is not an owner or editor of the shopping list."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = []

        # Shopping list owned by someone else, user has no membership
        sl = MockShoppingList(id=list_id, owner_id=other_user_id, items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # ShoppingListUser not configured → find_by returns None → 403

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 403

    def test_populate_from_recipe_editor_member_can_add_items(self, client, mock_db, mock_user):
        """A non-owner member with 'editor' role can successfully add items."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        recipe.ingredients = [ri]

        # List owned by someone else
        sl = MockShoppingList(id=list_id, owner_id=other_owner_id, items=[])

        # mock_user is an editor member
        editor_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListUser, editor_membership, shopping_list_id=list_id, user_id=str(mock_user.id))

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1


class TestPopulateFromRecipeBroadcast:
    """Verify WebSocket broadcast is called for each added item."""

    def test_populate_from_recipe_broadcasts_each_item(self, client, mock_db, mock_user):
        """Router broadcasts item_added for every ingredient added."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = [
            make_recipe_ingredient(str(uuid.uuid4()), recipe_id, "Flour"),
            make_recipe_ingredient(str(uuid.uuid4()), recipe_id, "Sugar"),
        ]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.post(
                f"/v1/shopping-lists/{list_id}/populate-from-recipe",
                json={"recipe_id": recipe_id},
            )

        assert response.status_code == 200
        assert mock_broadcast.call_count == 2

        for call in mock_broadcast.call_args_list:
            args = call[0]
            assert args[0] == list_id
            assert args[1] == "item_added"
            assert isinstance(args[2], dict)
            assert "id" in args[2], "broadcast data must include item id"
            assert "name" in args[2]
            kwargs = call[1]
            assert kwargs.get("user_id") == str(mock_user.id), "broadcast must carry actor user_id"

    def test_populate_from_recipe_no_broadcast_when_all_skipped(self, client, mock_db, mock_user):
        """No broadcast when all items are duplicates (nothing added)."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        ri = make_recipe_ingredient(ingredient_id, recipe_id)
        recipe.ingredients = [ri]

        existing_item = MockShoppingListItem(
            shopping_list_id=list_id,
            ingredient_id=ingredient_id,
            recipe_id=recipe_id,
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[existing_item])

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, MockRecipeBookUser(), user_id=str(mock_user.id), recipe_book_id=recipe.recipe_book_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.post(
                f"/v1/shopping-lists/{list_id}/populate-from-recipe",
                json={"recipe_id": recipe_id},
            )

        assert response.status_code == 200
        mock_broadcast.assert_not_called()
