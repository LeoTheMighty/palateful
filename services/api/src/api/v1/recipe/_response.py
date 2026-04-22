"""Shared response shaping for Recipe endpoints.

rf-2 extracted this helper out of `GetRecipe.execute` so `toggle_favorite`
(and future recipe-mutation endpoints) can return the same shape without
duplicating the query pipeline. `GetRecipe` still owns the endpoint
contract — this module is an internal helper reused within the recipe
package.
"""

from decimal import Decimal

from utils.formatting import format_quantity
from utils.models.import_item import ImportItem
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_note import RecipeNote
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


def build_recipe_response(
    database,
    user: User,
    recipe: Recipe,
    *,
    can_edit: bool,
    is_favorite: bool | None = None,
    debug: bool = False,
):
    """Hydrate a Recipe row into a full `GetRecipe.Response`.

    When ``is_favorite`` is ``None`` the builder queries ``UserFavorite``
    for the current state. Mutation endpoints (e.g. toggle_favorite)
    that already know the post-mutation state should pass it explicitly
    — skipping the extra query and avoiding a mock-state foot-gun in
    unit tests that mock ``find_by``.

    Imports the Response classes lazily to avoid a circular import
    (`_response` <-> `get_recipe`).
    """
    # Local import — module cycle avoidance.
    from api.v1.recipe.get_recipe import GetRecipe  # noqa: PLC0415

    db = database.db

    steps = database.where(
        RecipeStep,
        asc="step_number",
        recipe_id=recipe.id,
    ).all()

    step_responses = [
        GetRecipe.StepResponse(
            id=str(step.id),
            step_number=step.step_number,
            instruction=step.instruction,
            active_time_minutes=step.active_time_minutes,
            timers=step.timers,
            wait_time_minutes=step.wait_time_minutes,
            wait_type=step.wait_type,
            can_prep_ahead=step.can_prep_ahead,
            is_optional=step.is_optional,
        )
        for step in steps
    ]

    recipe_ingredients = (
        db.query(RecipeIngredient, Ingredient)
        .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .filter(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.order_index)
        .all()
    )

    ingredient_responses = [
        GetRecipe.IngredientResponse(
            id=str(ri.ingredient_id),
            ingredient=GetRecipe.IngredientSummary(
                id=str(ing.id),
                canonical_name=ing.canonical_name,
            ),
            quantity_display=format_quantity(ri.quantity_display, ri.unit_display),
            unit_display=ri.unit_display,
            quantity_normalized=_as_decimal(ri.quantity_normalized),
            unit_normalized=ri.unit_normalized,
            notes=ri.notes,
            is_optional=ri.is_optional,
            order_index=ri.order_index,
        )
        for ri, ing in recipe_ingredients
    ]

    if is_favorite is None:
        favorite = database.find_by(
            UserFavorite,
            user_id=user.id,
            recipe_id=str(recipe.id),
        )
        resolved_is_favorite = favorite is not None
    else:
        resolved_is_favorite = is_favorite

    version_count = database.where(
        RecipeVersion,
        recipe_id=str(recipe.id),
    ).count()

    notes = database.where(
        RecipeNote,
        recipe_id=str(recipe.id),
        asc="created_at",
    ).all()

    note_responses = [
        GetRecipe.NoteResponse(
            id=str(n.id),
            body=n.body,
            created_by=str(n.created_by) if n.created_by else None,
            created_at=n.created_at,
        )
        for n in notes
    ]

    debug_payload: GetRecipe.DebugPayload | None = None
    if debug and user.is_admin:
        import_item = database.find_by(ImportItem, created_recipe_id=recipe.id)
        if import_item is not None:
            debug_payload = GetRecipe.DebugPayload(
                import_item_id=str(import_item.id),
                status=import_item.status,
                source_type=import_item.source_type,
                source_reference=import_item.source_reference,
                source_url=import_item.source_url,
                last_successful_stage=import_item.last_successful_stage,
                error_code=import_item.error_code,
                error_message=import_item.error_message,
                raw_data=import_item.raw_data,
                parsed_recipe=import_item.parsed_recipe,
                user_edits=import_item.user_edits,
            )

    return GetRecipe.Response(
        id=str(recipe.id),
        name=recipe.name,
        description=recipe.description,
        instructions=recipe.instructions,
        servings=recipe.servings,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        tags=recipe.tags or [],
        primary_vibe=recipe.primary_vibe,
        secondary_vibe=recipe.secondary_vibe,
        can_edit=can_edit,
        is_favorite=resolved_is_favorite,
        ingredients=ingredient_responses,
        steps=step_responses,
        notes=note_responses,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        version_count=version_count,
        forked_from_recipe_id=str(recipe.forked_from_recipe_id)
        if recipe.forked_from_recipe_id
        else None,
        forked_from_book_id=str(recipe.forked_from_book_id)
        if recipe.forked_from_book_id
        else None,
        forked_from_recipe_name=recipe.forked_from_recipe_name,
        forked_from_book_name=recipe.forked_from_book_name,
        inferred_fields=list(recipe.inferred_fields or []),
        debug=debug_payload,
    )


def _as_decimal(value) -> Decimal | None:  # pragma: no cover — defensive util, exercised only in rare edit paths
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
