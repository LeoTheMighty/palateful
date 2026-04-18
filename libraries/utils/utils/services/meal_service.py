"""Meal domain service.

Encapsulates multi-row writes (create, reorder, component add/remove) so
that every handler gets the same transactional shape, and component
hydration (availability marking against archived recipes + unshared
books) lives in one place.

Kept orthogonal to `services/api/src/api/v1/meal/*.py` — handlers are
thin wrappers that do auth + schema translation; everything else lives
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import selectinload

from utils.models.meal import Meal
from utils.models.meal_favorite import MealFavorite
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook  # noqa: F401 — selectinload chain
from utils.models.recipe_book_user import RecipeBookUser


class MealServiceError(Exception):
    """Base for domain errors. Handlers translate these into APIException."""


class ComponentUnreadableError(MealServiceError):
    """A component recipe exists but the user can't read its book."""

    def __init__(self, recipe_ids: list[str]):
        super().__init__(f"Components unreadable: {recipe_ids}")
        self.recipe_ids = recipe_ids


class ComponentDuplicateError(MealServiceError):
    """The component is already attached to this Meal."""


class ComponentNotFoundError(MealServiceError):
    """The component isn't on this Meal."""


class MinComponentsError(MealServiceError):
    """Removing would drop the Meal below 2 components."""


class ReorderMismatchError(MealServiceError):
    """The reorder list doesn't match the current component set."""


@dataclass
class ComponentHydration:
    """Flat shape returned by `hydrate_components` — one row per component.

    `available=False` when the recipe is archived OR the user no longer
    has read membership on the recipe's book. Read handlers hide these
    in the aggregate; edit handlers surface them with a Remove action.
    """

    recipe_id: str
    order_index: int
    name: str
    image_url: str | None
    prep_time: int | None
    cook_time: int | None
    book_name: str | None
    available: bool
    last_known_name: str | None


class MealService:
    """Meal domain service. Instantiated per-request with a live session."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_with_components(self, meal_id: str) -> Meal | None:
        """Eager-load a Meal + components (MealRecipe → Recipe → RecipeBook).

        `selectinload` is deliberate: the IN-batched second query
        collapses the N-per-meal fanout to 2 queries regardless of
        component count, which matters for the list endpoint (50 meals
        × 6 components would be 50 wide-row explosions under joinedload).
        """
        return (
            self.db.query(Meal)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .filter(Meal.id == meal_id)
            .first()
        )

    def _readable_book_ids(self, user_id) -> set:
        """Return the set of recipe_book_ids the user can read."""
        rows = (
            self.db.query(RecipeBookUser.recipe_book_id)
            .filter(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.archived_at.is_(None),
            )
            .all()
        )
        return {str(row[0]) for row in rows}

    def hydrate_components(
        self, meal: Meal, *, user_id
    ) -> list[ComponentHydration]:
        """Flatten a Meal's components into response-shaped rows."""
        readable = self._readable_book_ids(user_id)
        hydrations: list[ComponentHydration] = []
        for comp in meal.components:
            recipe = comp.recipe
            if recipe is None:
                # Shouldn't happen with RESTRICT on recipe_id, but if the
                # ORM state is somehow inconsistent we surface an
                # unavailable row rather than 500.
                hydrations.append(
                    ComponentHydration(
                        recipe_id=str(comp.recipe_id),
                        order_index=comp.order_index,
                        name="",
                        image_url=None,
                        prep_time=None,
                        cook_time=None,
                        book_name=None,
                        available=False,
                        last_known_name=None,
                    )
                )
                continue

            book = recipe.recipe_book
            book_readable = str(recipe.recipe_book_id) in readable
            available = (
                recipe.archived_at is None
                and book is not None
                and book.archived_at is None
                and book_readable
            )
            hydrations.append(
                ComponentHydration(
                    recipe_id=str(recipe.id),
                    order_index=comp.order_index,
                    name=recipe.name if available else "",
                    image_url=recipe.image_url if available else None,
                    prep_time=recipe.prep_time if available else None,
                    cook_time=recipe.cook_time if available else None,
                    book_name=book.name if available and book else None,
                    available=available,
                    last_known_name=None if available else recipe.name,
                )
            )
        return hydrations

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def user_has_book_read(self, user_id, book_id) -> bool:
        return (
            self.db.query(RecipeBookUser)
            .filter(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.recipe_book_id == book_id,
                RecipeBookUser.archived_at.is_(None),
            )
            .first()
            is not None
        )

    def user_has_book_write(self, user_id, book_id) -> bool:
        membership = (
            self.db.query(RecipeBookUser)
            .filter(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.recipe_book_id == book_id,
                RecipeBookUser.archived_at.is_(None),
            )
            .first()
        )
        return membership is not None and membership.role in ("owner", "editor")

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def _ensure_components_readable(
        self, recipe_ids: list[str], *, user_id
    ) -> list[Recipe]:
        """Fetch recipes by id; raise if any are missing or unreadable."""
        recipes = (
            self.db.query(Recipe)
            .filter(Recipe.id.in_(recipe_ids))
            .all()
        )
        found_ids = {str(r.id) for r in recipes}
        missing = [rid for rid in recipe_ids if rid not in found_ids]
        readable = self._readable_book_ids(user_id)
        unreadable = [
            str(r.id) for r in recipes if str(r.recipe_book_id) not in readable
        ]
        if missing or unreadable:
            raise ComponentUnreadableError(missing + unreadable)
        return recipes

    def create_with_components(
        self,
        *,
        book_id: str,
        name: str,
        description: str | None,
        recipe_ids: list[str],
        user_id,
    ) -> Meal:
        """Create a Meal + its join rows in a single flush.

        The caller is expected to hold a request transaction; this
        function stages the writes and flushes, but does NOT commit —
        the request-scoped endpoint middleware handles the commit so a
        failure downstream in the handler rolls the whole thing back.
        """
        self._ensure_components_readable(recipe_ids, user_id=user_id)

        meal = Meal(
            name=name,
            description=description,
            recipe_book_id=book_id,
        )
        self.db.add(meal)
        self.db.flush()

        for idx, rid in enumerate(recipe_ids):
            self.db.add(
                MealRecipe(
                    meal_id=meal.id,
                    recipe_id=rid,
                    order_index=idx,
                )
            )
        self.db.flush()
        self.db.refresh(meal)
        return meal

    def add_component(
        self, *, meal: Meal, recipe_id: str, order_index: int | None, user_id
    ) -> MealRecipe:
        existing = (
            self.db.query(MealRecipe)
            .filter(
                MealRecipe.meal_id == meal.id,
                MealRecipe.recipe_id == recipe_id,
            )
            .first()
        )
        if existing is not None:
            raise ComponentDuplicateError(
                f"recipe {recipe_id} already on meal {meal.id}"
            )
        self._ensure_components_readable([recipe_id], user_id=user_id)

        if order_index is None:
            max_row = (
                self.db.query(MealRecipe)
                .filter(MealRecipe.meal_id == meal.id)
                .order_by(MealRecipe.order_index.desc())
                .first()
            )
            order_index = (max_row.order_index + 1) if max_row else 0

        row = MealRecipe(
            meal_id=meal.id,
            recipe_id=recipe_id,
            order_index=order_index,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def remove_component(self, *, meal: Meal, recipe_id: str) -> None:
        rows = (
            self.db.query(MealRecipe)
            .filter(MealRecipe.meal_id == meal.id)
            .all()
        )
        if len(rows) <= 2:
            raise MinComponentsError("Meal must retain at least 2 components")
        target = next(
            (r for r in rows if str(r.recipe_id) == recipe_id), None
        )
        if target is None:
            raise ComponentNotFoundError(
                f"recipe {recipe_id} not on meal {meal.id}"
            )
        self.db.delete(target)
        self.db.flush()

    def reorder_components(
        self, *, meal: Meal, recipe_ids: list[str]
    ) -> None:
        current = (
            self.db.query(MealRecipe)
            .filter(MealRecipe.meal_id == meal.id)
            .all()
        )
        current_ids = {str(r.recipe_id) for r in current}
        if current_ids != set(recipe_ids) or len(recipe_ids) != len(current):
            raise ReorderMismatchError(
                "reorder set does not match current components"
            )
        by_recipe = {str(r.recipe_id): r for r in current}
        for idx, rid in enumerate(recipe_ids):
            by_recipe[rid].order_index = idx
        self.db.flush()

    def archive(self, meal: Meal) -> Meal:
        meal.archived_at = datetime.now(UTC)
        self.db.flush()
        return meal

    def restore(self, meal: Meal) -> Meal:
        meal.archived_at = None
        self.db.flush()
        return meal

    # ------------------------------------------------------------------
    # Favorite helpers
    # ------------------------------------------------------------------

    def set_favorite(self, *, user_id, meal_id: str, favorite: bool) -> bool:
        """Toggle `meal_favorites` row. Returns True if state changed."""
        existing = (
            self.db.query(MealFavorite)
            .filter(
                MealFavorite.user_id == user_id,
                MealFavorite.meal_id == meal_id,
            )
            .first()
        )
        if favorite:
            if existing is not None:
                return False  # no-op, already favorited
            self.db.add(MealFavorite(user_id=user_id, meal_id=meal_id))
            self.db.flush()
            return True
        if existing is None:
            return False  # no-op, already not favorited
        self.db.delete(existing)
        self.db.flush()
        return True

    def is_favorited(self, *, user_id, meal_id) -> bool:
        """Return whether the given user has favorited this meal."""
        return (
            self.db.query(MealFavorite)
            .filter(
                MealFavorite.user_id == user_id,
                MealFavorite.meal_id == meal_id,
            )
            .first()
            is not None
        )
