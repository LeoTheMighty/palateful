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

## CURRENT: NX Monorepo Migration

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
