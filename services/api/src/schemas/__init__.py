"""Pydantic schemas for API request/response models."""

from schemas.ingredient import (
    IngredientCreate,
    IngredientResponse,
    IngredientSearchItem,
    IngredientSearchResponse,
)
from schemas.recipe import (
    RecipeCreate,
    RecipeIngredientInput,
    RecipeIngredientResponse,
    RecipeListResponse,
    RecipeResponse,
    RecipeUpdate,
)
from schemas.recipe_book import (
    RecipeBookCreate,
    RecipeBookDetailResponse,
    RecipeBookListResponse,
    RecipeBookResponse,
    RecipeBookUpdate,
    RecipeListItem,
)
from schemas.user import OnboardingResponse, UserResponse

__all__ = [
    # User
    "UserResponse",
    "OnboardingResponse",
    # Recipe Book
    "RecipeBookCreate",
    "RecipeBookUpdate",
    "RecipeBookResponse",
    "RecipeBookListResponse",
    "RecipeBookDetailResponse",
    "RecipeListItem",
    # Recipe
    "RecipeIngredientInput",
    "RecipeIngredientResponse",
    "RecipeCreate",
    "RecipeUpdate",
    "RecipeResponse",
    "RecipeListResponse",
    # Ingredient
    "IngredientCreate",
    "IngredientSearchItem",
    "IngredientSearchResponse",
    "IngredientResponse",
]
