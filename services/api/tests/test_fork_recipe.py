"""Tests for ForkRecipe endpoint."""

from conftest import MockRecipe, MockRecipeBook, MockRecipeBookUser


BOOK_ID = "b0000000-0000-0000-0000-000000000001"
DEST_BOOK_ID = "b0000000-0000-0000-0000-000000000002"
RECIPE_ID = "13000000-0000-0000-0000-000000000001"


class TestForkRecipe:
    """Tests for POST /v1/recipes/{recipe_id}/fork."""

    def test_fork_recipe_success(self, client, mock_db, mock_user):
        """Test forking a recipe successfully, verifying 201 + lineage fields."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID, name="Nonna's Pasta")
        src_book = MockRecipeBook(id=BOOK_ID, name="Family Recipes")
        dest_book = MockRecipeBook(id=DEST_BOOK_ID, name="My Recipes")
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=DEST_BOOK_ID,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        mock_db.set_find_by(
            RecipeBookUser, src_membership,
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID
        )
        mock_db.set_find_by(RecipeBook, dest_book, id=DEST_BOOK_ID)
        mock_db.set_find_by(
            RecipeBookUser, dest_membership,
            user_id=str(mock_user.id), recipe_book_id=DEST_BOOK_ID
        )
        mock_db.set_find_by(RecipeBook, src_book, id=BOOK_ID)

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["forked_from_recipe_id"] == RECIPE_ID
        assert data["forked_from_book_id"] == BOOK_ID
        assert data["forked_from_recipe_name"] == "Nonna's Pasta"
        assert data["forked_from_book_name"] == "Family Recipes"

    def test_fork_recipe_no_source_access_returns_403(self, client, mock_db, mock_user):
        """Test forking a recipe without access to source book returns 403."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID)

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        # No source membership configured → find_by returns None

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 403

    def test_fork_recipe_dest_not_owner_returns_403(self, client, mock_db, mock_user):
        """Test forking into a book where user is editor (not owner) returns 403."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID)
        dest_book = MockRecipeBook(id=DEST_BOOK_ID)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=DEST_BOOK_ID,
            role="editor",  # not owner
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        mock_db.set_find_by(
            RecipeBookUser, src_membership,
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID
        )
        mock_db.set_find_by(RecipeBook, dest_book, id=DEST_BOOK_ID)
        mock_db.set_find_by(
            RecipeBookUser, dest_membership,
            user_id=str(mock_user.id), recipe_book_id=DEST_BOOK_ID
        )

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 403

    def test_fork_recipe_dest_no_membership_returns_403(self, client, mock_db, mock_user):
        """Test forking into a book where user has no membership returns 403."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID)
        dest_book = MockRecipeBook(id=DEST_BOOK_ID)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        mock_db.set_find_by(
            RecipeBookUser, src_membership,
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID
        )
        mock_db.set_find_by(RecipeBook, dest_book, id=DEST_BOOK_ID)
        # No dest_membership configured → find_by returns None

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 403

    def test_fork_recipe_not_found_returns_404(self, client, mock_db, mock_user):
        """Test forking a recipe that does not exist returns 404."""
        # No recipe configured → find_by returns None

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 404

    def test_fork_recipe_dest_book_not_found_returns_404(self, client, mock_db, mock_user):
        """Test forking into a nonexistent destination book returns 404."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        mock_db.set_find_by(
            RecipeBookUser, src_membership,
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID
        )
        # No dest book configured -> find_by returns None -> 404

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 404

    def test_fork_recipe_src_book_none_uses_unknown(self, client, mock_db, mock_user):
        """Test that when source book is None, book name defaults to 'Unknown Book' (line 76)."""
        recipe = MockRecipe(id=RECIPE_ID, recipe_book_id=BOOK_ID, name="Pasta")
        dest_book = MockRecipeBook(id=DEST_BOOK_ID, name="My Recipes")
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=DEST_BOOK_ID,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=RECIPE_ID)
        mock_db.set_find_by(
            RecipeBookUser, src_membership,
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID
        )
        mock_db.set_find_by(RecipeBook, dest_book, id=DEST_BOOK_ID)
        mock_db.set_find_by(
            RecipeBookUser, dest_membership,
            user_id=str(mock_user.id), recipe_book_id=DEST_BOOK_ID
        )
        # Source book NOT configured -> find_by returns None -> src_book_name = "Unknown Book"

        response = client.post(
            f"/v1/recipes/{RECIPE_ID}/fork",
            json={"destination_book_id": DEST_BOOK_ID},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["forked_from_book_name"] == "Unknown Book"
