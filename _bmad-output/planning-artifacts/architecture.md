---
stepsCompleted: [step-01-init, step-02-context, step-03-starter, step-04-decisions, step-05-patterns, step-06-structure, step-07-validation, step-08-complete]
status: 'complete'
completedAt: '2026-03-12'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - docs/DATABASE.md
  - docs/database-schema.md
  - docs/ocr-batch-architecture.md
  - docs/RECIPE_IMPORT_SYSTEM.md
  - docs/api-reference.md
  - docs/business-logic.md
  - docs/ai-tools.md
  - docs/search-design.md
  - docs/SHARED_SHOPPING_CART.md
  - docs/INVITATION_SYSTEM.md
  - docs/calendar-system.md
  - docs/RECIPE_EXPERIENCE_IMPLEMENTATION.md
  - docs/AUTH0.md
  - docs/SETUP.md
  - docs/COST.md
  - docs/VERCEL.md
  - docs/OPENAI_AGENT_SETUP.md
  - docs/EVAL_DESIGN.md
  - docs/BIG_ROCKS.md
  - docs/MVP.md
  - docs/db-uml-diagram.md
workflowType: 'architecture'
project_name: 'palateful'
user_name: 'Leo'
date: '2026-03-12'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
61 FRs spanning 6 domains. Architecturally, these break into:
- **Core CRUD** (recipes, recipe books, pantries, ingredients) — standard REST patterns with SQLAlchemy async ORM
- **Smart matching** (ingredient deduplication via pg_trgm fuzzy + pgvector semantic search) — requires search infrastructure and embedding pipeline
- **Import pipeline** (URL/file/photo → parsed recipe) — async worker chain with multiple extraction strategies and confidence-based auto-approve/review flow
- **Collaboration** (shared recipe books, pantries, shopping lists, meal events) — role-based access with invitation/invite-link system
- **AI features** (chat agent, recipe suggestions, feasibility checking) — OpenAI function calling loop with streaming SSE responses
- **Meal planning & timers** (calendar events, prep steps, multi-phase cooking notifications) — event-driven with push notification integration via Firebase

**Non-Functional Requirements:**
31 NFRs driving architecture:
- **Performance**: Sub-200ms API responses, real-time subscriptions for shopping lists
- **Security**: Auth0 JWT, RBAC on every shared resource, encrypted credentials
- **Scalability**: Scale-to-zero GPU OCR, Celery worker pool, potential Aurora Serverless
- **Reliability**: Import pipeline with status tracking and retry semantics
- **Cost efficiency**: Tiered AI strategies to minimize OpenAI spend, Spot GPU instances
- **Accessibility**: WCAG AA compliance, cook mode with large touch targets

**Scale & Complexity:**
- Primary domain: Full-stack mobile + API
- Complexity level: High
- Estimated architectural components: 12+ (API service, worker service, OCR batch service, Redis cache, PostgreSQL + pgvector, S3 storage, AWS AppSync, Firebase push, Auth0 identity, Flutter mobile app, web app, load balancer/API gateway, monitoring)

### Three Runtime Domains

The system operates across three fundamentally different execution models that share a database and auth layer:

1. **Request-Response** — Standard REST API via FastAPI. Sub-200ms target. Handles CRUD, search, auth, feasibility checks.
2. **Async Workers** — Celery task chains for import pipeline, notification dispatch, AI suggestion engine. Minutes-scale operations with status tracking and retry semantics.
3. **Real-Time Streams** — Three distinct transports:
   - **AWS AppSync** (Terraform-managed) — GraphQL subscriptions for collaborative data sync (shopping lists, shared resources). Infrastructure-level, not application code.
   - **SSE via FastAPI** (API service) — AI chat streaming responses.
   - **Firebase Push** (external) — Background notifications for imports, timers, meal events.

### Architectural Priority Tiers

Mapped to the PRD's 4 development phases:

| Tier | Scope | Architecture Requirement | PRD Phase |
|------|-------|--------------------------|-----------|
| **Tier 1 — Must be right from day one** | Auth/RBAC, database schema, API patterns, recipe CRUD, import pipeline | Rock-solid foundations, fully designed | Phase 1-2 |
| **Tier 2 — Must be extensible** | Shopping list sync, calendar/meal events, notification system | Clear interfaces and extension points, can stub initially | Phase 2-3 |
| **Tier 3 — Can evolve** | AI suggestion engine, social features, voice control | Architectural awareness only, no premature optimization | Phase 3-4 |

Design for 100 users, plan for 1,000, don't prematurely optimize for 10,000.

### Existing Service Boundaries (Inherited Decisions)

The NX monorepo already defines service boundaries that constitute architectural decisions:

```
services/
├── api/          # FastAPI REST API (request-response domain)
├── worker/       # Celery async tasks (async worker domain)
├── parser/       # HunyuanOCR service (GPU batch domain)
├── migrator/     # Alembic database migrations
libraries/
├── utils/        # Shared business logic, extractors, matchers
├── test_helper/  # Shared test utilities
terraform/
├── modules/      # AWS infrastructure including AppSync for real-time
```

Real-time features (shopping list sync, live updates) handled via AWS AppSync GraphQL subscriptions, managed in `terraform/modules/`. No additional application service needed — AppSync connects to existing data sources (RDS, Lambda resolvers).

### Technical Constraints & Dependencies

- **Existing infrastructure**: FastAPI services in NX monorepo, Alembic migrations, Poetry dependency management, Docker Compose local dev
- **Database**: PostgreSQL 16 with pgvector extension (384-dim embeddings), pg_trgm for fuzzy search
- **Auth**: Auth0 with Google + Apple OAuth — JWT validation on all API endpoints
- **AI**: OpenAI gpt-4o-mini for chat/extraction/matching; HunyuanOCR self-hosted on GPU
- **Infrastructure**: AWS (ECS Fargate, RDS, S3, Batch with Spot, AppSync, CloudWatch), Terraform-managed
- **Mobile**: Flutter 3.19+ with iOS (Xcode 15+) and Android targets
- **Push notifications**: Firebase Cloud Messaging
- **Deprecated context**: Several docs (`AUTH0.md`, `SETUP.md`, `VERCEL.md`, `api-reference.md`) reference the legacy Next.js/Prisma/Vercel stack. These are historical reference only — the project has fully migrated to FastAPI/SQLAlchemy/AWS. Implementing agents should ignore Prisma/Next.js patterns in these docs.

### Cross-Cutting Concerns Identified

1. **Authentication & Authorization**: Every API endpoint needs JWT validation; every shared resource needs role checks (owner/editor/viewer). Invitation claim flow on signup adds complexity. AppSync auth integrates with Auth0 JWT.
2. **Real-time Communication**: AWS AppSync subscriptions for collaborative data sync, SSE for AI chat streaming, Firebase push for background events — three transports with different reliability guarantees. AppSync is infrastructure-managed via Terraform.
3. **Background Processing**: Celery for import pipeline tasks, AWS Batch for GPU OCR, periodic jobs for AI suggestions — need unified job tracking and error handling.
4. **AI Cost Management**: Tiered strategies across import (JSON-LD before AI), ingredient matching (cached/exact/fuzzy before semantic/AI), and chat (token tracking per operation).
5. **Data Integrity**: Shared mutable resources (pantries, shopping lists) need conflict resolution. Import pipeline needs idempotent operations. Timer state needs persistence across app restarts.
6. **Flutter Client State Management**: Offline-capable recipe viewing, optimistic updates for shopping lists, timer persistence when app backgrounds, reactive data bindings for real-time components (Timer Widget, Import Progress Card, Shopping List Item). Cook mode requires system-level integration (screen wake lock, background timer notifications).
7. **Observability**: Eval suite for AI/OCR quality regression, cost tracking per AI operation, structured logging across services.
8. **Implementation Guide Reconciliation**: Existing `docs/RECIPE_EXPERIENCE_IMPLEMENTATION.md` defines a Flutter file structure that the architecture must either adopt or explicitly supersede to avoid conflicting guidance for implementing agents.

## Starter Template Evaluation

### Primary Technology Domain

**Full-stack mobile + web + API** — brownfield project. Backend (FastAPI/Python) and infrastructure (AWS/Terraform) are established. This evaluation covers the **Flutter client stack** which needs library decisions for new feature development.

### Starter Options Considered

Not applicable — brownfield project with existing NX monorepo and Flutter app structure. This section documents **library selection decisions** for the Flutter client.

### Selected Stack

**State Management: Riverpod 3.0** (`flutter_riverpod`)
- Compile-time safety catches provider errors before runtime
- Built-in **offline persistence** — perfect for cached recipe viewing when offline
- Widget-tree independent — providers are testable without widget harnesses
- Lighter boilerplate than BLoC; we don't need enterprise audit trails
- Code generation via `riverpod_generator` for cleaner provider definitions

**Routing: go_router** (latest stable)
- Official Flutter team package — long-term maintenance guaranteed
- Declarative routing with Navigator 2.0 under the hood
- **Deep linking support** — critical for invitation links, shared recipe links
- **Web URL support** — path-based URLs work natively for Flutter Web
- Fragment and query parameter support for complex navigation patterns

**Real-time / GraphQL: amplify_flutter** (Amplify Gen 2)
- Official AWS SDK for AppSync — native subscription support
- Auto-reconnect with exponential backoff on connection loss
- Stream-based API for `.onCreate()`, `.onUpdate()`, `.onDelete()` subscriptions
- Auth integration supports JWT tokens from Auth0
- Codegen for type-safe GraphQL operations

**HTTP Client: dio** (~5.4+)
- Interceptors for JWT auth token injection on every request
- Request/response logging for debugging
- Retry logic with configurable strategies
- Multipart uploads for recipe images

**Data Models: freezed + json_serializable**
- Immutable data classes with `copyWith` — clean state updates with Riverpod
- Union types for modeling states (loading/success/error)
- Code generation eliminates serialization boilerplate
- Pattern matching for exhaustive state handling

**Flutter Web: Enabled**
- Shared codebase with mobile — single widget tree, responsive breakpoints
- Ideal fit: Palateful is an app experience, not an SEO-critical marketing site
- 3-4 column card grid on web/large screens (per UX spec)
- Tablet layout mirrors web (per UX spec)
- Limitation: Safari WasmGC support still lagging — acceptable tradeoff

### Architectural Decisions Provided by Stack

**Language & Runtime:**
Dart 3.6+, Flutter 3.27+, null safety enforced, pattern matching enabled

**Styling Solution:**
Material 3 with custom `ThemeData` (cream/chocolate palette, Playfair Display serif, warm dark mode) — already defined in UX spec

**Build Tooling:**
`build_runner` for code generation (freezed, json_serializable, riverpod_generator). NX workspace orchestrates builds.

**Testing Framework:**
`flutter_test` + `riverpod` test utilities (`ProviderContainer.test()`). Widget testing with `ProviderScope` overrides. Integration tests via `integration_test` package.

**Code Organization:**
Feature-first structure aligned with existing `lib/features/` convention from `RECIPE_EXPERIENCE_IMPLEMENTATION.md`:
```
lib/
├── core/           # Theme, constants, utils, auth
├── features/       # Feature modules (home, recipes, pantry, etc.)
│   └── {feature}/
│       ├── screens/
│       ├── widgets/
│       ├── providers/    # Riverpod providers
│       └── models/       # Freezed data classes
├── shared/         # Shared widgets, providers
└── routing/        # go_router configuration
```

**Development Experience:**
Hot reload, Riverpod devtools, dio request logging, `build_runner watch` for continuous codegen

**Note:** No separate project initialization needed — these libraries are added to the existing Flutter app's `pubspec.yaml`.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Dual API pattern (REST + AppSync)
- RBAC via FastAPI dependency injection
- Error response format standardization
- Two-environment deployment (local + prod)

**Important Decisions (Shape Architecture):**
- Caching strategy (Redis + Riverpod offline + image cache)
- CI/CD via GitHub Actions
- Shared ECR images across environments

**Deferred Decisions (Post-MVP):**
- API versioning (v1 prefix exists, no breaking changes expected yet)
- Rate limiting (not needed until public-facing scale)
- CDN strategy for Flutter Web (CloudFront, defer until web launch)

### Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | PostgreSQL 16 + pgvector + pg_trgm | Existing — handles CRUD, fuzzy search, semantic search |
| ORM | SQLAlchemy 2.0 async | Existing — async-first, mature ecosystem |
| Migrations | Alembic | Existing — version-controlled schema changes |
| Caching | Redis (server) + Riverpod offline persistence (client) | Redis for match cache, rate limits, Celery broker. Riverpod for offline recipe viewing, pantry data |
| Image Caching | `cached_network_image` with disk cache | Recipe photos are read-heavy, rarely change |
| Embedding Pipeline | Generate on ingredient creation/update via OpenAI | 384-dim vectors for semantic search, stored in pgvector |

### Authentication & Security

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Authentication | Auth0 JWT (existing) | Google + Apple OAuth, JWT validation on all endpoints |
| Authorization | FastAPI `Depends()` RBAC | Consistent with existing auth pattern, declarative role checks |
| AppSync Auth | Auth0 JWT integration | Same token validates across REST and GraphQL |
| API Security | HTTPS everywhere, CORS restricted to app domains | Standard practice, no custom encryption needed |

### API & Communication Patterns

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary API | REST via FastAPI (dio client) | Existing — all CRUD, search, auth, import, AI chat |
| Real-time | GraphQL subscriptions via AWS AppSync (amplify_flutter client) | Shopping list sync, live notifications — infrastructure-managed |
| AI Chat Streaming | SSE via FastAPI | Existing pattern — streaming token responses |
| Push Notifications | Firebase Cloud Messaging | Background events — import complete, timer alerts, meal reminders |
| Error Format | `{"error": {"code": "...", "message": "...", "status": N, "details": {}}}` | Extends existing error code pattern (240-259 for invitations) |
| API Prefix | `/v1/` | Existing — no versioning strategy needed yet |

### Frontend Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State Management | Riverpod 3.0 | Compile-time safety, offline persistence, testable |
| Routing | go_router | Official, deep linking, web URLs |
| HTTP Client | dio | Interceptors for JWT, retry, logging |
| Data Models | freezed + json_serializable | Immutable, codegen, pattern matching |
| GraphQL Client | amplify_flutter | AppSync native, subscription support |
| Code Organization | Feature-first `lib/features/` | Aligned with existing convention |
| Flutter Web | Enabled, shared codebase | Responsive breakpoints, not SEO-critical |

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Environments | Local (Docker Compose) + Prod (AWS) | Two environments only — no staging overhead |
| CI/CD | GitHub Actions | Lint/test on PR, Docker build + ECR push on merge, Terraform apply, Flutter web deploy |
| Container Images | Shared ECR, environment-agnostic | Parser dev image reused for prod — Terraform `environment` var controls config only |
| API Hosting | ECS Fargate | Existing pattern, scales with demand |
| OCR | AWS Batch Spot GPU (existing) | Scale-to-zero, g4dn.xlarge/g5.xlarge, 3 retry attempts |
| Real-time Infra | AWS AppSync (Terraform module) | Managed WebSocket, no application service needed |
| Monitoring | CloudWatch Logs + custom cost tracking | Log retention: 7d dev, 30d prod (already configured) |
| Mobile Builds | Fastlane | iOS TestFlight, Android Play Store |

### Decision Impact Analysis

**Implementation Sequence:**
1. Flutter library installation (Riverpod, go_router, dio, freezed, amplify_flutter)
2. Core architecture setup (theme, routing, dio interceptors, Riverpod providers)
3. Auth flow (Auth0 → dio JWT interceptor)
4. Feature modules (recipe CRUD, pantry, import)
5. AppSync integration (shopping list sync)
6. CI/CD pipeline (GitHub Actions)
7. Flutter Web responsive layout

**Cross-Component Dependencies:**
- dio JWT interceptor depends on Auth0 integration
- Riverpod offline persistence depends on freezed models being defined
- AppSync subscriptions depend on Terraform module deployment
- CI/CD depends on ECR repositories and Terraform state

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Database Naming:**
- Tables: plural snake_case (`users`, `recipe_books`, `shopping_list_items`)
- Columns: snake_case (`auth0_id`, `email_verified`, `created_at`)
- Primary keys: `id` (UUID)
- Foreign keys: `{entity}_id` (`user_id`, `recipe_book_id`)
- Timestamps: `created_at`, `updated_at`, `archived_at` (all `TIMESTAMPTZ`, server default `now()`)
- Indexes: `ix_{table}_{column}` (Alembic default)
- Soft deletes: use `archived_at` (not `deleted_at`)

**API Naming:**
- Prefix: `/v1/`
- Resources: plural kebab-case (`/v1/recipe-books`, `/v1/shopping-lists`)
- Path params: `/{resource_id}` (`/{recipe_book_id}`)
- Query params: snake_case (`limit`, `offset`, `sort_by`)
- Verbs: GET (list/get), POST (create), PUT (update), DELETE (soft delete)

**Python Code Naming:**
- Classes: `PascalCase` (`RecipeBook`, `CreateRecipeBook`)
- Functions/methods: `snake_case` (`list_recipe_books`)
- Files: `snake_case` (`recipe_book_router.py`, `create_recipe_book.py`)
- Constants: `UPPER_SNAKE_CASE`
- Schemas: `{Entity}Create`, `{Entity}Update`, `{Entity}Response`

**Dart/Flutter Code Naming:**
- Classes: `PascalCase` (`RecipeCard`, `AppColors`)
- Files: `snake_case` (`recipe_card.dart`, `app_colors.dart`)
- Variables/functions: `camelCase` (`onTap`, `recipeId`)
- Constants: `camelCase` static properties on classes (`AppColors.cream`)
- Providers: `camelCase` with `Provider` suffix (`recipeListProvider`)

### Structure Patterns

**Backend (Python):**
```
services/api/src/
├── api/v1/{resource}/           # Endpoint classes (one per operation)
│   ├── create_{resource}.py     # CreateResource(Endpoint)
│   ├── list_{resource}s.py      # ListResources(Endpoint)
│   ├── get_{resource}.py        # GetResource(Endpoint)
│   ├── update_{resource}.py     # UpdateResource(Endpoint)
│   └── delete_{resource}.py     # DeleteResource(Endpoint)
├── routers/v1/                  # FastAPI routers
│   └── {resource}_router.py     # Wire endpoints to routes
├── schemas/                     # Pydantic schemas
│   └── {resource}.py            # Create/Update/Response schemas
└── middleware/                   # Auth, CORS, error handling

libraries/utils/utils/
├── models/                      # SQLAlchemy models (shared)
├── services/                    # Business logic services
├── db/                          # Database utilities
└── classes/                     # Base classes (Endpoint, etc.)

services/api/tests/
└── test_{resource}.py           # Test{Resource} class with test_ methods
```

**Frontend (Flutter):**
```
app/lib/
├── core/
│   ├── theme/                   # AppColors, AppTheme, typography
│   ├── constants/               # App-wide constants
│   ├── auth/                    # Auth0 integration, token management
│   └── network/                 # dio client, interceptors
├── features/{feature}/
│   ├── screens/                 # Full-page screens
│   ├── widgets/                 # Feature-specific widgets
│   ├── providers/               # Riverpod providers
│   └── models/                  # Freezed data classes
├── shared/
│   ├── widgets/                 # Reusable widgets (buttons, cards)
│   └── providers/               # Shared providers (auth, user)
└── routing/
    └── app_router.dart          # go_router configuration
```

**Tests co-located by service** (not co-located with source):
- Python: `services/{service}/tests/test_{feature}.py`
- Flutter: `app/test/{feature}/` mirroring `lib/features/`

### Format Patterns

**API Response Format:**

Success:
```json
{"data": {"id": "uuid", "name": "..."}, "status": 200}
```

Error:
```json
{"error": {"code": "RECIPE_NOT_FOUND", "message": "...", "status": 404, "details": {}}}
```

Created:
```json
{"data": {"id": "uuid"}, "status": 201}
```

List:
```json
{"data": [{"id": "uuid", ...}], "total": 42, "limit": 20, "offset": 0, "status": 200}
```

- Use existing `success()` helper for all responses
- Error codes: string constants, grouped by domain (240-259 invitations, extend pattern)
- Dates in JSON: ISO 8601 strings (`"2026-03-12T14:30:00Z"`)
- JSON field naming: snake_case (matches Python, Dart `json_serializable` handles conversion)
- Null fields: include in response (don't omit), client handles nullability

**Endpoint Class Pattern (mandatory):**
Every API operation is an `Endpoint` subclass with nested `Params` and `Response`:
```python
class CreateRecipe(Endpoint):
    class Params(BaseModel):
        name: str
        recipe_book_id: UUID
    class Response(BaseModel):
        id: UUID
    def execute(self, params: "CreateRecipe.Params"):
        ...
```

### Communication Patterns

**Celery Task Naming:**
- Task names: `{service}.{domain}.{action}` (`worker.import.parse_source`, `worker.import.extract_recipe`)
- Task results: stored in Redis, keyed by job ID
- Status updates: write to `import_jobs`/`import_items` tables, not just task state

**AppSync Event Naming:**
- Subscription names: `on{Entity}{Action}` (`onShoppingListItemCreated`, `onShoppingListItemUpdated`)
- Mutation names: `{action}{Entity}` (`createShoppingListItem`, `updateShoppingListItem`)
- Payload: full entity object (not deltas)

**Riverpod State Patterns:**
- Use `AsyncValue<T>` for all server data (handles loading/error/data states)
- Provider naming: `{entity}{Action}Provider` (`recipeListProvider`, `pantryContentsProvider`)
- Notifier naming: `{Entity}{Action}Notifier` (`RecipeListNotifier`)
- Mutations through notifier methods, not separate providers
- Optimistic updates for shared mutable data (shopping lists)

**Logging:**
- Python: `structlog` with JSON output, include `user_id`, `request_id`, `resource_type`
- Log levels: ERROR (requires action), WARNING (unexpected but handled), INFO (business events), DEBUG (development only)
- Never log secrets, tokens, or full request bodies in production

### Process Patterns

**Error Handling:**
- Backend: raise `HTTPException` with error dict, caught by middleware
- Flutter: `AsyncValue.error` propagates to UI, `ErrorWidget` displays user-facing message
- Never expose stack traces to client
- Distinguish user errors (4xx, actionable message) from system errors (5xx, generic message)

**Loading States:**
- Flutter: `AsyncValue.loading` → shimmer/skeleton UI (not spinners)
- Backend: no loading concept — respond or error
- Import pipeline: `ImportJob.status` enum (`pending`, `processing`, `review_needed`, `completed`, `failed`)

**Auth Flow:**
- dio interceptor attaches `Authorization: Bearer {token}` to every request
- Token refresh: interceptor catches 401, refreshes via Auth0, retries original request
- AppSync: same JWT passed via amplify auth configuration
- No anonymous access — all endpoints require auth

**Validation:**
- Backend: Pydantic validates request body (automatic via FastAPI)
- Frontend: form-level validation before submission (instant feedback)
- Database: constraints as last line of defense (NOT NULL, UNIQUE, CHECK)
- Don't duplicate backend validation logic in frontend — validate shape/required only

### Enforcement Guidelines

**All AI Agents MUST:**
1. Follow the `Endpoint` class pattern for every new API operation
2. Use existing `success()` helper for all API responses
3. Create Alembic migrations for any schema changes (never raw SQL)
4. Write tests in `services/{service}/tests/test_{feature}.py`
5. Use `snake_case` for all Python, database, and JSON field names
6. Use Riverpod `AsyncValue<T>` for all server-fetched data in Flutter
7. Use `freezed` for all data model classes in Flutter
8. Soft delete via `archived_at` — never hard delete user data

**Anti-Patterns to Avoid:**
- Creating new response wrapper formats (use `success()`)
- Putting business logic in routers (use `Endpoint` classes)
- Using `setState` in Flutter (use Riverpod providers)
- Hard-coding URLs or API paths (use constants)
- Creating new base classes when existing ones suffice
- Skipping the `Params`/`Response` inner classes on Endpoints

## Project Structure & Boundaries

### Complete Project Directory Structure

```
palateful/
├── .github/
│   └── workflows/
│       └── ci.yml                          # GitHub Actions CI/CD pipeline
├── app/                                     # Flutter mobile + web app
│   ├── lib/
│   │   ├── main.dart                       # App entry point
│   │   ├── firebase_options.dart           # Firebase config (generated)
│   │   ├── core/
│   │   │   ├── config/
│   │   │   │   └── environment.dart        # API URLs, env config
│   │   │   ├── di/
│   │   │   │   └── injection.dart          # Dependency injection setup
│   │   │   ├── router/
│   │   │   │   └── app_router.dart         # go_router configuration
│   │   │   ├── services/
│   │   │   │   ├── api_client.dart         # dio HTTP client + interceptors
│   │   │   │   ├── auth_service.dart       # Auth0 integration
│   │   │   │   ├── auth_service_stub.dart  # Auth stub for testing
│   │   │   │   ├── auth_service_web.dart   # Web-specific auth
│   │   │   │   └── push_notification_service.dart
│   │   │   └── theme/
│   │   │       ├── app_colors.dart         # Cream/chocolate palette
│   │   │       ├── app_theme.dart          # Material 3 theme data
│   │   │       └── theme.dart              # Theme exports
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   │   └── login_screen.dart
│   │   │   ├── home/
│   │   │   │   ├── home_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── batch_import_status_widget.dart
│   │   │   │       ├── batch_job_result_sheet.dart
│   │   │   │       ├── meal_filter_bar.dart
│   │   │   │       ├── recipe_card.dart
│   │   │   │       └── sort_chips.dart
│   │   │   ├── onboarding/
│   │   │   │   ├── onboarding_start_screen.dart
│   │   │   │   └── onboarding_welcome_screen.dart
│   │   │   ├── recipe_books/
│   │   │   │   ├── recipe_book_detail_screen.dart
│   │   │   │   └── recipe_books_screen.dart
│   │   │   ├── recipes/
│   │   │   │   ├── recipe_detail_screen.dart
│   │   │   │   ├── add_recipe/
│   │   │   │   │   ├── add_recipe_sheet.dart
│   │   │   │   │   ├── batch_parser_service.dart
│   │   │   │   │   ├── file_import_screen.dart
│   │   │   │   │   ├── photo_capture_screen.dart
│   │   │   │   │   └── recipe_wizard_screen.dart
│   │   │   │   ├── cook_mode/
│   │   │   │   │   ├── cook_mode_screen.dart
│   │   │   │   │   └── widgets/
│   │   │   │   │       ├── ingredient_strip.dart
│   │   │   │   │       └── step_navigator.dart
│   │   │   │   ├── providers/              # Riverpod providers
│   │   │   │   └── models/                 # Freezed models
│   │   │   ├── search/
│   │   │   │   └── search_screen.dart
│   │   │   ├── shopping_cart/
│   │   │   │   ├── shopping_cart.dart
│   │   │   │   ├── models/
│   │   │   │   ├── screens/
│   │   │   │   ├── services/
│   │   │   │   ├── providers/              # AppSync subscription providers
│   │   │   │   └── widgets/
│   │   │   ├── pantry/                     # Pantry feature
│   │   │   │   ├── screens/
│   │   │   │   ├── widgets/
│   │   │   │   ├── providers/
│   │   │   │   └── models/
│   │   │   ├── calendar/                   # Meal planning feature
│   │   │   │   ├── screens/
│   │   │   │   ├── widgets/
│   │   │   │   ├── providers/
│   │   │   │   └── models/
│   │   │   ├── chat/                       # AI chat feature
│   │   │   │   ├── screens/
│   │   │   │   ├── widgets/
│   │   │   │   ├── providers/
│   │   │   │   └── models/
│   │   │   └── profile/                    # User profile/settings
│   │   │       ├── screens/
│   │   │       └── widgets/
│   │   └── shared/
│   │       ├── widgets/
│   │       └── providers/                  # Shared providers (auth, user)
│   ├── test/
│   ├── pubspec.yaml
│   ├── analysis_options.yaml
│   └── build.yaml                          # build_runner config
├── services/
│   ├── api/                                # FastAPI REST API
│   │   ├── Dockerfile
│   │   ├── project.json
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── dependencies.py             # Auth, DB dependencies
│   │   │   ├── api/v1/                     # Endpoint classes by resource
│   │   │   │   ├── friends/                # 8 endpoints
│   │   │   │   ├── import_job/             # 7 endpoints
│   │   │   │   ├── ingredient/             # 3 endpoints
│   │   │   │   ├── invitations/            # 7 endpoints
│   │   │   │   ├── invite_links/           # 4 endpoints
│   │   │   │   ├── meal_event/             # 8 endpoints
│   │   │   │   ├── parser/                 # 4 endpoints
│   │   │   │   ├── recipe/                 # 6 endpoints
│   │   │   │   ├── recipe_book/            # 6 endpoints
│   │   │   │   ├── search/                 # 1 endpoint (unified)
│   │   │   │   ├── shopping_list/          # 17 endpoints
│   │   │   │   ├── timer/                  # 4 endpoints
│   │   │   │   └── user/                   # 7 endpoints
│   │   │   ├── routers/v1/                 # One router per resource
│   │   │   └── schemas/                    # Pydantic schemas
│   │   └── tests/                          # API integration tests
│   ├── worker/                             # Celery async workers
│   │   ├── Dockerfile
│   │   ├── project.json
│   │   └── src/worker/
│   ├── parser/                             # HunyuanOCR GPU service
│   │   ├── Dockerfile
│   │   ├── project.json
│   │   └── src/parser/
│   ├── migrator/                           # Alembic migrations
│   │   ├── Dockerfile
│   │   ├── project.json
│   │   ├── alembic.ini
│   │   └── migrations/versions/
│   └── eval/                               # AI/OCR evaluation suite (dev only)
├── libraries/
│   ├── utils/                              # Shared business logic
│   │   └── utils/
│   │       ├── api/                        # Endpoint base, exceptions
│   │       ├── classes/                    # Enums, error codes
│   │       ├── db/                         # Database utilities
│   │       ├── models/                     # SQLAlchemy models (30+)
│   │       ├── services/                   # Auth0, AWS, Celery, DB, push, extractors, units
│   │       ├── serializers/
│   │       └── tasks/                      # Celery task definitions
│   │           ├── import_tasks/           # Import pipeline chain
│   │           └── shopping_list_tasks/    # Deadline reminders
│   ├── agent/                              # AI agent (LangGraph)
│   │   └── agent/
│   │       ├── graph/                      # Agent graph, nodes, state
│   │       ├── llm/                        # LLM providers (OpenAI, Anthropic, Ollama)
│   │       └── tools/                      # Agent tools (pantry, recipes, preferences)
│   └── test-helper/                        # Shared test utilities + factories
├── terraform/
│   └── modules/
│       ├── batch/main.tf                   # AWS Batch for OCR (existing)
│       ├── appsync/main.tf                 # AppSync for real-time
│       ├── ecs/main.tf                     # ECS Fargate for API/worker
│       ├── rds/main.tf                     # RDS PostgreSQL
│       └── networking/main.tf              # VPC, security groups
├── scripts/                                # Dev utility scripts
├── docs/                                   # Project documentation (22 files)
├── docker-compose.yml                      # Local development stack
├── nx.json                                 # NX workspace config
├── package.json
└── .env.example
```

### Architectural Boundaries

**API Boundaries:**
- All client requests enter through FastAPI `/v1/*` REST endpoints
- AppSync handles real-time subscriptions only (no CRUD through GraphQL)
- AI chat streaming uses SSE through FastAPI, not AppSync
- No direct database access from Flutter — always through API

**Service Boundaries:**
- `services/api` — HTTP request handling, delegates to `Endpoint` classes
- `services/worker` — Celery tasks only, no HTTP endpoints
- `services/parser` — Standalone GPU container, triggered by AWS Batch
- `services/eval` — Development-only, never deployed to prod
- `libraries/utils` — Shared by `api`, `worker`, `eval` (installed as Python package)
- `libraries/agent` — AI agent logic, used by `api` for chat endpoints
- `libraries/test-helper` — Shared test fixtures, used by all test suites

**Data Boundaries:**
- PostgreSQL is the single source of truth for all persistent data
- Redis is ephemeral — cache, Celery broker, rate limits
- S3 stores recipe images and OCR input/output (referenced by URL in DB)
- Riverpod offline persistence caches read-heavy data on device
- AppSync subscriptions push change events — client reconciles with local state

### Requirements to Structure Mapping

| Domain | API Endpoints | Models | Flutter Feature | Celery Tasks |
|--------|--------------|--------|-----------------|--------------|
| Recipe Management | `api/v1/recipe/`, `recipe_book/` | `recipe.py`, `recipe_book.py`, `recipe_step.py`, `recipe_ingredient.py` | `features/recipes/`, `features/recipe_books/` | — |
| Pantry | `api/v1/pantry/` | `pantry.py`, `pantry_ingredient.py`, `pantry_user.py` | `features/pantry/` | — |
| Import Pipeline | `api/v1/import_job/`, `parser/` | `import_job.py`, `import_item.py`, `ingredient_match.py` | `features/home/` (status) | `tasks/import_tasks/` |
| Shopping Lists | `api/v1/shopping_list/` | `shopping_list.py`, `shopping_list_event.py` | `features/shopping_cart/` | `tasks/shopping_list_tasks/` |
| Meal Planning | `api/v1/meal_event/` | `meal_event.py`, `prep_step.py` | `features/calendar/` | — |
| AI Chat | `api/v1/chat/` | `thread.py`, `chat.py` | `features/chat/` | — |
| Social | `api/v1/friends/`, `invitations/`, `invite_links/` | `friendship.py`, `invitation.py`, `invite_link.py` | `features/profile/` | — |
| Timers | `api/v1/timer/` | `active_timer.py` | `features/recipes/cook_mode/` | — |
| Search | `api/v1/search/` | Uses existing models | `features/search/` | — |

### Integration Points

**Internal Communication:**
- Flutter → API: dio HTTP over REST
- Flutter → AppSync: amplify_flutter GraphQL subscriptions
- API → Worker: Celery task dispatch via Redis
- API → Parser: AWS Batch job submission
- API → Firebase: Push notifications
- Worker → Database: Direct SQLAlchemy

**External Integrations:**
- Auth0 — JWT issuance and validation
- OpenAI — gpt-4o-mini for chat, extraction, matching
- AWS S3 — Image storage, OCR I/O
- AWS Batch — GPU OCR execution
- AWS AppSync — Real-time subscriptions
- Firebase — Push notifications (FCM)

**Data Flow (Recipe Import):**
```
Flutter → POST /v1/imports (dio)
  → API creates ImportJob → dispatches Celery chain
    → ParseSourceTask → ExtractRecipeTask → MatchIngredientsTask
      → (high confidence) CreateRecipeTask
      → (low confidence) mark for review
    → Push notification → Firebase → Flutter
```

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices are compatible. FastAPI + SQLAlchemy async + Alembic (backend), Flutter + Riverpod 3.0 + go_router + dio + freezed (frontend), amplify_flutter for AppSync + dio for REST coexist cleanly. Auth0 JWT validates across both FastAPI and AppSync. No contradictory decisions found.

**Pattern Consistency:** snake_case everywhere on backend (Python, DB, JSON). Feature-first organization on both backend (`api/v1/{resource}/`) and frontend (`features/{feature}/`). `Endpoint` class pattern mirrors Riverpod provider pattern — both single-responsibility. Error format consistent across REST responses.

**Structure Alignment:** Project structure supports all three runtime domains. Boundaries are clear with no circular dependencies. Libraries flow one-way into services.

### Requirements Coverage Validation

**Functional Requirements (61 FRs):** All covered.
- Recipe Management → `api/v1/recipe/`, `recipe_book/`, Flutter `features/recipes/`
- Pantry Management → models + `api/v1/pantry/` + Flutter `features/pantry/`
- Import Pipeline → tiered extraction, worker tasks, status tracking
- Shopping Lists → AppSync real-time sync, conflict resolution
- Meal Planning → `api/v1/meal_event/` + Flutter `features/calendar/`
- AI Features → `libraries/agent/` + SSE streaming + Flutter `features/chat/`
- Social/Sharing → invitations, invite links, friends endpoints

**Non-Functional Requirements (31 NFRs):** All addressed.
- Performance: FastAPI async + PostgreSQL pooling + Redis caching
- Security: Auth0 JWT + RBAC via Depends() + HTTPS + CORS
- Scalability: ECS Fargate + scale-to-zero GPU OCR + Celery workers
- Reliability: Celery retry (3x), Batch retry (3x), import status tracking
- Cost efficiency: Tiered AI strategies, Spot GPU, scale-to-zero
- Accessibility: WCAG AA, cook mode large touch targets

### Implementation Readiness Validation

**Decision Completeness:** All critical technology decisions documented with specific versions/packages. Implementation patterns cover naming, structure, format, communication, and process. Enforcement guidelines and anti-patterns listed.

### Gap Analysis Results

**No critical gaps.**

**Important gaps (addressable during implementation):**
1. AppSync GraphQL schema — placeholder until shopping list sync stories
2. Riverpod provider migration — existing Flutter code migrates incrementally per feature
3. CI/CD workflow expansion — `ci.yml` needs Docker builds, Terraform, Flutter web steps

**Minor gaps (deferred):**
- No monitoring beyond CloudWatch — acceptable for MVP
- No API rate limiting — not needed until public launch
- No CDN for Flutter Web — defer until web is production-ready

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed (61 FRs, 31 NFRs)
- [x] Scale and complexity assessed (high, full-stack mobile + API)
- [x] Technical constraints identified (brownfield, existing services)
- [x] Cross-cutting concerns mapped (8 concerns)

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified (backend + frontend + infra)
- [x] Integration patterns defined (REST + AppSync + SSE + Firebase)
- [x] Performance considerations addressed (caching, async, scale-to-zero)

**Implementation Patterns**
- [x] Naming conventions established (DB, API, Python, Dart)
- [x] Structure patterns defined (backend + frontend)
- [x] Communication patterns specified (Celery, AppSync, Riverpod)
- [x] Process patterns documented (errors, loading, auth, validation)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established (6 service boundaries)
- [x] Integration points mapped (6 internal, 6 external)
- [x] Requirements to structure mapping complete (10 domains)

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level:** High

**Key Strengths:**
- Brownfield architecture leverages 80%+ existing decisions — low risk
- Three runtime domains cleanly separated with no coupling
- Existing Endpoint/Router pattern battle-tested with 80+ endpoints
- Flutter library choices (Riverpod, go_router, freezed) are mature
- Tiered AI cost strategy prevents runaway spend

**Areas for Future Enhancement:**
- AppSync schema design (Phase 2-3)
- Monitoring/alerting beyond CloudWatch (at scale)
- CDN and edge caching for Flutter Web (when web goes live)
- Self-hosted LLM evaluation (10K+ users)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**
1. Install Flutter libraries (Riverpod, go_router, dio, freezed, amplify_flutter) in `app/pubspec.yaml`
2. Set up core architecture (theme update, routing migration, dio interceptors, base providers)
3. Auth flow integration (Auth0 → dio JWT interceptor)
4. Begin feature module implementation per sprint plan


---

## Addendum — 2026-04-17 — Rolling-Window Materialization for Recurring Meal Plans

This addendum covers the one new cross-cutting pattern introduced by the recurring-meal-plans epic: a rolling-window materialization strategy for rule → occurrence expansion. No new services, languages, or infra; one new table and one scheduled job.

### Pattern: Rolling-Window Materialization

**Problem.** Recurring rules ("Every Monday lunch") could either be (a) pre-materialized on write into concrete rows, (b) virtualized on read in the list endpoint, or (c) a hybrid. Pure pre-materialization explodes the `meal_events` table and wastes writes for occurrences users never look at. Pure virtualization complicates every read path that joins `meal_events` (shopping-list aggregation, prep-step coupling, participant invites) and forces client-side merging. Hybrid lands where the real work is: users see concrete rows, the system caps how far forward occurrences exist.

**Decision.** Rule occurrences materialize as concrete `meal_events` rows with a `recurrence_rule_id` FK pointing back to the rule. The materialization covers a rolling window of **current week + 8 weeks forward** (roughly the planning horizon real users operate at). Triggers:

- **On rule create/edit**: run materialization for the current window inside the same transaction. Editing with "All occurrences" scope regenerates all future materialized rows (deletes + re-inserts); editing with "This and following" splits the rule and materializes the new child rule; editing with "This occurrence only" detaches one `meal_event` row from its rule (clears `recurrence_rule_id`) and edits it as a one-off.
- **On `ListMealEvents` reads that cross the window boundary**: if the requested `end_date` exceeds the rule's `materialized_through` watermark, the endpoint extends materialization up to the requested date before querying. Bounded work per request; never arbitrary.
- **Nightly job** (new — runs in the existing `worker` service): advances the window for every active rule (current week + 8 weeks forward), and archives materialized rows that are older than 6 months to keep the table bounded.

**Why this shape:**
- Every existing read path that joins `meal_events` (shopping-list aggregation via `PopulateFromCalendarRange`, prep-step expansion, participant invites, weekly calendar) keeps working with zero changes because it still sees concrete rows. No cross-cutting refactor.
- Materialization is idempotent (regenerate deletes existing future rows that belong to the rule, then re-inserts) which survives retry, concurrent edits, and the nightly job running twice.
- Per-occurrence overrides are trivial: detaching a row (`recurrence_rule_id := NULL`) is enough to make it immune to future regeneration passes.
- Latency: the hot-path extension check is a bounded `SELECT` per user per request (`SELECT ... WHERE materialized_through < :requested_end_date`). Expansion beyond the window is rare and bounded. NFR37 caps the baseline drift.

**What this rules out:**
- Client-side rule expansion. The Flutter client has no visibility into rules during calendar reads; it renders `meal_events` rows verbatim as it does today. The only new Flutter state is the `Recurring Plans` list screen, which talks to a new dedicated rules endpoint.
- Storing rules without materialization (pure-virtual). Rejected because every downstream join would need rewriting.
- Generating occurrences permanently into the table (pure pre-materialize). Rejected because a "forever" rule with daily-weekday selection would blow up the row count.

### New Data Model

- **`meal_recurrence_rules`** (new table): stores the rule — slot, weekday selection (JSONB or a weekday-chip array column), interval (weekly / biweekly / monthly-nth-weekday), optional end-date, recipe link, owner, household sharing, and a `materialized_through` watermark (DATE). FK from `meal_events.recurrence_rule_id` (nullable; SET NULL on rule delete so orphaned historical rows remain queryable).
- **`meal_events.recurrence_rule_id`** (new column): nullable UUID FK to `meal_recurrence_rules.id`. Non-null rows are materialized occurrences; null rows are one-offs (including detached overrides).

Legacy `meal_events.is_recurring`, `recurrence_rule`, `recurrence_end_date`, `parent_event_id` columns are left in place for backward compatibility with any legacy clients (marked for removal in a follow-up epic once this ships and stabilizes).

### New Service Surface

A dedicated router namespace for recurrence rules: `POST/GET/PUT/DELETE /api/v1/recurrence-rules`, plus `GET /api/v1/recurrence-rules` (list for the user). Lives alongside the existing `meal_event_router.py` at `services/api/src/routers/v1/recurrence_rule_router.py`. Endpoints follow the existing `Endpoint` pattern (single-handler-per-file under `services/api/src/api/v1/recurrence_rule/`).

### Impact on Existing Consistency Rules

- **Directory patterns**: new handlers live at `services/api/src/api/v1/recurrence_rule/*.py`; new model at `libraries/utils/utils/models/meal_recurrence_rule.py`. Follows existing per-endpoint-file convention.
- **Migration**: one alembic revision adding the new table + FK column. Located in `services/migrator/migrations/versions/`.
- **Worker job**: new scheduled task registered in the existing `worker` service. No new worker infra.
- **No feature flags**: per existing project pattern; the feature ships directly. Legacy columns stay as read-through compatibility for any stragglers.
