"""Pydantic schemas for Meal endpoints.

Wire contract only — handlers translate to/from SQLAlchemy models. Kept
separate from `libraries/utils/utils/schemas/*` because the recipe/book
schemas have stayed co-located with their endpoints; Meal follows suit.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MealCreateRequest(BaseModel):
    """Body for POST /v1/recipe-books/{book_id}/meals."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    component_recipe_ids: list[str] = Field(..., min_length=2)

    @field_validator("component_recipe_ids")
    @classmethod
    def _reject_duplicates(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("component_recipe_ids must be unique")
        return v


class MealUpdateRequest(BaseModel):
    """Body for PATCH /v1/meals/{meal_id}. Name / description only."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class MealComponentAddRequest(BaseModel):
    """Body for POST /v1/meals/{meal_id}/recipes."""

    recipe_id: str
    order_index: int | None = None


class MealReorderRequest(BaseModel):
    """Body for POST /v1/meals/{meal_id}/reorder."""

    recipe_ids: list[str] = Field(..., min_length=2)

    @field_validator("recipe_ids")
    @classmethod
    def _reject_duplicates(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("recipe_ids must be unique")
        return v


class MealComponentResponse(BaseModel):
    """A single component on a Meal.

    `available=False` when the component's recipe is archived OR the user
    has lost read access to the recipe's book. Unavailable rows are
    hidden on read surfaces and surfaced on edit surfaces with Remove.
    """

    recipe_id: str
    name: str
    image_url: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    book_name: str | None = None
    order_index: int = 0
    available: bool = True
    last_known_name: str | None = None


class MealResponse(BaseModel):
    """Full Meal detail — hydrated components + metadata."""

    id: str
    name: str
    description: str | None = None
    recipe_book_id: str
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    components: list[MealComponentResponse] = []
    is_favorite: bool = False


class MealSummaryResponse(BaseModel):
    """Grid-tile-shaped response for list endpoints."""

    id: str
    name: str
    description: str | None = None
    recipe_book_id: str
    component_count: int
    component_image_urls: list[str] = []
    component_recipe_ids: list[str] = []
    archived_at: datetime | None = None
    updated_at: datetime


class MealListResponse(BaseModel):
    items: list[MealSummaryResponse] = []
    total: int = 0


class MealArchiveResponse(BaseModel):
    success: bool
    archived_at: datetime | None = None


class MealFavoriteResponse(BaseModel):
    is_favorite: bool


class ShareMealResponse(BaseModel):
    """Response for POST /v1/meals/{meal_id}/share — mirrors ShareRecipe."""

    token: str
    deep_link: str


class PublicMealComponent(BaseModel):
    """A single component on a public Meal page.

    Deliberately omits `recipe_id`, `order_index`, and `book_id` — a stranger
    holding the public link MUST NOT be able to probe private recipe UUIDs
    via a Meal share. `public_token` is populated iff the component recipe
    has its own public share_token AND is not archived.
    """

    name: str
    image_url: str | None = None
    has_public_token: bool
    public_token: str | None = None


class PublicMealResponse(BaseModel):
    """Unauthenticated read view of a shared Meal."""

    id: str
    name: str
    description: str | None = None
    recipe_book_name: str
    components: list[PublicMealComponent] = []
