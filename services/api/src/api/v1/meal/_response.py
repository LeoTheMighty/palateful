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
    hydrations = MealService(db).hydrate_components(meal, user_id=user_id)
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
    )


def build_meal_summary(meal: Meal, *, db, user_id) -> MealSummaryResponse:
    """Thin grid-tile response — up to 4 component image URLs."""
    hydrations = MealService(db).hydrate_components(meal, user_id=user_id)
    image_urls = [h.image_url for h in hydrations if h.available and h.image_url][:4]
    component_count = len(hydrations)
    return MealSummaryResponse(
        id=str(meal.id),
        name=meal.name,
        description=meal.description,
        recipe_book_id=str(meal.recipe_book_id),
        component_count=component_count,
        component_image_urls=image_urls,
        archived_at=meal.archived_at,
        updated_at=meal.updated_at,
    )
