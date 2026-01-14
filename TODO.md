# Palateful TODO List

## How to Use This Document

This is the **single source of truth** for all planned work on Palateful.

### For the Developer (You)
- Check this file before starting work to see priorities
- Mark items as completed with `[x]` when done
- Add new ideas/requests to the appropriate section
- Move items between sections as priorities change

### For Claude Code (AI Assistant)
- **Always consult this file** when asked about remaining work
- **Update this file** when new TODO items are requested
- Keep the internal TodoWrite tool in sync with this document
- When completing work, mark items here AND in internal todos

### Status Legend
- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Completed
- `[!]` - Blocked / Needs discussion
- `[?]` - Needs clarification

---

## Architecture Decision: NX Monorepo Migration

> **Decision (2025-01-08)**: Migrate from Next.js/TypeScript/Prisma to NX monorepo with Flutter frontend and Python microservices.

**Confirmed Choices:**
- **Cloud Provider**: AWS (ECS Fargate, RDS, API Gateway, Lambda, ElastiCache)
- **Flutter Platforms**: iOS, Android, and Web
- **Data Migration**: Fresh start (re-seed with base ingredients/units)
- **OCR Service**: Stub for now (structure in place, mock integration)

**Documentation Created:**
- `docs/database-schema.md` - Complete Prisma schema documentation
- `docs/business-logic.md` - All algorithms documented
- `docs/ai-tools.md` - AI tool definitions and usage
- `docs/api-reference.md` - Current API endpoints
- `docs/ocr-batch-architecture.md` - HunyuanOCR AWS Batch architecture

---

## Completed Work (Next.js Era - Reference Only)

> These represent work done in the original Next.js/TypeScript implementation. The code is preserved for reference during migration.

### Phase 1: Foundation
- [x] Initialize Next.js project with dependencies (yarn)
- [x] Setup Prisma 5.x and database schema (User model)
- [x] Implement Auth0 v4 integration
- [x] Create UI components
- [x] Build page routes
- [x] Configure Vercel deployment

### Phase 2: Database Layer
- [x] Setup Postgres with pgvector and pg_trgm extensions
- [x] Update Prisma schema with all models
- [x] Create migration with vector indexes and custom SQL functions
- [x] Create core lib files (units, conversion, embeddings, search, feasibility, cooking)
- [x] Create and run seed scripts (units, ingredients, substitutions)
- [x] Create API routes

### Phase 3: AI Agent Infrastructure
- [x] Add Thread and Chat models to Prisma schema
- [x] Create OpenAI integration with function calling (tools)
- [x] Implement streaming SSE responses
- [x] Create recipe tools (search, list, details, suggest)
- [x] Create pantry tools (contents, feasibility, add)
- [x] Auto-generate thread titles

---

## NEXT STEPS: MVP Implementation

> **Session Date:** 2025-01-10
> **Reference:** See `docs/MVP.md` for complete implementation guide

### Quick Start for Next Session

```bash
# 1. Start services
docker compose up -d postgres

# 2. Continue with Phase 1 (Foundation Cleanup)
```

---

### Phase 1: Foundation Cleanup [ ]

#### 1.1 Create BaseEnum Class [ ]
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
        return [member.value for member in cls]

    @classmethod
    def names(cls) -> list[str]:
        return [member.name for member in cls]
```

#### 1.2 Update ErrorCode [ ]
**File:** `libraries/utils/utils/classes/error_code.py`
- Change import from `classes.enum import BaseEnum` to `from utils.classes.base_enum import BaseEnum`
- Add Palateful-specific error codes (100-129 for Recipe/Ingredient errors)

#### 1.3 Update APIException [ ]
**File:** `libraries/utils/utils/api/api_exception.py`
- Change import from `classes.error_code import ErrorCode` to `from utils.classes.error_code import ErrorCode`

#### 1.4 Update Endpoint [ ]
**File:** `libraries/utils/utils/api/endpoint.py`
- Update to use local modules:
  - `from utils.classes.error_code import ErrorCode`
  - Remove `catalyst` import (not needed for Palateful)
  - Remove Datadog/Sentry imports or make optional

---

### Phase 2: Authentication [ ]

> **Goal:** Implement Auth0 JWT verification

#### 2.1 Create Auth0 Verifier [ ]
**File:** `libraries/utils/utils/services/auth0.py`
- Install deps: `poetry add python-jose httpx` in libraries/utils
- Implement JWKS fetching and caching
- JWT verification with proper error handling

#### 2.2 Update Dependencies [ ]
**File:** `services/api/src/dependencies.py`
- Add `get_current_user` dependency
- Auto-create user on first login
- Export `CurrentUser`, `DbSession`, `Db` type aliases

#### 2.3 Add Config [ ]
**File:** `libraries/utils/utils/config.py` or `services/api/src/config.py`
- Add Auth0 settings (domain, audience, client_id)
- Load from environment variables

---

### Phase 3: API Implementation [ ]

> **Goal:** Implement all MVP endpoints

#### 3.1 Pydantic Schemas [ ]
Create in `services/api/src/schemas/`:
- [ ] `user.py` - UserResponse
- [ ] `recipe_book.py` - RecipeBookCreate, RecipeBookResponse, RecipeBookListResponse
- [ ] `recipe.py` - RecipeCreate, RecipeResponse, RecipeIngredientInput
- [ ] `ingredient.py` - IngredientSearchResult, IngredientCreate

#### 3.2 Ingredient Endpoints [ ] (do first - needed for recipes)
Create in `services/api/src/api/v1/ingredient/`:
- [ ] `search_ingredients.py` - GET /v1/ingredients/search (uses pg_trgm fuzzy search)
- [ ] `create_ingredient.py` - POST /v1/ingredients
- [ ] `get_ingredient.py` - GET /v1/ingredients/{id}

Create router:
- [ ] `services/api/src/routers/v1/ingredient_router.py`

#### 3.3 Recipe Book Endpoints [ ]
Create in `services/api/src/api/v1/recipe_book/`:
- [ ] `list_recipe_books.py` - GET /v1/recipe-books
- [ ] `create_recipe_book.py` - POST /v1/recipe-books
- [ ] `get_recipe_book.py` - GET /v1/recipe-books/{id}
- [ ] `update_recipe_book.py` - PUT /v1/recipe-books/{id}
- [ ] `delete_recipe_book.py` - DELETE /v1/recipe-books/{id}

Create router:
- [ ] `services/api/src/routers/v1/recipe_book_router.py`

#### 3.4 Recipe Endpoints [ ]
Create in `services/api/src/api/v1/recipe/`:
- [ ] `list_recipes.py` - GET /v1/recipe-books/{book_id}/recipes
- [ ] `create_recipe.py` - POST /v1/recipe-books/{book_id}/recipes
- [ ] `get_recipe.py` - GET /v1/recipes/{id}
- [ ] `update_recipe.py` - PUT /v1/recipes/{id}
- [ ] `delete_recipe.py` - DELETE /v1/recipes/{id}

Create router:
- [ ] `services/api/src/routers/v1/recipe_router.py`

#### 3.5 User Endpoints [ ]
Update in `services/api/src/api/v1/user/`:
- [ ] `get_me.py` - GET /v1/users/me
- [ ] `complete_onboarding.py` - POST /v1/users/me/complete-onboarding

#### 3.6 Wire Up Routers [ ]
**File:** `services/api/src/routers/v1_router.py`
- Include all new routers

---

### Phase 4: Migration [ ]

> **Goal:** Verify database schema matches models

```bash
# Delete old migration (if needed)
rm services/migrator/migrations/versions/001_initial.py

# Create fresh migration
npx nx run migrator:create-migration --description="initial_schema"

# Review generated migration file

# Run migration
npx nx run migrator:migrate

# Verify
npx nx run migrator:migration-status
```

---

### Phase 5: Testing [ ]

> **Goal:** Verify all endpoints work

```bash
# Start API
npx nx run api:serve

# Test health
curl http://localhost:8000/health

# Test ingredient search (no auth)
curl "http://localhost:8000/v1/ingredients/search?q=tomato"

# Get Auth0 token and test authenticated endpoints
export TOKEN="..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/users/me
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/recipe-books
```

---

### Phase 6: Flutter Setup [ ]

> **Goal:** Connect Flutter app to API via ngrok

```bash
# Start ngrok tunnel
ngrok http 8000

# Note the URL: https://xxx.ngrok-free.app

# Configure Flutter environment.dart with ngrok URL

# Run Flutter app
cd app && flutter run
```

---

## ARCHIVED: NX Monorepo Migration

### Target Directory Structure

```
palateful/
├── nx.json
├── pyproject.toml
├── docker-compose.yml
│
├── terraform/
│   ├── modules/
│   │   ├── vpc/
│   │   ├── rds/              # PostgreSQL with pgvector
│   │   ├── ecs/              # Fargate services
│   │   ├── api-gateway/
│   │   ├── lambda/           # Authorizers
│   │   ├── elasticache/      # Redis
│   │   ├── s3/               # OCR inputs/outputs
│   │   └── batch/            # OCR GPU batch jobs
│   └── environments/
│       ├── dev/
│       └── prod/
│
├── app/                      # Flutter frontend
│   └── lib/
│       ├── core/             # DI, router, theme
│       ├── data/             # Repositories, API clients
│       ├── domain/           # Entities, use cases
│       └── presentation/     # Screens, widgets, blocs
│
├── services/
│   ├── api/                  # FastAPI main API
│   ├── worker/               # Celery workers
│   ├── migrator/             # SQLAlchemy + Alembic
│   ├── authorizer/           # API Gateway Lambda
│   ├── stream_authorizer/    # Stream token Lambda
│   ├── vector_db_mgmt/       # Vector index management
│   └── ocr/                  # HunyuanOCR batch container
│
└── libraries/
    ├── utils/                # Shared code (models, services)
    └── test_helper/          # Factories, fixtures
```

---

### Migration Phase 1: Documentation & Archive
- [x] Create `docs/database-schema.md`
- [x] Create `docs/business-logic.md`
- [x] Create `docs/ai-tools.md`
- [x] Create `docs/api-reference.md`
- [x] Create `docs/ocr-batch-architecture.md`
- [x] Update `TODO.md` with migration plan
- [ ] Create `archive/` directory
- [ ] Move current `src/`, `prisma/`, `scripts/` to archive

### Migration Phase 2: NX Workspace Setup
- [ ] Remove current Next.js config files
- [ ] Initialize NX workspace: `npx create-nx-workspace palateful --preset=apps`
- [ ] Install NX Python plugin: `npm install @nxlv/python`
- [ ] Configure `nx.json` for Python projects
- [ ] Create root `pyproject.toml` with Poetry
- [ ] Create `.python-version` (3.11)
- [ ] Create `.env.example` with all required vars
- [ ] Update `docker-compose.yml` for new services

### Migration Phase 3: Shared Libraries
#### libraries/utils
- [ ] Create `libraries/utils/project.json`
- [ ] Create `libraries/utils/pyproject.toml`
- [ ] Install deps: sqlalchemy, pgvector, pydantic

#### SQLAlchemy Models (translate from Prisma)
- [ ] `db/models/user.py` - User model
- [ ] `db/models/thread.py` - AI threads
- [ ] `db/models/chat.py` - Chat messages
- [ ] `db/models/pantry.py` - Pantry, PantryUser, PantryIngredient
- [ ] `db/models/recipe.py` - RecipeBook, Recipe, RecipeIngredient
- [ ] `db/models/ingredient.py` - Ingredient with Vector(384), Substitutions
- [ ] `db/models/unit.py` - Unit, CookingLog
- [ ] `db/session.py` - Session management
- [ ] `db/base.py` - Declarative base

#### Unit Conversion Logic
- [ ] `units/constants.py` - Unit definitions
- [ ] `units/conversion.py` - normalize_quantity, convert_between_units

#### Shared Services
- [ ] `services/auth0.py` - JWT verification
- [ ] `services/redis.py` - Redis client
- [ ] `exceptions.py` - Custom exceptions

#### libraries/test_helper
- [ ] Create factories: UserFactory, RecipeFactory, IngredientFactory
- [ ] Create pytest fixtures: db_session, authenticated_user

### Migration Phase 4: Migrator Service
- [ ] Create `services/migrator/project.json`
- [ ] Create `services/migrator/alembic.ini`
- [ ] Create `alembic/env.py` - Import all models
- [ ] Create `001_initial.py` migration:
  - Enable pg_trgm and pgvector extensions
  - Create all tables
  - Create trigram GIN index
  - Create vector HNSW index
  - Create `search_ingredients_fuzzy()` function
  - Create `search_ingredients_semantic()` function
- [ ] Create seed scripts for units, ingredients, substitutions

### Migration Phase 5: FastAPI Service
#### Project Setup
- [ ] Create `services/api/project.json`
- [ ] Create `services/api/pyproject.toml`
- [ ] Create `services/api/Dockerfile`
- [ ] Install deps: fastapi, uvicorn, sqlalchemy, openai, python-jose, httpx

#### Core Infrastructure
- [ ] `main.py` - FastAPI app with CORS, routers
- [ ] `config.py` - Pydantic Settings
- [ ] `dependencies.py` - DB session, Auth0 JWT verification

#### Pydantic Schemas
- [ ] `schemas/user.py`
- [ ] `schemas/recipe.py`
- [ ] `schemas/pantry.py`
- [ ] `schemas/ingredient.py`
- [ ] `schemas/chat.py`

#### Business Services (translate from TypeScript)
- [ ] `services/ingredient_service.py` - Search cascade
- [ ] `services/feasibility_service.py` - Recipe feasibility
- [ ] `services/cooking_service.py` - Cook with deduction
- [ ] `services/recipe_service.py` - Recipe CRUD
- [ ] `services/pantry_service.py` - Pantry CRUD
- [ ] `services/chat_service.py` - Thread/chat management

#### API Routers
- [ ] `routers/auth.py`
- [ ] `routers/users.py`
- [ ] `routers/ingredients.py`
- [ ] `routers/recipes.py`
- [ ] `routers/pantry.py`
- [ ] `routers/chat.py` - SSE streaming

#### AI Integration
- [ ] `ai/client.py` - OpenAI AsyncClient
- [ ] `ai/prompts.py` - System prompts
- [ ] `ai/tools/base.py` - BaseTool, ToolContext
- [ ] `ai/tools/recipe_tools.py`
- [ ] `ai/tools/pantry_tools.py`
- [ ] `ai/executor.py` - Tool execution
- [ ] `ai/streaming.py` - SSE streaming

### Migration Phase 6: Celery Worker
- [ ] Create `services/worker/project.json`
- [ ] Create `services/worker/pyproject.toml`
- [ ] Create `services/worker/Dockerfile`
- [ ] `celery_app.py` - Celery configuration
- [ ] `tasks/embedding_tasks.py` - Generate embeddings
- [ ] `tasks/import_tasks.py` - URL import
- [ ] `tasks/ai_tasks.py` - Long-running AI

### Migration Phase 7: Lambda Authorizers
#### API Gateway Authorizer
- [ ] Create `services/authorizer/`
- [ ] `handler.py` - Verify Auth0 JWT
- [ ] `auth0_verifier.py` - JWKS handling

#### Stream Authorizer
- [ ] Create `services/stream_authorizer/`
- [ ] `handler.py` - Stream token verification

### Migration Phase 8: Vector DB Management
- [ ] Create `services/vector_db_mgmt/`
- [ ] `cli.py` - Click CLI
- [ ] `embeddings.py` - Batch generation
- [ ] `indexing.py` - Index management
- [ ] `backfill.py` - Backfill missing

### Migration Phase 9: OCR Service (Stubbed)
> See `docs/ocr-batch-architecture.md` for full design

- [ ] Create `services/ocr/`
- [ ] Create Dockerfile (CUDA base)
- [ ] `run_job.py` - Download from S3, run OCR, upload result
- [ ] Mock OCR function for testing

### Migration Phase 10: Terraform Infrastructure
#### Modules
- [ ] `terraform/modules/vpc/` - VPC, subnets, security groups
- [ ] `terraform/modules/rds/` - PostgreSQL 16 with pgvector
- [ ] `terraform/modules/ecs/` - Fargate cluster
- [ ] `terraform/modules/api-gateway/` - REST API
- [ ] `terraform/modules/lambda/` - Authorizers
- [ ] `terraform/modules/elasticache/` - Redis
- [ ] `terraform/modules/s3/` - OCR buckets
- [ ] `terraform/modules/batch/` - GPU batch compute

#### Environments
- [ ] `terraform/environments/dev/`
- [ ] `terraform/environments/prod/`

### Migration Phase 11: Flutter App
#### Project Setup
- [ ] Create Flutter project in `app/`
- [ ] Add deps: flutter_bloc, go_router, dio, get_it, freezed, auth0_flutter

#### Core Layer
- [ ] `lib/core/di/injection.dart`
- [ ] `lib/core/router/app_router.dart`
- [ ] `lib/core/theme/app_theme.dart`

#### Data Layer
- [ ] `lib/data/datasources/api_client.dart`
- [ ] `lib/data/datasources/auth_datasource.dart`
- [ ] `lib/data/repositories/`

#### Domain Layer
- [ ] `lib/domain/entities/`
- [ ] `lib/domain/repositories/`
- [ ] `lib/domain/usecases/`

#### Presentation Layer
- [ ] `lib/presentation/blocs/`
- [ ] `lib/presentation/screens/`
- [ ] `lib/presentation/widgets/`

### Migration Phase 12: Docker & Local Dev
- [ ] Update `docker-compose.yml`:
  - postgres (pgvector/pgvector:pg16)
  - redis (redis:7-alpine)
  - api (FastAPI)
  - worker (Celery)
- [ ] Create `scripts/setup.sh`
- [ ] Create `scripts/migrate.sh`
- [ ] Create `scripts/seed.sh`

---

## Post-Migration: Feature Development

> These features will be implemented in the new Python/Flutter stack.

### High Priority: Data Model Enhancements

#### Dish & Recipe Versioning
- [ ] Create `Dish` model (name, description, defaultRecipeId)
- [ ] Add `dishId` to Recipe model
- [ ] Add `versionLabel` field to Recipe
- [ ] API routes for Dish CRUD
- [ ] "Compare versions" view

#### Simple Recipe / Offline Mode
- [ ] Add `simpleRecipe` markdown field
- [ ] Create markdown template
- [ ] Auto-generate on recipe create/update
- [ ] PWA offline caching

#### CustomFields for Recipes
- [ ] Add `customFields` JSON column
- [ ] Define common field types
- [ ] API support for custom fields

### High Priority: Comments, Ratings & Cooking Log

#### Recipe Notes System
- [ ] Create `RecipeNote` model
- [ ] Create `RecipeRating` model
- [ ] Inline notes on steps
- [ ] Quick rating after cooking

#### Cooking Log
- [ ] Enhanced `CookingLog` model
- [ ] "I cooked this!" button
- [ ] Cooking history dashboard

#### Audio Input
- [ ] Browser speech recognition
- [ ] Voice-to-text for notes
- [ ] Voice chat with AI agent

### High Priority: Sharing & Collaboration

#### Recipe Book Sharing
- [ ] Sharing settings on RecipeBook
- [ ] Role-based permissions
- [ ] Invite system
- [ ] Activity feed

#### Public Recipe Sharing
- [ ] `isPublic` and `publicSlug` fields
- [ ] Public route `/r/[slug]`
- [ ] QR code generation

### High Priority: Recipe Import System

#### URL Import
- [ ] POST endpoint for URL import
- [ ] JSON-LD/microdata parsing
- [ ] LLM fallback extraction
- [ ] Preview before save

#### OCR Import (after stubbed service)
- [ ] Integrate HunyuanOCR batch jobs
- [ ] Recipe structurer service
- [ ] Image upload UI

### AI Agent: Additional Tools
- [ ] `suggestRecipeFromPantry`
- [ ] `surpriseMe`
- [ ] `suggestVariation`
- [ ] `createRecipe`
- [ ] `importRecipeFromUrl`
- [ ] `logCooking`
- [ ] `rateRecipe`

---

## Backlog

### Frontend (Flutter)
- [ ] Recipe list with filters/search
- [ ] Recipe detail page
- [ ] Recipe create/edit forms
- [ ] Pantry management UI
- [ ] Chat interface
- [ ] User profile/settings

### Technical
- [ ] Rate limiting
- [ ] Cost tracking for AI
- [ ] Real-time sync (WebSockets)
- [ ] Backup/export

---

## Notes & Decisions Log

### 2025-01-10 (Session 5) - MVP Planning

**MVP Scope Decisions:**
- **Cooking UI:** Scrollable view (not step-by-step with timers)
- **Ingredient Handling:** Fuzzy search → suggest existing → create new if no match
- **Pantry:** Out of scope for MVP (recipe book only)
- **Auth:** Auth0 with JWT tokens

**Documentation Created:**
- `docs/MVP.md` - Complete implementation guide with:
  - API endpoint specifications
  - Pydantic schema definitions
  - Authentication implementation details
  - Flutter + ngrok setup guide
  - Error code reference
  - Testing commands

**Technical Decisions:**
- Create local `BaseEnum` class for `ErrorCode`
- Palateful-specific error codes start at 100 (recipe/ingredient errors)
- Ingredient search uses PostgreSQL `search_ingredients_fuzzy()` function (pg_trgm)
- New user-submitted ingredients marked with `pending_review: true`

**Files to Create:**
- `libraries/utils/utils/classes/base_enum.py`
- `libraries/utils/utils/services/auth0.py`
- 4 schema files in `services/api/src/schemas/`
- 13 endpoint files in `services/api/src/api/v1/`
- 3 router files in `services/api/src/routers/v1/`

---

### 2025-01-08 (Session 4)
- **Major Decision**: Migrate to NX monorepo with Python/Flutter
- Created comprehensive documentation:
  - `docs/database-schema.md` - All Prisma models documented
  - `docs/business-logic.md` - Algorithms (feasibility, cooking, search, units)
  - `docs/ai-tools.md` - All tool definitions with examples
  - `docs/api-reference.md` - Current API endpoints
  - `docs/ocr-batch-architecture.md` - AWS Batch GPU architecture for OCR
- Confirmed: AWS, all Flutter platforms, fresh DB start, stubbed OCR

### 2025-01-01 (Session 3)
- Completed AI infrastructure: executor, tools, streaming
- Created all chat API routes with SSE streaming
- Added comprehensive feature TODO

### 2024-12-31 (Session 2)
- Added Thread and Chat models for AI chat system
- Created OpenAI integration documentation
- Decision: Use OpenAI Chat Completions API with function calling

### 2024-12-31 (Session 1)
- Completed full database layer with pgvector support
- Using Xenova/transformers for local embeddings (384-dim)
- Migration includes custom SQL functions for fuzzy and semantic search

---

*Last updated: 2025-01-08*
