"""Pydantic schemas for API request/response models."""

from schemas.user import UserResponse, OnboardingResponse
from schemas.recipe_book import (
    RecipeBookCreate,
    RecipeBookUpdate,
    RecipeBookResponse,
    RecipeBookListResponse,
    RecipeBookDetailResponse,
    RecipeListItem,
)
from schemas.recipe import (
    RecipeIngredientInput,
    RecipeIngredientResponse,
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeListResponse,
)
from schemas.ingredient import (
    IngredientCreate,
    IngredientSearchItem,
    IngredientSearchResponse,
    IngredientResponse,
)

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
