"""Tests for recipe public sharing endpoints."""

import uuid

from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
    MockRecipeIngredient,
    MockRecipeStep,
)


def _setup_recipe(mock_db, mock_user, recipe_id=None, book_id=None, role="owner"):
    """Set up a recipe with book membership for auth'd endpoint tests."""
    book_id = book_id or str(uuid.uuid4())
    recipe_id = recipe_id or str(uuid.uuid4())

    recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Pasta")
    membership = MockRecipeBookUser(
        user_id=str(mock_user.id), recipe_book_id=book_id, role=role
    )

    from utils.models.recipe import Recipe
    from utils.models.recipe_book_user import RecipeBookUser

    mock_db.set_find_by(Recipe, recipe, id=recipe_id)
    mock_db.set_find_by(
        RecipeBookUser,
        membership,
        user_id=mock_user.id,
        recipe_book_id=book_id,
    )

    return recipe_id, book_id, recipe


class TestShareRecipeGenerate:
    """POST /v1/recipes/{recipe_id}/share — generate public share token."""

    def test_generate_returns_201_with_token_and_deep_link(
        self, client, mock_db, mock_user
    ):
        """Successful generate returns 201 with token and deep_link."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user)

        response = client.post(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert len(data["token"]) <= 20
        assert data["deep_link"] == f"palateful://recipe-public/{data['token']}"

    def test_generate_calls_commit(self, client, mock_db, mock_user):
        """Token generation commits to the database."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user)

        client.post(f"/v1/recipes/{recipe_id}/share")

        mock_db.db.commit.assert_called()

    def test_generate_replaces_existing_token(self, client, mock_db, mock_user):
        """Calling generate twice updates the token (each call returns a new token)."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user)

        response1 = client.post(f"/v1/recipes/{recipe_id}/share")
        response2 = client.post(f"/v1/recipes/{recipe_id}/share")

        assert response1.status_code == 201
        assert response2.status_code == 201
        # Each call generates a distinct token (collision is astronomically unlikely)
        assert response1.json()["token"] != response2.json()["token"]

    def test_generate_recipe_not_found_returns_404(self, client, mock_db, mock_user):
        """Returns 404 when recipe doesn't exist."""
        recipe_id = str(uuid.uuid4())
        # No recipe registered in mock_db → find_by returns None

        response = client.post(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 404

    def test_generate_non_member_returns_403(self, client, mock_db, mock_user):
        """Returns 403 when user is not a book member."""
        book_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        # No membership registered → find_by returns None
        mock_db.set_find_by(
            RecipeBookUser,
            None,
            user_id=mock_user.id,
            recipe_book_id=book_id,
        )

        response = client.post(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 403

    def test_generate_viewer_member_returns_403(self, client, mock_db, mock_user):
        """Returns 403 when user is only a viewer (not owner/editor)."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user, role="viewer")

        response = client.post(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 403

    def test_generate_unauthenticated_rejected(self, unauthed_client):
        """Unauthenticated requests are rejected."""
        response = unauthed_client.post(f"/v1/recipes/{uuid.uuid4()}/share")
        assert response.status_code in (401, 422)


class TestRevokeRecipeShare:
    """DELETE /v1/recipes/{recipe_id}/share — revoke public share token."""

    def test_revoke_returns_200_success(self, client, mock_db, mock_user):
        """Successful revoke returns 200 with success=true."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user)

        response = client.delete(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_revoke_calls_commit(self, client, mock_db, mock_user):
        """Revoke commits the null token to the database."""
        recipe_id, _, recipe = _setup_recipe(mock_db, mock_user)

        client.delete(f"/v1/recipes/{recipe_id}/share")

        mock_db.db.commit.assert_called()

    def test_revoke_clears_share_token(self, client, mock_db, mock_user):
        """Revoke sets share_token to None on the recipe object."""
        recipe_id, _, recipe = _setup_recipe(mock_db, mock_user)
        recipe.share_token = "someexistingtoken"

        client.delete(f"/v1/recipes/{recipe_id}/share")

        assert recipe.share_token is None

    def test_revoke_recipe_not_found_returns_404(self, client, mock_db, mock_user):
        """Returns 404 when recipe doesn't exist."""
        recipe_id = str(uuid.uuid4())

        response = client.delete(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 404

    def test_revoke_non_member_returns_403(self, client, mock_db, mock_user):
        """Returns 403 when user is not a book member."""
        book_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(
            RecipeBookUser,
            None,
            user_id=mock_user.id,
            recipe_book_id=book_id,
        )

        response = client.delete(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 403

    def test_revoke_viewer_member_returns_403(self, client, mock_db, mock_user):
        """Returns 403 when user is only a viewer (not owner/editor)."""
        recipe_id, _, _ = _setup_recipe(mock_db, mock_user, role="viewer")

        response = client.delete(f"/v1/recipes/{recipe_id}/share")

        assert response.status_code == 403

    def test_revoke_unauthenticated_rejected(self, unauthed_client):
        """Unauthenticated requests are rejected."""
        response = unauthed_client.delete(f"/v1/recipes/{uuid.uuid4()}/share")
        assert response.status_code in (401, 422)


class TestGetPublicRecipeByToken:
    """GET /v1/recipes/public/{token} — no auth required."""

    def _setup_public(self, mock_db, token="tok12345678901234567"):
        """Set up mocks for a public recipe lookup by token."""
        book_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            name="Public Pasta",
            share_token=token,
        )
        book = MockRecipeBook(id=book_id, name="My Cookbook")
        ingredient = MockIngredient(id=ingredient_id, canonical_name="flour")
        ri = MockRecipeIngredient(
            recipe_id=recipe_id,
            ingredient_id=ingredient_id,
        )
        step = MockRecipeStep(
            recipe_id=recipe_id, step_number=1, instruction="Boil water"
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep

        # First db.query call: Recipe lookup by share_token
        # Second db.query call: RecipeIngredient + Ingredient join
        mock_db.db.query.side_effect = [
            MockQuery([recipe]),
            MockQuery([(ri, ingredient)]),
        ]
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_where(RecipeStep, [step])

        return recipe_id, token

    def test_public_endpoint_returns_200_with_recipe(self, client, mock_db):
        """Valid token returns 200 with recipe data."""
        _, token = self._setup_public(mock_db)

        response = client.get(f"/v1/recipes/public/{token}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Public Pasta"
        assert data["recipe_book_name"] == "My Cookbook"

    def test_public_endpoint_includes_steps_and_ingredients(
        self, client, mock_db
    ):
        """Response includes steps and ingredients."""
        _, token = self._setup_public(mock_db)

        response = client.get(f"/v1/recipes/public/{token}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["instruction"] == "Boil water"
        assert len(data["ingredients"]) == 1
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "flour"

    def test_public_endpoint_invalid_token_returns_404(self, client, mock_db):
        """Unknown token returns 404."""
        # db.query returns empty result for unknown token
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recipes/public/unknowntoken12345678")

        assert response.status_code == 404

    def test_public_endpoint_archived_recipe_returns_404(self, client, mock_db):
        """Archived recipe is not accessible via share token (archive filter applied)."""
        # Simulates DB returning no result after archive filter excludes the recipe
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recipes/public/tok12345678901234567")

        assert response.status_code == 404

    def test_public_endpoint_no_auth_required(self, unauthed_client, mock_db):
        """Public endpoint works without authentication."""
        token = "tok12345678901234567"
        book_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            name="Unauthed Recipe",
            share_token=token,
        )
        book = MockRecipeBook(id=book_id, name="Unauthed Book")

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_step import RecipeStep

        mock_db.db.query.side_effect = [
            MockQuery([recipe]),
            MockQuery([]),  # No ingredients
        ]
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_where(RecipeStep, [])

        response = unauthed_client.get(f"/v1/recipes/public/{token}")

        assert response.status_code == 200
        assert response.json()["name"] == "Unauthed Recipe"
