"""Get recipe endpoint."""

import os
from datetime import datetime
from decimal import Decimal

from api.v1.recipe._response import build_recipe_response
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

# ffm-9a: fields the caller can toggle on/off via ``?include=...``.
# Every value is mapped to the concrete response key(s) that get
# dropped when the value is absent from the include list. Keys NOT
# listed here are always present (id, name, description, etc.).
_INCLUDABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "ingredients": ("ingredients",),
    "steps": ("steps",),
    # `notes` is the on-the-wire name for "comments" in the PRD; the
    # include alias matches the epic spec so client code reads
    # naturally.
    "comments": ("notes",),
    # `versions` gates the count field today; when a future
    # `versions` array is added it'll drop in here too.
    "versions": ("version_count",),
}

_DEFAULT_INCLUDE = frozenset(_INCLUDABLE_FIELDS.keys())

# ffm-9b: when no ``?include=`` is supplied, what should the default
# shape be?
#
# - With the env var UNSET / false (the initial safety-default), the
#   response keeps the full ffm-9a shape — every gated field present.
#   Old clients that still rely on ``versions`` / ``comments`` being
#   at the root won't notice ffm-9a/9b landing.
# - Once Flutter builds have shipped with ``?include=ingredients,
#   steps`` wired on the detail screen and dashboards confirm zero
#   upstream consumers depend on the full shape, set
#   ``RECIPES_LEAN_DEFAULT=true`` via ECS task-def. The default then
#   drops to the lean `ingredients,steps` subset — heavy `versions`
#   + `comments` fields are absent unless the caller opts in.
# - Env-var flip is the one-line rollback: change the task-def, no
#   code change, no re-deploy.
_LEAN_INCLUDE_ALIASES = frozenset({"ingredients", "steps"})


def _lean_default_enabled() -> bool:
    """Read the env-var flag. Re-checked per request so a task-def
    flip takes effect without a container recycle."""
    return os.environ.get("RECIPES_LEAN_DEFAULT", "").lower() == "true"


class GetRecipe(Endpoint):
    """Get recipe details by ID."""

    def execute(
        self,
        recipe_id: str,
        debug: bool = False,
        include: str | None = None,
    ):
        """
        Get recipe details including ingredients.

        Args:
            recipe_id: The recipe's ID
            debug: When True (and caller is admin), attach the
                source import_item diagnostics blob.
            include: ffm-9a optional CSV filter. When ``None``
                (default) every field is included — today's shape
                stays bit-identical for old clients. When supplied,
                only the named fields are present in the response
                (unknown values are silently ignored; unknown-in-
                both-directions is the safest no-op). Omitted
                fields are ABSENT from the JSON, not null.
        """
        user: User = self.user

        # Get recipe
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Check access via recipe book
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED
            )

        response_model = build_recipe_response(
            self.database,
            user,
            recipe,
            can_edit=membership.role in ("owner", "editor"),
            debug=debug,
        )

        if include is None:
            # ffm-9b: when the lean-default flag is OFF (initial safe
            # state, pre-flip), fall back to ffm-9a's full-shape
            # default. When the flag is ON, treat the no-include case
            # as if the caller had asked for the lean subset.
            if not _lean_default_enabled():
                return success(data=response_model)
            known_requested = _LEAN_INCLUDE_ALIASES
        else:
            # Parse the include CSV. Unknown values are dropped on
            # the floor — easier than raising 400 when a client
            # sends a new-world alias against an old server.
            requested = {
                s.strip() for s in include.split(",") if s.strip()
            }
            known_requested = requested & _DEFAULT_INCLUDE

        # Build a dict and strip the gated fields the caller didn't
        # ask for. Using a dict here (instead of returning the
        # Response model) is the only way to truly OMIT fields under
        # the existing ``CustomJSONResponse`` encoder — a None-valued
        # Pydantic field still serializes as ``null``.
        payload = response_model.model_dump()
        for alias, keys in _INCLUDABLE_FIELDS.items():
            if alias in known_requested:
                continue
            for key in keys:
                payload.pop(key, None)

        return success(data=payload)

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "GetRecipe.IngredientSummary"
        quantity_display: str
        unit_display: str
        quantity_normalized: Decimal | None = None
        unit_normalized: str | None = None
        notes: str | None = None
        is_optional: bool = False
        order_index: int = 0

    class StepResponse(BaseModel):
        id: str
        step_number: int
        instruction: str
        active_time_minutes: int | None = None
        timers: list[dict] | None = None
        wait_time_minutes: int | None = None
        wait_type: str | None = None
        can_prep_ahead: bool = False
        is_optional: bool = False

    class NoteResponse(BaseModel):
        id: str
        body: str
        created_by: str | None = None
        created_at: datetime

    class DebugPayload(BaseModel):
        import_item_id: str
        status: str
        source_type: str
        source_reference: str | None = None
        source_url: str | None = None
        last_successful_stage: str | None = None
        error_code: str | None = None
        error_message: str | None = None
        raw_data: dict | None = None
        parsed_recipe: dict | None = None
        user_edits: dict | None = None

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        instructions: str | None = None
        servings: int = 1
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None
        source_url: str | None = None
        tags: list[str] = []
        primary_vibe: str | None = None
        secondary_vibe: str | None = None
        can_edit: bool = False
        is_favorite: bool = False
        ingredients: list["GetRecipe.IngredientResponse"] = []
        steps: list["GetRecipe.StepResponse"] = []
        notes: list["GetRecipe.NoteResponse"] = []
        created_at: datetime
        updated_at: datetime
        version_count: int = 0
        forked_from_recipe_id: str | None = None
        forked_from_book_id: str | None = None
        forked_from_recipe_name: str | None = None
        forked_from_book_name: str | None = None
        inferred_fields: list[str] = []
        debug: "GetRecipe.DebugPayload | None" = None
