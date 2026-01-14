# Palateful MVP Implementation Guide

> **Last Updated:** 2025-01-10
> **Status:** Planning Complete - Ready for Implementation

## Table of Contents

1. [MVP Overview](#mvp-overview)
2. [User Experience](#user-experience)
3. [Technical Architecture](#technical-architecture)
4. [Database Schema](#database-schema)
5. [API Endpoints Reference](#api-endpoints-reference)
6. [Implementation Details](#implementation-details)
7. [Error Codes](#error-codes)
8. [Testing Guide](#testing-guide)

---

## MVP Overview

### Core Features

The MVP delivers a recipe book application with these capabilities:

| Feature | Description |
|---------|-------------|
| **Auth0 Sign-In** | Secure authentication via Auth0 with JWT tokens |
| **Recipe Books** | Create, view, update, delete recipe book collections |
| **Recipes** | Full CRUD for recipes with structured ingredients |
| **Ingredient Deduplication** | Fuzzy search to suggest existing ingredients before creating new ones |
| **Cooking View** | Scrollable recipe view optimized for cooking |

### Out of Scope (Post-MVP)

- Pantry/inventory tracking
- AI chat assistant
- Celery background workers
- OCR recipe import
- Recipe sharing/collaboration
- Cooking logs

---

## User Experience

### Authentication Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Landing Page   │────▶│  Auth0 Login    │────▶│  Dashboard      │
│                 │     │                 │     │  (Recipe Books) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. User lands on app, clicks "Sign In"
2. Redirected to Auth0 hosted login page
3. After authentication, redirected back with JWT token
4. Token stored in app, used for all API requests
5. On first login, user record created automatically

### Recipe Book Management

```
Dashboard
├── "My Recipe Books" header
├── [+ Create Recipe Book] button
└── Recipe Book Cards
    ├── Book Name
    ├── Recipe Count
    ├── Last Updated
    └── [Open] [Edit] [Delete] actions
```

### Recipe Creation Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│ Recipe Book  │────▶│ New Recipe   │────▶│ Add          │
│ Detail View  │     │ Form         │     │ Ingredients  │
│              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
                     ┌──────────────────────────────────────┐
                     │ Ingredient Search Autocomplete       │
                     ├──────────────────────────────────────┤
                     │ Type: "tomatoe"                      │
                     │                                      │
                     │ Suggestions:                         │
                     │ ├── tomato (98% match) ◀── fuzzy    │
                     │ ├── cherry tomato (85%)              │
                     │ └── [+ Create "tomatoe"] ◀── new     │
                     └──────────────────────────────────────┘
```

**Ingredient Deduplication Logic:**
1. User types ingredient name in autocomplete field
2. Frontend debounces input (300ms), calls `/v1/ingredients/search?q={query}`
3. Backend uses PostgreSQL `search_ingredients_fuzzy()` function
4. Returns top 10 matches with similarity scores
5. User selects existing ingredient OR clicks "Create new"
6. If creating new: POST `/v1/ingredients` with `pending_review: true`

### Cooking View (Scrollable)

```
┌────────────────────────────────────────┐
│ ◀ Back                    [Scale: 1x]  │
├────────────────────────────────────────┤
│                                        │
│ Simple Tomato Pasta                    │
│                                        │
│ Prep: 10 min  Cook: 20 min  Serves: 4  │
│                                        │
├────────────────────────────────────────┤
│ INGREDIENTS                            │
│ ─────────────────────────────────────  │
│ □ 400g pasta                           │
│ □ 2 cans crushed tomatoes              │
│ □ 3 cloves garlic, minced              │
│ □ 2 tbsp olive oil                     │
│ □ Salt and pepper to taste             │
│                                        │
├────────────────────────────────────────┤
│ INSTRUCTIONS                           │
│ ─────────────────────────────────────  │
│                                        │
│ 1. Bring a large pot of salted water  │
│    to a boil. Cook pasta according to │
│    package directions.                 │
│                                        │
│ 2. Meanwhile, heat olive oil in a     │
│    large pan over medium heat. Add    │
│    garlic and cook until fragrant.    │
│                                        │
│ 3. Add crushed tomatoes, season with  │
│    salt and pepper. Simmer for 15     │
│    minutes.                            │
│                                        │
│ 4. Drain pasta and toss with sauce.   │
│    Serve immediately.                  │
│                                        │
└────────────────────────────────────────┘
```

**Key UI Elements:**
- Large, readable text
- Checkable ingredient list (local state only for MVP)
- Scrollable single-page layout
- Optional serving size scaling (frontend calculation)

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Flutter App                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Auth    │  │  Recipe  │  │  Recipe  │  │  Ingredient      │ │
│  │  BLoC    │  │  Book    │  │  BLoC    │  │  Search BLoC     │ │
│  │          │  │  BLoC    │  │          │  │                  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
│       │             │             │                  │           │
│       └─────────────┴──────┬──────┴──────────────────┘           │
│                            │                                      │
│                    ┌───────▼───────┐                             │
│                    │   API Client  │                             │
│                    │   (Dio)       │                             │
│                    └───────┬───────┘                             │
└────────────────────────────┼─────────────────────────────────────┘
                             │ HTTPS + JWT
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI                                   │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Auth0       │  │ Routers     │  │ Endpoints               │  │
│  │ Middleware  │  │ (v1)        │  │ (Business Logic)        │  │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │
│         │                │                       │                │
│         └────────────────┴───────────┬───────────┘                │
│                                      │                            │
│                          ┌───────────▼───────────┐               │
│                          │   Database Helper     │               │
│                          │   (SQLAlchemy 2.0)    │               │
│                          └───────────┬───────────┘               │
└──────────────────────────────────────┼───────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐│
│  │ pg_trgm       │  │ pgvector      │  │ Custom Functions      ││
│  │ (fuzzy search)│  │ (embeddings)  │  │ - search_fuzzy        ││
│  └───────────────┘  └───────────────┘  │ - search_semantic     ││
│                                        └───────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
palateful/
├── services/
│   └── api/
│       └── src/
│           ├── main.py                    # FastAPI app
│           ├── config.py                  # Settings
│           ├── dependencies.py            # DI (auth, db)
│           ├── schemas/                   # Pydantic models
│           │   ├── __init__.py
│           │   ├── user.py
│           │   ├── recipe_book.py
│           │   ├── recipe.py
│           │   └── ingredient.py
│           ├── routers/
│           │   ├── v1_router.py           # Aggregates all v1 routers
│           │   └── v1/
│           │       ├── user_router.py
│           │       ├── recipe_book_router.py
│           │       ├── recipe_router.py
│           │       └── ingredient_router.py
│           └── api/
│               └── v1/
│                   ├── user/
│                   │   ├── get_me.py
│                   │   └── complete_onboarding.py
│                   ├── recipe_book/
│                   │   ├── list_recipe_books.py
│                   │   ├── create_recipe_book.py
│                   │   ├── get_recipe_book.py
│                   │   ├── update_recipe_book.py
│                   │   └── delete_recipe_book.py
│                   ├── recipe/
│                   │   ├── list_recipes.py
│                   │   ├── create_recipe.py
│                   │   ├── get_recipe.py
│                   │   ├── update_recipe.py
│                   │   └── delete_recipe.py
│                   └── ingredient/
│                       ├── search_ingredients.py
│                       ├── create_ingredient.py
│                       └── get_ingredient.py
│
└── libraries/
    └── utils/
        └── utils/
            ├── classes/
            │   ├── base_enum.py           # BaseEnum class
            │   └── error_code.py          # ErrorCode enum
            ├── api/
            │   ├── endpoint.py            # Endpoint base class
            │   └── api_exception.py       # APIException class
            ├── services/
            │   ├── auth0.py               # Auth0 JWT verification
            │   └── database.py            # Database helper
            └── models/
                ├── user.py
                ├── recipe.py              # RecipeBook, RecipeBookUser, Recipe, RecipeIngredient
                ├── ingredient.py          # Ingredient, IngredientSubstitution
                └── ...
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│   ┌────────────┐         ┌──────────────────┐                    │
│   │   User     │◄────────┤ RecipeBookUser   │                    │
│   │            │   N:M   │ (role, user_id,  │                    │
│   │ id         │         │  recipe_book_id) │                    │
│   │ auth0_id   │         └────────┬─────────┘                    │
│   │ email      │                  │                               │
│   │ name       │                  │                               │
│   └────────────┘                  ▼                               │
│                          ┌──────────────────┐                    │
│                          │   RecipeBook     │                    │
│                          │                  │                    │
│                          │ id               │                    │
│                          │ name             │                    │
│                          │ description      │                    │
│                          │ is_public        │                    │
│                          └────────┬─────────┘                    │
│                                   │ 1:N                          │
│                                   ▼                               │
│                          ┌──────────────────┐                    │
│                          │   Recipe         │                    │
│                          │                  │                    │
│                          │ id               │                    │
│                          │ name             │                    │
│                          │ description      │                    │
│                          │ instructions     │                    │
│                          │ servings         │                    │
│                          │ prep_time        │                    │
│                          │ cook_time        │                    │
│                          │ image_url        │                    │
│                          │ source_url       │                    │
│                          │ recipe_book_id   │                    │
│                          └────────┬─────────┘                    │
│                                   │ 1:N                          │
│                                   ▼                               │
│                          ┌──────────────────┐                    │
│                          │ RecipeIngredient │                    │
│                          │                  │                    │
│                          │ id               │◄──────────────┐    │
│                          │ quantity_display │               │    │
│                          │ unit_display     │               │    │
│                          │ notes            │               │    │
│                          │ is_optional      │     ┌─────────┴─┐  │
│                          │ order_index      │     │Ingredient │  │
│                          │ recipe_id        │     │           │  │
│                          │ ingredient_id    │────▶│ id        │  │
│                          └──────────────────┘     │ canon_name│  │
│                                                   │ aliases[] │  │
│                                                   │ category  │  │
│                                                   │ embedding │  │
│                                                   └───────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Tables for MVP

#### users
```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,           -- CUID
    auth0_id VARCHAR UNIQUE NOT NULL, -- Auth0 subject ID
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR,
    picture VARCHAR,
    email_verified BOOLEAN DEFAULT false,
    has_completed_onboarding BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### recipe_books
```sql
CREATE TABLE recipe_books (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### recipe_book_users
```sql
CREATE TABLE recipe_book_users (
    id VARCHAR PRIMARY KEY,
    role VARCHAR DEFAULT 'member',    -- 'owner', 'editor', 'viewer'
    user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
    recipe_book_id VARCHAR REFERENCES recipe_books(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, recipe_book_id)
);
```

#### recipes
```sql
CREATE TABLE recipes (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    instructions TEXT,                 -- Markdown or plain text
    servings INTEGER DEFAULT 1,
    prep_time INTEGER,                 -- Minutes
    cook_time INTEGER,                 -- Minutes
    image_url VARCHAR,
    source_url VARCHAR,
    recipe_book_id VARCHAR REFERENCES recipe_books(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### ingredients
```sql
CREATE TABLE ingredients (
    id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR UNIQUE NOT NULL,
    aliases TEXT[] DEFAULT '{}',
    category VARCHAR,                  -- 'produce', 'dairy', 'protein', etc.
    flavor_profile TEXT[] DEFAULT '{}',
    default_unit VARCHAR,
    is_canonical BOOLEAN DEFAULT true,
    pending_review BOOLEAN DEFAULT false,
    image_url VARCHAR,
    submitted_by_id VARCHAR REFERENCES users(id),
    parent_id VARCHAR REFERENCES ingredients(id),
    embedding VECTOR(384),             -- Semantic search
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Fuzzy search index
CREATE INDEX idx_ingredients_canonical_name_trgm
ON ingredients USING gin (canonical_name gin_trgm_ops);

-- Vector search index
CREATE INDEX idx_ingredients_embedding
ON ingredients USING hnsw (embedding vector_cosine_ops);
```

#### recipe_ingredients
```sql
CREATE TABLE recipe_ingredients (
    id VARCHAR PRIMARY KEY,
    quantity_display NUMERIC(10,3) NOT NULL,  -- User-entered (e.g., "1.5")
    unit_display VARCHAR NOT NULL,            -- User-entered (e.g., "cups")
    quantity_normalized NUMERIC(10,3) NOT NULL,
    unit_normalized VARCHAR NOT NULL,
    notes VARCHAR,                            -- "finely chopped", "room temp"
    is_optional BOOLEAN DEFAULT false,
    order_index INTEGER DEFAULT 0,
    recipe_id VARCHAR REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id VARCHAR REFERENCES ingredients(id),
    UNIQUE(recipe_id, ingredient_id)
);
```

---

## API Endpoints Reference

### Authentication

All endpoints except ingredient search require authentication.

**Header:**
```
Authorization: Bearer <jwt_token>
```

**Token Claims (from Auth0):**
```json
{
  "sub": "auth0|123456789",
  "email": "user@example.com",
  "email_verified": true,
  "name": "John Doe",
  "picture": "https://..."
}
```

### User Endpoints

#### GET /v1/users/me

Get current authenticated user.

**Response 200:**
```json
{
  "id": "clz123abc",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://...",
  "has_completed_onboarding": true,
  "created_at": "2025-01-10T12:00:00Z"
}
```

#### POST /v1/users/me/complete-onboarding

Mark onboarding as complete.

**Response 200:**
```json
{
  "success": true
}
```

### Recipe Book Endpoints

#### GET /v1/recipe-books

List user's recipe books.

**Query Parameters:**
- `limit` (int, default 20): Max results
- `offset` (int, default 0): Pagination offset

**Response 200:**
```json
{
  "items": [
    {
      "id": "clz123abc",
      "name": "Family Recipes",
      "description": "Recipes from grandma",
      "recipe_count": 15,
      "created_at": "2025-01-10T12:00:00Z",
      "updated_at": "2025-01-10T12:00:00Z"
    }
  ],
  "total": 3,
  "limit": 20,
  "offset": 0
}
```

#### POST /v1/recipe-books

Create a new recipe book.

**Request:**
```json
{
  "name": "Italian Classics",
  "description": "Traditional Italian recipes"
}
```

**Response 201:**
```json
{
  "id": "clz456def",
  "name": "Italian Classics",
  "description": "Traditional Italian recipes",
  "recipe_count": 0,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z"
}
```

#### GET /v1/recipe-books/{id}

Get recipe book details.

**Response 200:**
```json
{
  "id": "clz123abc",
  "name": "Family Recipes",
  "description": "Recipes from grandma",
  "recipe_count": 15,
  "recipes": [
    {
      "id": "clz789ghi",
      "name": "Grandma's Pie",
      "prep_time": 30,
      "cook_time": 45
    }
  ],
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z"
}
```

#### PUT /v1/recipe-books/{id}

Update a recipe book.

**Request:**
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

**Response 200:**
```json
{
  "id": "clz123abc",
  "name": "Updated Name",
  "description": "Updated description",
  "recipe_count": 15,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:30:00Z"
}
```

#### DELETE /v1/recipe-books/{id}

Delete a recipe book and all its recipes.

**Response 204:** No content

### Recipe Endpoints

#### GET /v1/recipe-books/{book_id}/recipes

List recipes in a book.

**Query Parameters:**
- `limit` (int, default 20): Max results
- `offset` (int, default 0): Pagination offset
- `search` (str, optional): Search by name

**Response 200:**
```json
{
  "items": [
    {
      "id": "clz789ghi",
      "name": "Spaghetti Carbonara",
      "description": "Classic Roman pasta",
      "prep_time": 15,
      "cook_time": 20,
      "servings": 4,
      "image_url": null,
      "created_at": "2025-01-10T12:00:00Z"
    }
  ],
  "total": 15,
  "limit": 20,
  "offset": 0
}
```

#### POST /v1/recipe-books/{book_id}/recipes

Create a new recipe.

**Request:**
```json
{
  "name": "Spaghetti Carbonara",
  "description": "Classic Roman pasta dish",
  "instructions": "1. Cook pasta...\n2. Fry guanciale...",
  "servings": 4,
  "prep_time": 15,
  "cook_time": 20,
  "ingredients": [
    {
      "ingredient_id": "clz_pasta",
      "quantity": 400,
      "unit": "g",
      "notes": null,
      "is_optional": false
    },
    {
      "ingredient_id": "clz_guanciale",
      "quantity": 200,
      "unit": "g",
      "notes": "or pancetta",
      "is_optional": false
    },
    {
      "ingredient_id": "clz_egg",
      "quantity": 4,
      "unit": "count",
      "notes": "yolks only",
      "is_optional": false
    },
    {
      "ingredient_id": "clz_pecorino",
      "quantity": 100,
      "unit": "g",
      "notes": "freshly grated",
      "is_optional": false
    }
  ]
}
```

**Response 201:**
```json
{
  "id": "clz789ghi",
  "name": "Spaghetti Carbonara",
  "description": "Classic Roman pasta dish",
  "instructions": "1. Cook pasta...\n2. Fry guanciale...",
  "servings": 4,
  "prep_time": 15,
  "cook_time": 20,
  "image_url": null,
  "source_url": null,
  "ingredients": [
    {
      "id": "clz_ri_1",
      "ingredient": {
        "id": "clz_pasta",
        "canonical_name": "pasta",
        "category": "pantry"
      },
      "quantity_display": 400,
      "unit_display": "g",
      "notes": null,
      "is_optional": false,
      "order_index": 0
    }
  ],
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z"
}
```

#### GET /v1/recipes/{id}

Get recipe details (cooking view).

**Response 200:** Same as POST response above

#### PUT /v1/recipes/{id}

Update a recipe.

**Request:** Same structure as POST

**Response 200:** Updated recipe

#### DELETE /v1/recipes/{id}

Delete a recipe.

**Response 204:** No content

### Ingredient Endpoints

#### GET /v1/ingredients/search

Search for ingredients (fuzzy match).

**Query Parameters:**
- `q` (str, required): Search query (min 2 chars)
- `limit` (int, default 10): Max results

**Response 200:**
```json
{
  "items": [
    {
      "id": "clz_tomato",
      "canonical_name": "tomato",
      "category": "produce",
      "similarity": 0.95
    },
    {
      "id": "clz_cherry_tomato",
      "canonical_name": "cherry tomato",
      "category": "produce",
      "similarity": 0.78
    }
  ]
}
```

**Note:** This endpoint does NOT require authentication to allow ingredient autocomplete before user is fully logged in.

#### POST /v1/ingredients

Create a new ingredient.

**Request:**
```json
{
  "canonical_name": "guanciale",
  "category": "protein",
  "default_unit": "g"
}
```

**Response 201:**
```json
{
  "id": "clz_guanciale",
  "canonical_name": "guanciale",
  "category": "protein",
  "default_unit": "g",
  "pending_review": true,
  "created_at": "2025-01-10T12:00:00Z"
}
```

**Note:** New ingredients are created with `pending_review: true` for later admin review.

#### GET /v1/ingredients/{id}

Get ingredient details.

**Response 200:**
```json
{
  "id": "clz_tomato",
  "canonical_name": "tomato",
  "aliases": ["tomatoes", "roma tomato"],
  "category": "produce",
  "flavor_profile": ["acidic", "sweet"],
  "default_unit": "count",
  "is_canonical": true,
  "pending_review": false
}
```

---

## Implementation Details

### Phase 1: Foundation Cleanup

#### 1.1 Create BaseEnum Class

**File:** `libraries/utils/utils/classes/base_enum.py`

```python
from enum import Enum


class BaseEnum(Enum):
    """Base enum class with utility methods."""

    @classmethod
    def from_value(cls, value: int) -> "BaseEnum":
        """Get enum member by value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No {cls.__name__} member with value {value}")

    @classmethod
    def values(cls) -> list[int]:
        """Get all enum values."""
        return [member.value for member in cls]

    @classmethod
    def names(cls) -> list[str]:
        """Get all enum names."""
        return [member.name for member in cls]
```

#### 1.2 Update ErrorCode

**File:** `libraries/utils/utils/classes/error_code.py`

```python
from enum import unique
from utils.classes.base_enum import BaseEnum


@unique
class ErrorCode(BaseEnum):
    """Enum for all possible error codes."""

    # General errors (1-99)
    INTERNAL_ERROR = 1
    INVALID_REQUEST = 2
    INVALID_ENDPOINT_RESULT = 3
    UNAUTHORIZED = 4
    FORBIDDEN = 5

    # Auth errors (10-19)
    INVALID_TOKEN = 10
    TOKEN_EXPIRED = 11
    USER_NOT_FOUND = 12

    # Recipe Book errors (100-109)
    RECIPE_BOOK_NOT_FOUND = 100
    RECIPE_BOOK_ACCESS_DENIED = 101
    DUPLICATE_RECIPE_BOOK_NAME = 102

    # Recipe errors (110-119)
    RECIPE_NOT_FOUND = 110
    RECIPE_ACCESS_DENIED = 111
    DUPLICATE_RECIPE_NAME = 112

    # Ingredient errors (120-129)
    INGREDIENT_NOT_FOUND = 120
    DUPLICATE_INGREDIENT = 121
    INVALID_INGREDIENT_QUANTITY = 122

    # Database errors (200-209)
    DB_ROLLBACK_ERROR = 200
    DATABASE_LOCK_ERROR = 201
```

#### 1.3 Update APIException

**File:** `libraries/utils/utils/api/api_exception.py`

```python
from fastapi import HTTPException
from utils.classes.error_code import ErrorCode


class APIException(HTTPException):
    """Custom exception with error codes."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code.value

    def __reduce__(self):
        return self.__class__, (
            self.status_code,
            self.detail,
            ErrorCode.from_value(self.code)
        )

    def __str__(self):
        return f"APIException(code={self.code}): {self.detail}"
```

#### 1.4 Update Endpoint

**File:** `libraries/utils/utils/api/endpoint.py`

```python
import json
import logging
import typing
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from utils.classes.error_code import ErrorCode
from utils.api.api_exception import APIException
from utils.services.helpers.encoder import CustomEncoder

logger = logging.getLogger(__name__)

# ... rest of the file with imports fixed
```

### Phase 2: Authentication

#### 2.1 Auth0 Verifier

**File:** `libraries/utils/utils/services/auth0.py`

```python
import httpx
from functools import lru_cache
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from typing import Optional

from utils.api.api_exception import APIException
from utils.classes.error_code import ErrorCode


class Auth0Verifier:
    """Verify Auth0 JWT tokens."""

    def __init__(self, domain: str, audience: str):
        self.domain = domain
        self.audience = audience
        self.algorithms = ["RS256"]
        self._jwks: Optional[dict] = None

    async def _get_jwks(self) -> dict:
        """Fetch JWKS from Auth0 (cached)."""
        if self._jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.domain}/.well-known/jwks.json"
                )
                response.raise_for_status()
                self._jwks = response.json()
        return self._jwks

    async def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return claims.

        Raises:
            APIException: If token is invalid or expired
        """
        try:
            jwks = await self._get_jwks()
            unverified_header = jwt.get_unverified_header(token)

            # Find the signing key
            rsa_key = {}
            for key in jwks.get("keys", []):
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break

            if not rsa_key:
                raise APIException(
                    status_code=401,
                    detail="Unable to find appropriate key",
                    code=ErrorCode.INVALID_TOKEN
                )

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=f"https://{self.domain}/"
            )

            return payload

        except ExpiredSignatureError:
            raise APIException(
                status_code=401,
                detail="Token has expired",
                code=ErrorCode.TOKEN_EXPIRED
            )
        except JWTError as e:
            raise APIException(
                status_code=401,
                detail=f"Invalid token: {str(e)}",
                code=ErrorCode.INVALID_TOKEN
            )


@lru_cache()
def get_auth0_verifier() -> Auth0Verifier:
    """Get cached Auth0 verifier instance."""
    from utils.config import settings
    return Auth0Verifier(
        domain=settings.auth0_domain,
        audience=settings.auth0_audience
    )
```

#### 2.2 FastAPI Dependencies

**File:** `services/api/src/dependencies.py`

```python
from typing import Annotated
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from utils.services.database import Database
from utils.services.auth0 import get_auth0_verifier
from utils.api.api_exception import APIException
from utils.classes.error_code import ErrorCode
from utils.models import User

from src.db import SessionLocal


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database():
    """Get Database helper."""
    database = Database()
    try:
        yield database
    finally:
        database.close()


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    database: Database = Depends(get_database)
) -> User:
    """
    Verify JWT token and return current user.
    Creates user if first login.
    """
    # Extract token from "Bearer <token>"
    if not authorization.startswith("Bearer "):
        raise APIException(
            status_code=401,
            detail="Invalid authorization header",
            code=ErrorCode.INVALID_TOKEN
        )

    token = authorization[7:]  # Remove "Bearer "

    # Verify token
    verifier = get_auth0_verifier()
    claims = await verifier.verify_token(token)

    # Get or create user
    auth0_id = claims["sub"]
    user = database.find_by(User, auth0_id=auth0_id)

    if user is None:
        # First login - create user
        from cuid2 import cuid_wrapper
        cuid = cuid_wrapper()

        user = User(
            id=cuid(),
            auth0_id=auth0_id,
            email=claims.get("email", ""),
            name=claims.get("name"),
            picture=claims.get("picture"),
            email_verified=claims.get("email_verified", False)
        )
        database.create(user)

    return user


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
Db = Annotated[Database, Depends(get_database)]
```

### Phase 3: Endpoint Examples

#### Create Recipe Book Endpoint

**File:** `services/api/src/api/v1/recipe_book/create_recipe_book.py`

```python
from pydantic import BaseModel
from cuid2 import cuid_wrapper

from utils.api.endpoint import Endpoint, success
from utils.api.api_exception import APIException
from utils.classes.error_code import ErrorCode
from utils.models import RecipeBook, RecipeBookUser, User


cuid = cuid_wrapper()


class CreateRecipeBook(Endpoint):
    """Create a new recipe book."""

    def execute(self, params: "CreateRecipeBook.Params", user: User):
        # Create recipe book
        recipe_book = RecipeBook(
            id=cuid(),
            name=params.name,
            description=params.description
        )
        self.database.create(recipe_book)

        # Create ownership relationship
        membership = RecipeBookUser(
            id=cuid(),
            user_id=user.id,
            recipe_book_id=recipe_book.id,
            role="owner"
        )
        self.database.create(membership)

        return success(
            data=CreateRecipeBook.Response(
                id=recipe_book.id,
                name=recipe_book.name,
                description=recipe_book.description,
                recipe_count=0,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            ),
            status=201
        )

    class Params(BaseModel):
        name: str
        description: str | None = None

    class Response(BaseModel):
        id: str
        name: str
        description: str | None
        recipe_count: int
        created_at: datetime
        updated_at: datetime
```

#### Search Ingredients Endpoint

**File:** `services/api/src/api/v1/ingredient/search_ingredients.py`

```python
from pydantic import BaseModel
from sqlalchemy import text

from utils.api.endpoint import Endpoint, success


class SearchIngredients(Endpoint):
    """Search ingredients using fuzzy matching."""

    def execute(self, q: str, limit: int = 10):
        # Use PostgreSQL fuzzy search function
        result = self.db.execute(
            text("""
                SELECT id, canonical_name, category, best_similarity as similarity
                FROM search_ingredients_fuzzy(:query, 0.3, :limit)
            """),
            {"query": q, "limit": limit}
        )

        items = [
            SearchIngredients.IngredientMatch(
                id=row.id,
                canonical_name=row.canonical_name,
                category=row.category,
                similarity=row.similarity
            )
            for row in result
        ]

        return success(data={"items": items})

    class IngredientMatch(BaseModel):
        id: str
        canonical_name: str
        category: str | None
        similarity: float

    class Response(BaseModel):
        items: list["SearchIngredients.IngredientMatch"]
```

### Router Example

**File:** `services/api/src/routers/v1/recipe_book_router.py`

```python
from fastapi import APIRouter, Depends

from src.dependencies import CurrentUser, Db
from src.api.v1.recipe_book.list_recipe_books import ListRecipeBooks
from src.api.v1.recipe_book.create_recipe_book import CreateRecipeBook
from src.api.v1.recipe_book.get_recipe_book import GetRecipeBook
from src.api.v1.recipe_book.update_recipe_book import UpdateRecipeBook
from src.api.v1.recipe_book.delete_recipe_book import DeleteRecipeBook


router = APIRouter(prefix="/recipe-books", tags=["recipe-books"])


@router.get("/")
async def list_recipe_books(
    user: CurrentUser,
    database: Db,
    limit: int = 20,
    offset: int = 0
):
    return ListRecipeBooks.call(
        limit=limit,
        offset=offset,
        user=user,
        database=database
    )


@router.post("/")
async def create_recipe_book(
    params: CreateRecipeBook.Params,
    user: CurrentUser,
    database: Db
):
    return CreateRecipeBook.call(params, user=user, database=database)


@router.get("/{recipe_book_id}")
async def get_recipe_book(
    recipe_book_id: str,
    user: CurrentUser,
    database: Db
):
    return GetRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database
    )


@router.put("/{recipe_book_id}")
async def update_recipe_book(
    recipe_book_id: str,
    params: UpdateRecipeBook.Params,
    user: CurrentUser,
    database: Db
):
    return UpdateRecipeBook.call(
        recipe_book_id=recipe_book_id,
        params=params,
        user=user,
        database=database
    )


@router.delete("/{recipe_book_id}", status_code=204)
async def delete_recipe_book(
    recipe_book_id: str,
    user: CurrentUser,
    database: Db
):
    return DeleteRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database
    )
```

---

## Error Codes

| Code | Name | HTTP Status | Description |
|------|------|-------------|-------------|
| 1 | INTERNAL_ERROR | 500 | Unexpected server error |
| 2 | INVALID_REQUEST | 400 | Malformed request |
| 3 | INVALID_ENDPOINT_RESULT | 500 | Endpoint returned invalid response |
| 4 | UNAUTHORIZED | 401 | Not authenticated |
| 5 | FORBIDDEN | 403 | Not authorized for resource |
| 10 | INVALID_TOKEN | 401 | JWT token is invalid |
| 11 | TOKEN_EXPIRED | 401 | JWT token has expired |
| 12 | USER_NOT_FOUND | 404 | User does not exist |
| 100 | RECIPE_BOOK_NOT_FOUND | 404 | Recipe book does not exist |
| 101 | RECIPE_BOOK_ACCESS_DENIED | 403 | No access to recipe book |
| 102 | DUPLICATE_RECIPE_BOOK_NAME | 400 | Recipe book name already exists |
| 110 | RECIPE_NOT_FOUND | 404 | Recipe does not exist |
| 111 | RECIPE_ACCESS_DENIED | 403 | No access to recipe |
| 112 | DUPLICATE_RECIPE_NAME | 400 | Recipe name already exists in book |
| 120 | INGREDIENT_NOT_FOUND | 404 | Ingredient does not exist |
| 121 | DUPLICATE_INGREDIENT | 400 | Ingredient already exists |
| 122 | INVALID_INGREDIENT_QUANTITY | 400 | Invalid quantity value |
| 200 | DB_ROLLBACK_ERROR | 500 | Database transaction failed |
| 201 | DATABASE_LOCK_ERROR | 500 | Failed to acquire database lock |

---

## Testing Guide

### Prerequisites

```bash
# Start PostgreSQL
docker compose up -d postgres

# Run migrations
npx nx run migrator:migrate

# Start API server
npx nx run api:serve
```

### Manual Testing

#### 1. Get Auth0 Test Token

```bash
# Using Auth0 CLI or Management API
# Or use the Auth0 Dashboard to get a test token

export TOKEN="eyJ..."
```

#### 2. Test User Endpoint

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/users/me
```

#### 3. Test Recipe Book CRUD

```bash
# Create
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Book", "description": "My test recipes"}' \
  http://localhost:8000/v1/recipe-books

# List
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/recipe-books

# Get (replace ID)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/recipe-books/clz123abc

# Update
curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}' \
  http://localhost:8000/v1/recipe-books/clz123abc

# Delete
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/recipe-books/clz123abc
```

#### 4. Test Ingredient Search

```bash
# No auth required
curl "http://localhost:8000/v1/ingredients/search?q=tomato&limit=5"
```

#### 5. Test Recipe Creation

```bash
# First search for ingredients
curl "http://localhost:8000/v1/ingredients/search?q=pasta"
# Note the ingredient IDs

# Create recipe
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Simple Pasta",
    "instructions": "Boil water, cook pasta, add sauce.",
    "servings": 2,
    "prep_time": 5,
    "cook_time": 15,
    "ingredients": [
      {"ingredient_id": "PASTE_ID_HERE", "quantity": 200, "unit": "g"}
    ]
  }' \
  http://localhost:8000/v1/recipe-books/BOOK_ID/recipes
```

### Automated Tests

```bash
# Run API tests
npx nx run api:test

# Run with coverage
npx nx run api:test -- --cov=src
```

---

## Flutter + ngrok Development Setup

### Why ngrok?

When developing the Flutter mobile app on a physical device or emulator, it can't access `localhost` on your development machine. ngrok creates a public tunnel to your local API server.

### Setup Instructions

#### 1. Install ngrok

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com/download
```

#### 2. Configure ngrok (one-time)

```bash
# Sign up at ngrok.com and get your authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. Start the API Server

```bash
# Terminal 1: Start PostgreSQL
docker compose up -d postgres

# Terminal 2: Start API server
npx nx run api:serve
# Server runs on http://localhost:8000
```

#### 4. Start ngrok Tunnel

```bash
# Terminal 3: Create tunnel
ngrok http 8000
```

Output:
```
Session Status                online
Account                       your@email.com
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8000
```

Copy the `https://...ngrok-free.app` URL.

#### 5. Configure Flutter App

**File:** `app/lib/core/config/environment.dart`

```dart
class Environment {
  // Development - use ngrok URL
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://abc123.ngrok-free.app', // Your ngrok URL
  );

  // Production
  // static const String apiBaseUrl = 'https://api.palateful.com';

  static const String auth0Domain = 'your-tenant.auth0.com';
  static const String auth0ClientId = 'YOUR_CLIENT_ID';
  static const String auth0Audience = 'https://api.palateful.com';
}
```

#### 6. Run Flutter App

```bash
# iOS Simulator
cd app
flutter run -d ios

# Android Emulator
flutter run -d android

# With custom API URL
flutter run --dart-define=API_BASE_URL=https://abc123.ngrok-free.app
```

### API Client Configuration

**File:** `app/lib/data/datasources/api_client.dart`

```dart
import 'package:dio/dio.dart';
import '../core/config/environment.dart';

class ApiClient {
  late final Dio _dio;
  String? _authToken;

  ApiClient() {
    _dio = Dio(BaseOptions(
      baseUrl: Environment.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        // Required for ngrok free tier
        'ngrok-skip-browser-warning': 'true',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_authToken != null) {
          options.headers['Authorization'] = 'Bearer $_authToken';
        }
        return handler.next(options);
      },
      onError: (error, handler) {
        // Handle 401 - redirect to login
        if (error.response?.statusCode == 401) {
          // Trigger logout/re-auth
        }
        return handler.next(error);
      },
    ));
  }

  void setAuthToken(String token) {
    _authToken = token;
  }

  void clearAuthToken() {
    _authToken = null;
  }

  // Recipe Books
  Future<Response> getRecipeBooks({int limit = 20, int offset = 0}) {
    return _dio.get('/v1/recipe-books', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  Future<Response> createRecipeBook(Map<String, dynamic> data) {
    return _dio.post('/v1/recipe-books', data: data);
  }

  // Recipes
  Future<Response> getRecipes(String bookId, {int limit = 20, int offset = 0}) {
    return _dio.get('/v1/recipe-books/$bookId/recipes', queryParameters: {
      'limit': limit,
      'offset': offset,
    });
  }

  Future<Response> getRecipe(String recipeId) {
    return _dio.get('/v1/recipes/$recipeId');
  }

  Future<Response> createRecipe(String bookId, Map<String, dynamic> data) {
    return _dio.post('/v1/recipe-books/$bookId/recipes', data: data);
  }

  // Ingredients
  Future<Response> searchIngredients(String query, {int limit = 10}) {
    return _dio.get('/v1/ingredients/search', queryParameters: {
      'q': query,
      'limit': limit,
    });
  }
}
```

### ngrok Tips

#### Use a Static Domain (Paid Feature)
```bash
# With ngrok paid plan, you get a static domain
ngrok http 8000 --domain=palateful-dev.ngrok.io
```

#### Local ngrok Config File

**File:** `~/.ngrok2/ngrok.yml`

```yaml
version: "2"
authtoken: YOUR_AUTH_TOKEN
tunnels:
  palateful:
    proto: http
    addr: 8000
    inspect: true
```

Then run:
```bash
ngrok start palateful
```

#### Handle ngrok Browser Warning

ngrok free tier shows a browser warning page. Add this header to bypass:

```dart
headers: {
  'ngrok-skip-browser-warning': 'true',
}
```

### Development Workflow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Flutter App    │────▶│  ngrok Tunnel   │────▶│  Local FastAPI  │
│  (Device/Sim)   │     │  (HTTPS)        │     │  (localhost)    │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               │
        ▼                                               ▼
┌─────────────────┐                           ┌─────────────────┐
│                 │                           │                 │
│  Auth0          │                           │  PostgreSQL     │
│  (Cloud)        │                           │  (Docker)       │
│                 │                           │                 │
└─────────────────┘                           └─────────────────┘
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` | Ensure API server is running on port 8000 |
| `401 Unauthorized` | Check Auth0 config, ensure token is valid |
| ngrok shows HTML page | Add `ngrok-skip-browser-warning` header |
| Tunnel expires | Free tier tunnels expire after 2 hours, restart ngrok |
| CORS errors | Check FastAPI CORS middleware allows ngrok domain |

#### Update CORS for ngrok

**File:** `services/api/src/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "https://*.ngrok-free.app",  # Allow all ngrok domains
        "https://*.ngrok.io",        # Legacy ngrok domains
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
