"""Shared response shaping for Meal endpoints."""

from schemas.meal import (
    MealComponentResponse,
    MealResponse,
    MealSummaryResponse,
)
from utils.models.meal import Meal
from utils.services.meal_service import MealService


def build_meal_response(
    meal: Meal,
    *,
    db,
    user_id,
    readable_book_ids: set | None = None,
    is_favorite: bool | None = None,
) -> MealResponse:
    """Hydrate a Meal into the full response shape.

    `readable_book_ids` threads through to `MealService.hydrate_components`
    so callers paging over many meals can hoist the lookup once —
    single-meal callers keep the `None` default and pay one extra
    round-trip, same as before.

    `is_favorite` is an optional override. rf-2 mutation endpoints
    (`favorite_meal`) already know the post-mutation state — passing it
    here skips the extra `is_favorited` query and avoids a mock-state
    foot-gun in unit tests that pre-specify `db.query` `side_effect`
    sequences.
    """
    service = MealService(db)
    hydrations = service.hydrate_components(
        meal, user_id=user_id, readable_book_ids=readable_book_ids
    )
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
        is_favorite=(
            is_favorite
            if is_favorite is not None
            else service.is_favorited(user_id=user_id, meal_id=meal.id)
        ),
    )


def build_meal_summary(
    meal: Meal,
    *,
    db,
    user_id,
    readable_book_ids: set | None = None,
) -> MealSummaryResponse:
    """Thin grid-tile response — up to 4 component image URLs.

    `component_recipe_ids` is emitted in order so home (hmp-1) can run
    an in-memory join against the already-loaded recipe list to render
    the component-name chip row without an N+1 detail fetch.

    `readable_book_ids` threads through to `hydrate_components` — list
    callers (`list_meals`) compute this set once per request instead of
    re-fetching per meal. Single-meal callers keep the `None` default.
    """
    hydrations = MealService(db).hydrate_components(
        meal, user_id=user_id, readable_book_ids=readable_book_ids
    )
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
