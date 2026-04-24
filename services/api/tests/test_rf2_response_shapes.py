"""rf-2: response-shape contract tests.

The Flutter client depends on these endpoints returning:

- `POST /v1/import-items/{id}/dismiss` — legacy top-level fields
  (``item_id``, ``dismissed_at``, ``job_dismissed``) **plus** a full
  ``item`` object. Old clients keep reading the legacy fields; new
  clients patch cached state from ``item``.
- `POST /v1/recipes/{id}/favorite` — full recipe payload (ingredients,
  steps, notes) with ``is_favorite`` nested inside. Old clients reading
  ``is_favorite`` at the top level keep working.
- `POST /v1/meals/{id}/favorite` — full ``MealResponse`` (hydrated
  components, ``is_favorite`` inside). Old clients reading ``is_favorite``
  at the top level keep working.

These tests are intentionally shape-focused (not behavior-focused) —
behavior-level coverage is in test_import.py / test_recipe.py.
"""

from unittest.mock import AsyncMock, patch

from conftest import (
    MockImportItem,
    MockImportJob,
    MockQuery,
    MockRecipe,
    MockRecipeBookUser,
    MockUserFavorite,
)


# ---------------------------------------------------------------------------
# POST /v1/import-items/{id}/dismiss
# ---------------------------------------------------------------------------


class TestDismissResponseShape:
    def _setup(self, mock_db, mock_user):
        item_id = "dismiss-rf2-item"
        job_id = "dismiss-rf2-job"
        book_id = "dismiss-rf2-book"
        item = MockImportItem(
            id=item_id,
            import_job_id=job_id,
            status="failed",
            dismissed_at=None,
            source_type="url",
            source_url="https://example.com/r",
            error_message="parser_timeout",
        )
        job = MockImportJob(
            id=job_id,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            status="failed",
            dismissed_at=None,
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.import_item import ImportItem
        from utils.models.import_job import ImportJob
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(ImportItem, item, id=item_id)
        mock_db.set_find_by(ImportJob, job, id=job_id)
        mock_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        mock_db.db.query.return_value = MockQuery([item])
        return item, job, item_id

    def test_legacy_top_level_fields_stay(self, client, mock_db, mock_user):
        _, _, item_id = self._setup(mock_db, mock_user)

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 200
        data = response.json()
        # pre-rf-2 clients read these three.
        assert data["item_id"] == item_id
        assert isinstance(data["dismissed_at"], str)
        assert data["job_dismissed"] is True

    def test_full_item_object_present(self, client, mock_db, mock_user):
        _, _, item_id = self._setup(mock_db, mock_user)

        response = client.post(f"/v1/import-items/{item_id}/dismiss")
        assert response.status_code == 200
        data = response.json()

        # rf-2: new `item` field carries the full ImportItemSummary.
        assert data["item"] is not None
        item = data["item"]
        assert item["id"] == item_id
        assert item["status"] == "failed"
        assert item["source_type"] == "url"
        assert item["source_url"] == "https://example.com/r"
        assert item["error_message"] == "parser_timeout"
        # ImportItemSummary also includes these server-shaped fields —
        # verify presence so the schema contract doesn't regress.
        assert "recipe_name" in item
        assert "needs_review" in item
        assert "ai_cost_cents" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# POST /v1/recipes/{id}/favorite
# ---------------------------------------------------------------------------


class TestFavoriteRecipeResponseShape:
    def _setup(self, mock_db, mock_user, *, has_favorite=False):
        recipe_id = "fav-rf2-recipe"
        book_id = "fav-rf2-book"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user_favorite import UserFavorite

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(
            RecipeBookUser,
            membership,
            user_id=mock_user.id,
            recipe_book_id=book_id,
        )
        if has_favorite:
            fav = MockUserFavorite(
                user_id=str(mock_user.id), recipe_id=recipe_id
            )
            mock_db.set_find_by(
                UserFavorite,
                fav,
                user_id=mock_user.id,
                recipe_id=recipe_id,
            )
        # Empty queries for steps/ingredients/versions/notes.
        mock_db.db.query.return_value = MockQuery([])
        return recipe_id

    def test_add_favorite_returns_full_recipe_payload(
        self, client, mock_db, mock_user
    ):
        recipe_id = self._setup(mock_db, mock_user, has_favorite=False)

        response = client.post(f"/v1/recipes/{recipe_id}/favorite")
        assert response.status_code == 201
        data = response.json()

        # Legacy top-level field — pre-rf-2 clients keep working.
        assert data["is_favorite"] is True

        # rf-2: full recipe payload nested alongside.
        assert data["id"] == recipe_id
        assert "name" in data
        assert "ingredients" in data
        assert "steps" in data
        assert "notes" in data
        assert "tags" in data
        assert "servings" in data
        assert isinstance(data["ingredients"], list)
        assert isinstance(data["steps"], list)

    def test_remove_favorite_returns_full_recipe_payload(
        self, client, mock_db, mock_user
    ):
        recipe_id = self._setup(mock_db, mock_user, has_favorite=True)

        response = client.post(f"/v1/recipes/{recipe_id}/favorite")
        assert response.status_code == 200
        data = response.json()

        assert data["is_favorite"] is False
        assert data["id"] == recipe_id
        assert "ingredients" in data
        assert "steps" in data


# ---------------------------------------------------------------------------
# POST/DELETE /v1/meals/{id}/favorite
# ---------------------------------------------------------------------------


class TestFavoriteMealResponseShape:
    def _patches(self, db_session, has_favorite):
        """Patch MealService methods used by favorite_meal + _access."""
        meal_mock = type(
            "FakeMeal",
            (),
            {
                "id": "meal-rf2",
                "name": "Test Dinner",
                "description": "rf-2 test",
                "recipe_book_id": "book-rf2",
                "archived_at": None,
                "created_at": __import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ),
                "updated_at": __import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ),
            },
        )()
        return meal_mock

    # aam-10: MealService methods are now async; patches need AsyncMock so
    # `await service.<method>(...)` resolves to `return_value` instead of
    # returning a plain MagicMock and tripping `TypeError: object MagicMock
    # can't be used in 'await' expression`.
    @patch("utils.services.meal_service.MealService.is_favorited", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.hydrate_components", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.set_favorite", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.user_has_book_read", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.get_with_components", new_callable=AsyncMock)
    def test_favorite_returns_full_meal_response(
        self,
        mock_get,
        mock_has_read,
        mock_set_fav,
        mock_hydrate,
        mock_is_fav,
        client,
        mock_db,
        mock_user,
    ):
        meal = self._patches(mock_db, has_favorite=True)
        mock_get.return_value = meal
        mock_has_read.return_value = True
        mock_hydrate.return_value = []
        mock_is_fav.return_value = True

        response = client.post("/v1/meals/meal-rf2/favorite")
        assert response.status_code == 201
        data = response.json()

        # Legacy top-level field — pre-rf-2 clients keep working.
        assert data["is_favorite"] is True
        # rf-2: full MealResponse payload.
        assert data["id"] == "meal-rf2"
        assert data["name"] == "Test Dinner"
        assert "recipe_book_id" in data
        assert "components" in data
        assert isinstance(data["components"], list)

    @patch("utils.services.meal_service.MealService.is_favorited", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.hydrate_components", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.set_favorite", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.user_has_book_read", new_callable=AsyncMock)
    @patch("utils.services.meal_service.MealService.get_with_components", new_callable=AsyncMock)
    def test_unfavorite_returns_full_meal_response(
        self,
        mock_get,
        mock_has_read,
        mock_set_fav,
        mock_hydrate,
        mock_is_fav,
        client,
        mock_db,
        mock_user,
    ):
        meal = self._patches(mock_db, has_favorite=False)
        mock_get.return_value = meal
        mock_has_read.return_value = True
        mock_hydrate.return_value = []
        mock_is_fav.return_value = False

        response = client.delete("/v1/meals/meal-rf2/favorite")
        assert response.status_code == 200
        data = response.json()

        assert data["is_favorite"] is False
        assert data["id"] == "meal-rf2"
        assert "components" in data
