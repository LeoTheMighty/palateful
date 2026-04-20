"""Shared response shaping for Meal endpoints."""

from schemas.meal import (
    MealComponentResponse,
    MealResponse,
    MealSummaryResponse,
)
from utils.models.meal import Meal
from utils.services.meal_service import MealService


def build_meal_response(meal: Meal, *, db, user_id) -> MealResponse:
    """Hydrate a Meal into the full response shape."""
    service = MealService(db)
    hydrations = service.hydrate_components(meal, user_id=user_id)
    components = [
        MealComponentResponse(
            recipe_id=h.recipe_id,
            name=h.name,
            image_url=h.image_url,
            prep_time=h.prep_time,
            cook_time=h.cook_time,
            book_name=h.book_name,
            order_index=h.order_index,
            available=h.available,
            last_known_name=h.last_known_name,
        )
        for h in hydrations
    ]
    return MealResponse(
        id=str(meal.id),
        name=meal.name,
        description=meal.description,
        recipe_book_id=str(meal.recipe_book_id),
        archived_at=meal.archived_at,
        created_at=meal.created_at,
        updated_at=meal.updated_at,
        components=components,
        is_favorite=service.is_favorited(user_id=user_id, meal_id=meal.id),
    )


def build_meal_summary(meal: Meal, *, db, user_id) -> MealSummaryResponse:
    """Thin grid-tile response — up to 4 component image URLs.

    `component_recipe_ids` is emitted in order so home (hmp-1) can run
    an in-memory join against the already-loaded recipe list to render
    the component-name chip row without an N+1 detail fetch.
    """
    hydrations = MealService(db).hydrate_components(meal, user_id=user_id)
    image_urls = [h.image_url for h in hydrations if h.available and h.image_url][:4]
    component_count = len(hydrations)
    component_recipe_ids = [h.recipe_id for h in hydrations]
    return MealSummaryResponse(
        id=str(meal.id),
        name=meal.name,
        description=meal.description,
        recipe_book_id=str(meal.recipe_book_id),
        component_count=component_count,
        component_image_urls=image_urls,
        component_recipe_ids=component_recipe_ids,
        archived_at=meal.archived_at,
        updated_at=meal.updated_at,
    )
