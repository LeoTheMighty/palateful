"""Recipe CRUD tools with ingredient-name auto-resolution.

All tools wrap an existing `Endpoint` — no business logic lives here. The
one pattern that's MCP-specific is resolving ingredient names to IDs before
calling `CreateRecipe` / `UpdateRecipe`, so the user never has to know about
ingredient UUIDs.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from api.v1.ingredient.create_ingredient import CreateIngredient
from api.v1.ingredient.search_ingredients import SearchIngredients
from api.v1.recipe.create_recipe import CreateRecipe
from api.v1.recipe.delete_recipe import DeleteRecipe
from api.v1.recipe.fork_recipe import ForkRecipe
from api.v1.recipe.get_recipe import GetRecipe
from api.v1.recipe.list_favorites import ListFavorites
from api.v1.recipe.list_recipes import ListRecipes
from api.v1.recipe.toggle_favorite import ToggleFavorite
from api.v1.recipe.update_recipe import UpdateRecipe
from fastapi.encoders import jsonable_encoder
from mcp_server.auth import get_current_database, get_current_user
from mcp_server.server import call_endpoint, mcp
from utils.services.database import Database

INGREDIENT_MATCH_THRESHOLD = 0.85


def _resolve_ingredient(name: str, database: Database, user) -> str:
    """Resolve an ingredient name to a canonical Ingredient UUID.

    Fuzzy-search existing ingredients via pg_trgm similarity; if the top match
    is strong (>= 0.85) return its ID. Otherwise create a new Ingredient so
    the user never has to pick from a list.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Ingredient name cannot be empty")

    search = SearchIngredients(database=database, user=user).run(q=cleaned, limit=1)
    if search["success"]:
        items = (search.get("data") or {}).get("items") or []
        if items:
            top = items[0]
            similarity = getattr(top, "similarity", None)
            if similarity is None and isinstance(top, dict):
                similarity = top.get("similarity")
            ingredient_id = getattr(top, "id", None)
            if ingredient_id is None and isinstance(top, dict):
                ingredient_id = top.get("id")
            if similarity is not None and float(similarity) >= INGREDIENT_MATCH_THRESHOLD:
                return str(ingredient_id)

    create = CreateIngredient(database=database, user=user).run(
        params=CreateIngredient.Params(canonical_name=cleaned)
    )
    if not create["success"]:
        raise RuntimeError(create.get("error_message") or "Failed to create ingredient")
    new_id = (create.get("data") or {}).id if hasattr(create.get("data") or {}, "id") else None
    if new_id is None and isinstance(create.get("data"), dict):
        new_id = create["data"].get("id")
    if new_id is None:
        raise RuntimeError("CreateIngredient returned no id")
    return str(new_id)


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid quantity: {value!r}") from exc


def _require_default_book_id(user) -> str:
    book_id = getattr(user, "default_recipe_book_id", None)
    if not book_id:
        raise ValueError(
            "No book_id provided and user has no default recipe book — ask the user which book to use"
        )
    return str(book_id)


@mcp.tool()
def get_recipe(recipe_id: str) -> str:
    """Fetch a recipe's full details: ingredients with quantities, step-by-step
    instructions, notes, tags, vibes, prep and cook times, and whether it's
    favorited. Use this any time the user asks about a specific recipe, or
    before suggesting variations.
    """
    return call_endpoint(GetRecipe, recipe_id=recipe_id)


@mcp.tool()
def list_recipes(
    book_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
) -> str:
    """List recipes in a book. If `book_id` is omitted, uses the user's default
    recipe book. Pair with `search` for a quick name filter, or paginate with
    `limit`/`offset` to walk the full collection. For natural-language search
    across all books, prefer `search_recipes` instead.
    """
    user = get_current_user()
    resolved_book_id = book_id or _require_default_book_id(user)
    kwargs: dict[str, Any] = {
        "book_id": resolved_book_id,
        "limit": limit,
        "offset": offset,
    }
    if search is not None:
        kwargs["search"] = search
    return call_endpoint(ListRecipes, **kwargs)


@mcp.tool()
def create_recipe(
    name: str,
    ingredients: list[dict] | None = None,
    steps: list[dict] | None = None,
    description: str | None = None,
    servings: int | None = None,
    prep_time: int | None = None,
    cook_time: int | None = None,
    tags: list[str] | None = None,
    book_id: str | None = None,
) -> str:
    """Create a new recipe in the user's default book (or a specified `book_id`).

    Ingredients accept human names — no UUID required. Each entry is
    `{name, quantity, unit, notes?, is_optional?}`. Steps are
    `{instruction, active_time_minutes?, wait_time_minutes?}`. If an
    ingredient name doesn't closely match an existing one, a new ingredient
    is created automatically. Use this after `suggest_recipe` if the user
    wants to save the suggestion, or any time they dictate a recipe.
    """
    user = get_current_user()
    database = get_current_database()
    resolved_book_id = book_id or _require_default_book_id(user)

    ingredient_inputs: list[CreateRecipe.IngredientInput] = []
    for entry in ingredients or []:
        if not isinstance(entry, dict):
            raise ValueError("Each ingredient must be an object with name/quantity/unit")
        ing_name = entry.get("name") or entry.get("canonical_name")
        if not ing_name:
            raise ValueError("Each ingredient needs a `name`")
        quantity_raw = entry.get("quantity")
        if quantity_raw is None:
            raise ValueError(f"Ingredient '{ing_name}' is missing a quantity")
        unit = entry.get("unit")
        if not unit:
            raise ValueError(f"Ingredient '{ing_name}' is missing a unit")
        ingredient_id = _resolve_ingredient(ing_name, database, user)
        ingredient_inputs.append(
            CreateRecipe.IngredientInput(
                ingredient_id=ingredient_id,
                quantity=_to_decimal(quantity_raw),
                unit=unit,
                notes=entry.get("notes"),
                is_optional=bool(entry.get("is_optional", False)),
            )
        )

    step_inputs: list[CreateRecipe.StepInput] = []
    for idx, entry in enumerate(steps or []):
        if not isinstance(entry, dict):
            raise ValueError("Each step must be an object with at least `instruction`")
        instruction = entry.get("instruction")
        if not instruction:
            raise ValueError(f"Step {idx + 1} is missing an `instruction`")
        step_inputs.append(
            CreateRecipe.StepInput(
                step_number=entry.get("step_number"),
                instruction=instruction,
                active_time_minutes=entry.get("active_time_minutes"),
                timers=entry.get("timers"),
                wait_time_minutes=entry.get("wait_time_minutes"),
                wait_type=entry.get("wait_type"),
                can_prep_ahead=bool(entry.get("can_prep_ahead", False)),
                is_optional=bool(entry.get("is_optional", False)),
            )
        )

    params = CreateRecipe.Params(
        name=name,
        description=description,
        servings=servings,
        prep_time=prep_time,
        cook_time=cook_time,
        tags=tags or [],
        ingredients=ingredient_inputs,
        steps=step_inputs,
    )
    return call_endpoint(CreateRecipe, book_id=resolved_book_id, params=params)


@mcp.tool()
def update_recipe(
    recipe_id: str,
    name: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
    servings: int | None = None,
    prep_time: int | None = None,
    cook_time: int | None = None,
    tags: list[str] | None = None,
    ingredients: list[dict] | None = None,
    steps: list[dict] | None = None,
) -> str:
    """Update an existing recipe. Only fields you pass are modified (partial
    update). Replacing `ingredients` or `steps` replaces the full list — pass
    the whole set you want. Ingredient names auto-resolve the same way as in
    `create_recipe`.
    """
    user = get_current_user()
    database = get_current_database()

    params_kwargs: dict[str, Any] = {}
    if name is not None:
        params_kwargs["name"] = name
    if description is not None:
        params_kwargs["description"] = description
    if instructions is not None:
        params_kwargs["instructions"] = instructions
    if servings is not None:
        params_kwargs["servings"] = servings
    if prep_time is not None:
        params_kwargs["prep_time"] = prep_time
    if cook_time is not None:
        params_kwargs["cook_time"] = cook_time
    if tags is not None:
        params_kwargs["tags"] = tags

    if ingredients is not None:
        resolved: list[UpdateRecipe.IngredientInput] = []
        for entry in ingredients:
            if not isinstance(entry, dict):
                raise ValueError("Each ingredient must be an object")
            ing_name = entry.get("name") or entry.get("canonical_name")
            if not ing_name:
                raise ValueError("Each ingredient needs a `name`")
            if entry.get("quantity") is None:
                raise ValueError(f"Ingredient '{ing_name}' is missing a quantity")
            unit = entry.get("unit")
            if not unit:
                raise ValueError(f"Ingredient '{ing_name}' is missing a unit")
            ingredient_id = _resolve_ingredient(ing_name, database, user)
            resolved.append(
                UpdateRecipe.IngredientInput(
                    ingredient_id=ingredient_id,
                    quantity=_to_decimal(entry["quantity"]),
                    unit=unit,
                    notes=entry.get("notes"),
                    is_optional=bool(entry.get("is_optional", False)),
                )
            )
        params_kwargs["ingredients"] = resolved

    if steps is not None:
        resolved_steps: list[UpdateRecipe.StepInput] = []
        for idx, entry in enumerate(steps):
            if not isinstance(entry, dict):
                raise ValueError("Each step must be an object")
            instruction = entry.get("instruction")
            if not instruction:
                raise ValueError(f"Step {idx + 1} is missing `instruction`")
            resolved_steps.append(
                UpdateRecipe.StepInput(
                    step_number=entry.get("step_number"),
                    instruction=instruction,
                    active_time_minutes=entry.get("active_time_minutes"),
                    timers=entry.get("timers"),
                    wait_time_minutes=entry.get("wait_time_minutes"),
                    wait_type=entry.get("wait_type"),
                    can_prep_ahead=bool(entry.get("can_prep_ahead", False)),
                    is_optional=bool(entry.get("is_optional", False)),
                )
            )
        params_kwargs["steps"] = resolved_steps

    params = UpdateRecipe.Params(**params_kwargs)
    return call_endpoint(UpdateRecipe, recipe_id=recipe_id, params=params)


@mcp.tool()
def delete_recipe(recipe_id: str) -> str:
    """Archive (soft-delete) a recipe. The recipe is hidden from lists but can
    be restored later via the app. Use when the user says "delete", "archive",
    or "remove" a recipe.
    """
    return call_endpoint(DeleteRecipe, recipe_id=recipe_id)


@mcp.tool()
def toggle_favorite(recipe_id: str) -> str:
    """Toggle the favorite status on a recipe. Returns the new state so you
    can confirm "marked as favorite" or "removed from favorites".
    """
    return call_endpoint(ToggleFavorite, recipe_id=recipe_id)


@mcp.tool()
def list_favorites() -> str:
    """List every recipe the user has favorited, newest first. Great for
    "what are my favorites" or quick access when planning meals.
    """
    return call_endpoint(ListFavorites)


@mcp.tool()
def fork_recipe(recipe_id: str, destination_book_id: str | None = None) -> str:
    """Fork a recipe (typically a shared or public one) into a book the user
    owns, preserving lineage. Defaults to the user's default book.
    """
    user = get_current_user()
    dest = destination_book_id or _require_default_book_id(user)
    params = ForkRecipe.Params(destination_book_id=dest)
    return call_endpoint(ForkRecipe, recipe_id=recipe_id, params=params)


# Used by the resolver's unit tests — exposed so tests can monkeypatch.
__all__ = [
    "INGREDIENT_MATCH_THRESHOLD",
    "_resolve_ingredient",
    "create_recipe",
    "delete_recipe",
    "fork_recipe",
    "get_recipe",
    "jsonable_encoder",
    "json",
    "list_favorites",
    "list_recipes",
    "toggle_favorite",
    "update_recipe",
]
