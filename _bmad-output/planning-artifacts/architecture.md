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

---

## Addendum — 2026-04-17 — Calendar as First-Class Container (multiple switchable calendars, full co-edit)

This addendum introduces one new cross-cutting primitive: **Calendar** as a shareable container for `meal_events` and `meal_recurrence_rules`. Mirrors the existing `recipe_book` shape. No new services, languages, infrastructure, or queues — one new table, one new join table, one extended invitation resource_type, one backfill migration.

### Pattern: Calendar Container (parallels `recipe_book`)

**Problem.** Every meal_event today is owner-scoped via `owner_id`. Sharing is one meal at a time via `meal_event_participants` (host/cohost/guest). This breaks down as soon as users want:
- Blanket edit rights on "our shared household calendar" — they currently have to re-invite on every meal.
- More than one logical calendar (personal meal prep vs. shared-with-partner dinners).
- A way to keep some meals private while collaborating on others.

**Decision.** Introduce a `calendars` table (id, owner_id, name, is_shared, is_default, color, archived_at) and a `calendar_users` join table (calendar_id, user_id, role ∈ {owner, editor}). Every `meal_event` and every `meal_recurrence_rule` gets a **mandatory `calendar_id` FK**. The calendar is the unit of sharing; per-meal `meal_event_participants` stays as-is for per-meal invite semantics but no longer grants edit rights (calendar membership does).

Authorization moves one level up: "can user X read/write meal_event Y?" becomes "is user X an owner or editor on `meal_event.calendar_id`?" A single indexed lookup on `calendar_users (calendar_id, user_id)` replaces the current composite check (owner_id match OR participant-table role lookup).

### New Data Model

- **`calendars`** (new table): `id UUID`, `owner_id UUID FK users`, `name VARCHAR(128) NOT NULL`, `description TEXT NULL`, `is_shared BOOLEAN DEFAULT false`, `is_default BOOLEAN DEFAULT false`, `color VARCHAR(7) NULL` (reserved hex, not surfaced in UI), `archived_at TIMESTAMPTZ NULL`, plus `created_at`/`updated_at`. Indexes: `(owner_id)`, `(owner_id, is_default)` for default lookup.
- **`calendar_users`** (new join table): `calendar_id UUID FK calendars`, `user_id UUID FK users`, composite PK `(calendar_id, user_id)`, `role VARCHAR(16) CHECK role IN ('owner','editor')`, `invited_by_id UUID NULL FK users`, `last_opened_at TIMESTAMPTZ NULL`, plus `created_at`/`updated_at`/`archived_at`. Indexes: `(user_id, archived_at)` for per-user calendar lists, `(calendar_id)` for member lists.
- **`meal_events.calendar_id`** (new column, NOT NULL after backfill): UUID FK to `calendars.id`, ON DELETE RESTRICT (calendar archive cascades via `archived_at`, not hard delete). Index: `(calendar_id, scheduled_at)` for per-calendar range queries.
- **`meal_recurrence_rules.calendar_id`** (new column, NOT NULL after backfill): UUID FK to `calendars.id`, ON DELETE RESTRICT. Index: `(calendar_id)` for per-calendar rule lists.

### Backfill Migration (one-time, data migration)

Runs in a single alembic revision. Sequence:

1. Create `calendars` and `calendar_users` tables + indexes.
2. Add `meal_events.calendar_id` as **nullable** initially.
3. Add `meal_recurrence_rules.calendar_id` as **nullable** initially.
4. For each distinct `user_id` in `users`: insert one row into `calendars` with `name = 'My Calendar'`, `is_default = true`, `owner_id = user.id`; insert one row into `calendar_users` with `role = 'owner'`, `user_id = user.id`.
5. `UPDATE meal_events SET calendar_id = (SELECT id FROM calendars WHERE owner_id = meal_events.owner_id AND is_default = true)`.
6. `UPDATE meal_recurrence_rules SET calendar_id = (SELECT id FROM calendars WHERE owner_id = meal_recurrence_rules.owner_id AND is_default = true)`.
7. Alter both columns to `NOT NULL`.
8. Verify: `SELECT COUNT(*) FROM meal_events WHERE calendar_id IS NULL` → 0. Same for `meal_recurrence_rules`. If non-zero, abort migration (data integrity check).

Migration is re-runnable: step 4's `INSERT ... ON CONFLICT DO NOTHING` on `(owner_id, is_default)` index makes the default-calendar insert idempotent. Steps 5–6 are idempotent because they only update NULL rows.

**Reversibility**: down-migration drops `calendar_id` FKs from `meal_events` and `meal_recurrence_rules`, then drops `calendar_users` and `calendars`. Event/rule data stays owner-scoped as it was. Backup snapshot taken before the forward migration.

### New Service Surface

- `services/api/src/api/v1/calendar/*.py` (new handler directory): `create_calendar.py`, `get_calendar.py`, `list_calendars.py`, `update_calendar.py`, `delete_calendar.py`, `list_calendar_members.py`, `update_calendar_member.py`, `remove_calendar_member.py`.
- `services/api/src/routers/v1/calendar_router.py` (new): registers the calendar endpoints under `/api/v1/calendars`.
- **Invitation plumbing extension** (`services/api/src/api/v1/invitations/helpers.py`): add `"calendar": {"editor"}` to `VALID_ROLES` (owner is implicit via `owner_id`, not invitable). Add a conditional branch to `check_resource_permission()` that queries `calendars` + `calendar_users`. Add a conditional branch to `create_membership()` that inserts into `calendar_users`. Add a resource-name lookup for `get_resource_name()`.
- **`meal_event` handlers** (`services/api/src/api/v1/meal_event/*.py`): every handler's permission check is rewritten to check `calendar_users` membership instead of `owner_id`/participant role. `create_meal_event.py` reads `calendar_id` from the request (required). `list_meal_events.py`, `get_meal_event.py`, etc. all scope to the requested calendar (or union across calendars if no `calendar_id` query param — used by `PopulateFromCalendarRange`).
- **`recurrence_rule` handlers** (`services/api/src/api/v1/recurrence_rule/*.py`): same treatment. `create_recurrence_rule.py` reads `calendar_id` from the request. List scopes to the requested calendar.
- **`shopping_list.populate_from_calendar_range.py`** (modify): replace the current owner-scoped `meal_events` WHERE with `calendar_id IN (SELECT calendar_id FROM calendar_users WHERE user_id = :user_id AND archived_at IS NULL)`. No API shape change.
- **User-provisioning flow** (wherever new users are created on first Auth0 signup — typically `services/api/src/api/v1/user/create_or_sync_user.py` or the Auth0 JWT interceptor): emit one `calendars` row with `name = 'My Calendar'`, `is_default = true`, plus a `calendar_users` row with `role = 'owner'` atomically with user creation.

### Authorization Model

A user can read/write a meal_event or recurrence rule iff they have an active (`archived_at IS NULL`) row in `calendar_users` for the resource's `calendar_id`. Both roles (`owner`, `editor`) grant full CRUD on meal_events and rules. Only `owner` can:

- Modify calendar metadata (name, description).
- Archive the calendar.
- Add, remove, or change the role of other members.
- Transfer ownership (by promoting another member to owner — implemented as `UPDATE calendar_users SET role = 'owner' WHERE ...` + `UPDATE calendar_users SET role = 'editor' WHERE user_id = current_owner`; a single transaction). Kept minimal — no dedicated "transfer" button per PRD.

Legacy `meal_event_participants` host/cohost/guest roles remain functional for per-meal invite semantics but are **ignored for edit authorization**. A `guest` participant who isn't a calendar editor cannot edit the meal. This is a semantic narrowing of the previous model; tests and documentation must call it out.

### Impact on Existing Consistency Rules

- **Directory patterns**: new handlers live at `services/api/src/api/v1/calendar/*.py`; new models at `libraries/utils/utils/models/calendar.py` and `calendar_user.py`. Follows existing per-endpoint-file convention.
- **Migration**: one alembic revision — new tables + two FK columns + backfill + NOT NULL tightening. Located in `services/migrator/migrations/versions/`. Naming: `<YYYYMMDDHHMMSS>_add_calendars.py`.
- **Invitation system**: `VALID_ROLES`, `check_resource_permission()`, `create_membership()`, `get_resource_name()` all get a new `"calendar"` branch. Error codes for calendar-specific failures reserved in the 26x range (e.g., `CALENDAR_CANNOT_DELETE_LAST`).
- **No new worker jobs**: the recurring-meals nightly materializer already iterates by rule; no per-calendar scheduling needed. The materializer's cross-calendar behavior is unchanged — it walks all active rules regardless of calendar.
- **No new AWS resources, no Terraform changes, no new queues.**
- **No feature flags**: per existing project pattern; the feature ships directly behind the passing backfill migration.
- **Field-render policy**: every new server-returned field on `meal_events` (namely `calendar_id`) is rendered or intentionally omitted from the Flutter client. The calendar switcher renders `calendar.name` + `calendar.is_shared` + `calendar.member_count`.
- **Idempotency**: calendar creation, rename, and member add/remove are all idempotent on retry via the usual `INSERT ... ON CONFLICT` / `UPDATE ... WHERE` patterns.
- **Audit**: calendar delete writes to `error_logs` with `service="audit"` (matches the `promote_admin.py` pattern) so we can forensically reconstruct archive events without polluting error dashboards.

---

## Addendum — 2026-04-18 — Operator Observability: Latency Metrics & User Feedback

One new cross-cutting pattern (**Batched Async Writer for high-frequency capture**) plus two straightforward append-only tables and one Celery fan-out task. No new services, no new AWS resources, no new language or queue runtime.

### Pattern: Batched Async Writer for High-Frequency Event Capture

**Problem.** Measuring per-request latency (and per-Celery-task latency) means emitting one datapoint per event. Even at 50 users and 5 req/sec that's ~400k rows/day. Writing synchronously from the hot path inflates response time (one DB round-trip per request is untenable at sub-200ms targets, NFR1/NFR4). Shipping to CloudWatch EMF costs money the budget doesn't have (NFR29) and ties us to AWS metrics cardinality limits. Prometheus sidecars + Grafana introduce ops burden that is out of proportion to <50 users.

**Decision.** A new primitive — **`BatchedLatencyWriter`** — lives in `libraries/utils/utils/services/observability/batched_latency_writer.py`. Singleton per process (API worker / Celery worker). In-memory `asyncio.Queue` (API side) or a lightweight `threading.Queue` (Celery side) accepts dicts with the fields we care about. A background coroutine / thread flushes on the first of: 100 samples queued, 2 seconds elapsed, or process shutdown (SIGTERM handler). Flush is one `INSERT ... VALUES (...), (...), ...` per table.

Queue-full policy is **drop-oldest, never block**. The hot path cannot wait on the writer. Dropped samples are counted and logged at WARNING level every minute so sample loss is observable without being flood-prone.

**Why this shape.**
- Single-digit microseconds of hot-path overhead (enqueue is lock-free on Python 3.10+ asyncio.Queue).
- Batch size of 100 amortizes DB round-trip cost: one INSERT per 2 seconds worst case vs one per request.
- Postgres handles multi-row INSERT at >10k rows/sec on t4g.micro without CPU credit depletion; the batching gives us ~50 inserts/sec under load.
- Zero dependency on AWS-side metrics cardinality limits; the tables are pure append-only with B-tree indexes; pruning is a nightly Celery task.
- Pattern is generic — if a future signal (e.g., AI-tool-call durations, push-notification round-trip times) needs the same capture shape, the same class handles it with a different table name.

**What this rules out.**
- **Synchronous writes per request.** Rejected on NFR1 / NFR4.
- **CloudWatch Embedded Metric Format.** Rejected on NFR29; revisit if we leave friends-and-family scale.
- **Prometheus sidecar on ECS.** Rejected on ops burden; revisit if we hire ops or cross 500 users.

### New Data Model

Two append-only tables. Partitioning explicitly skipped — 30-day retention + a single composite index keeps us on the default heap table without pain at expected volume (NFR51).

- **`request_latencies`** (new): `id UUID PK`, `method VARCHAR(8) NOT NULL`, `normalized_path VARCHAR(256) NOT NULL`, `status_code SMALLINT NOT NULL`, `duration_ms INTEGER NOT NULL`, `user_id UUID NULL FK users ON DELETE SET NULL`, `request_id VARCHAR(64) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Indexes: `ix_request_latencies_created_path (created_at DESC, normalized_path)`, `ix_request_latencies_created (created_at DESC)` for admin-dashboard overall-p95 query. User FK is `SET NULL` on user delete so samples survive user offboarding but don't dangle.
- **`task_latencies`** (new): `id UUID PK`, `task_name VARCHAR(128) NOT NULL`, `task_id VARCHAR(64) NOT NULL`, `duration_ms INTEGER NOT NULL`, `status VARCHAR(16) NOT NULL CHECK status IN ('success','failure','retry')`, `queue_name VARCHAR(64) NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Indexes: `ix_task_latencies_created_task (created_at DESC, task_name)`, `ix_task_latencies_created (created_at DESC)`.
- **`user_feedbacks`** (new): `id UUID PK`, `user_id UUID NOT NULL FK users ON DELETE CASCADE`, `body TEXT NOT NULL CHECK length(body) BETWEEN 1 AND 4000`, `category VARCHAR(16) NULL CHECK category IN ('bug','idea','praise','other')`, `context JSONB NULL` (app_version, platform, route, recipe_id), `status VARCHAR(16) NOT NULL DEFAULT 'unread' CHECK status IN ('unread','read','archived')`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Indexes: `ix_user_feedbacks_status_created (status, created_at DESC)` for the filtered inbox queries, `ix_user_feedbacks_user (user_id)`. Status-change updates `updated_at` via a SQLAlchemy event hook.

All three tables live alongside existing models in `libraries/utils/utils/models/`.

### New Service Surface

- **FastAPI middleware** (`services/api/src/middleware/latency_capture.py`): runs after routing, captures start-time, on response enqueues the sample. `/health` and `/ready` are hard-skipped. Path normalization uses FastAPI's `request.scope['route'].path` (the template path, e.g. `/v1/recipes/{recipe_id}`) rather than the raw URL, eliminating cardinality explosion from UUIDs in paths.
- **Celery signal handlers** (`libraries/utils/utils/services/observability/celery_hooks.py`): `task_prerun` stores `start_time` in task context; `task_postrun` computes `duration_ms` and enqueues via the thread-safe writer; `task_failure` does the same with `status='failure'`. Wired in the existing `celery.py` app configuration.
- **Aggregation endpoints** at `services/api/src/api/v1/admin/get_endpoint_metrics.py` and `get_task_metrics.py` — follow the existing `Endpoint` pattern. Each returns the percentile breakdown + sparkline via a single query using Postgres `percentile_cont() WITHIN GROUP` and `generate_series` for bucketing.
- **`user_feedbacks` endpoints** at `services/api/src/api/v1/user/create_user_feedback.py` (user-facing) and `services/api/src/api/v1/admin/{list_feedback.py, update_feedback_status.py}` (admin-only; `require_admin`).
- **Admin notify fan-out task** at `libraries/utils/utils/tasks/notification_tasks/notify_admins_new_feedback.py` — loads every `is_admin=true` user and calls `PushNotificationService.send_to_user(..., type=NEW_FEEDBACK, force=True)` for each. `NEW_FEEDBACK` is a new value on the existing `NotificationType` enum in `libraries/utils/utils/models/notification.py`.
- **Nightly prune task** at `libraries/utils/utils/tasks/observability_tasks/cleanup_latency_samples.py` — wired into the existing Celery beat schedule in `libraries/utils/utils/services/celery.py`, runs at the same 02:00 UTC slot as `cleanup_error_logs`.
- **Prod script** at `services/api/scripts/fetch_feedback.py` — direct `DATABASE_URL`, argparse CLI, streams CSV/TSV/JSON-lines to stdout, writes audit row to `error_logs`.

### Extension to Existing Consistency Rules

- **Directory**: new handlers under `services/api/src/api/v1/admin/` and `services/api/src/api/v1/user/`. New services under `libraries/utils/utils/services/observability/`. New tasks under `libraries/utils/utils/tasks/{notification_tasks, observability_tasks}/`. Follows existing convention.
- **Migration**: one alembic revision adds all three tables + indexes. Located in `services/migrator/migrations/versions/`. Naming: `<ts>_add_latencies_and_feedbacks.py`.
- **No feature flags**: the latency capture is safe-by-construction (drop-oldest on queue-full); the feedback endpoint is behind auth; ships directly.
- **No new AWS resources, no Terraform changes, no new queues.** Celery fan-out task reuses the existing `default` queue. Nightly prune reuses the existing beat schedule.
- **Audit**: feedback status-change (`read` or `archive`) writes an `error_logs` row with `service="audit"` and `error_type="FeedbackStatusChange"` (matches `promote_admin.py`). The prod fetch-feedback script writes `service="audit"`, `error_type="FeedbackExport"` per run.
- **Idempotency**: feedback status-change is idempotent (setting `read` on an already-read row is a no-op at the SQL level). Latency sample inserts are append-only and carry a unique UUID id, so double-submit on retry is harmless but not automatically deduped — acceptable because the batched writer does not retry (drop-on-failure over double-count).
- **Notification enum extension**: `NotificationType.NEW_FEEDBACK` is the first new enum value since Epic 12; the existing migration pattern is `op.execute("ALTER TYPE notification_type ADD VALUE 'NEW_FEEDBACK'")` inside the alembic revision.

## Addendum — 2026-04-18 — Universal Share Ingest

### New iOS app target: `PalatefulShare`

- A third iOS app-extension target is added alongside `PalatefulWidgets` and `PalatefulNotificationService`. Swift + SwiftUI; no Objective-C, no new Pod dependencies initially.
- Uses the existing App Group `group.com.palateful.app` for optional state handoff (pending-import counter for the main app badge; not for file transfer).
- `NSExtensionActivationRule` accepts URL, Image, File, PDF, Movie, and plain Text. Single-item constraint (`MaxCount=1` per type) for v1 — multi-file share is deferred.
- Presigned S3 PUT uploads file content directly from the extension; extension calls `POST /v1/recipe-books/{book_id}/import` with the resulting `s3_key`. Main app is not required to be running.
- Code signing: new bundle ID `com.palateful.app.shareextension`. App Store Connect changes required: new App ID, new provisioning profile, enable App Group capability. Xcode Cloud `ci_scripts/ci_post_clone.sh` needs no changes (Pods handled via existing scheme); the new target must be added to the build scheme.

### Backend additions

- **New source_type `video_file`** — local video uploads (e.g., Photos app on iOS, Files on Android). Distinct from the existing `url` path that handles social media video URLs (TikTok/Instagram/YouTube) via yt-dlp metadata + audio fallback. `video_file` uses ffmpeg to extract the audio track, then reuses the existing Whisper → text extraction path. Worker-only dependency; no change to API container.
- **ffmpeg in `services/worker/Dockerfile`** — installed via apt-get in the builder and final stages. LGPL-compatible build used; no GPL codec licensing exposure.
- **New import endpoint `POST /v1/imports/upload-url`** — presigned S3 PUT URL for import files. Accepts `{ filename, mime_type, size_bytes }`; returns `{ upload_url, s3_key, expires_at }`. URL valid for 1 hour.
- **Updated `POST /v1/recipe-books/{book_id}/import`** — adds `s3_key` field (alternative to `file_base64`) for file-based source types. When `s3_key` is set, the worker reads from S3 in `ParseSourceTask` instead of decoding base64 in the endpoint.
- **Size enforcement** — 100 MB hard cap enforced server-side at `upload-url` request time (via `size_bytes`) and again on the presigned URL signature (`Content-Length-Range` condition). Files exceeding the cap get a 413 response before any upload begins.

### S3 bucket

- **New bucket `palateful-imports-{env}`** — scratch storage for shared-in files awaiting worker processing. 7-day lifecycle rule in dev; 30-day in prod. Worker IAM role extended with `s3:GetObject` on this bucket.

### Social URL routing moves upstream

- `libraries/utils/utils/services/url_classifier.py` (already exists per backend research) — its `detect_platform()` result is now called from the import endpoint at ImportItem creation time. `source_type` is set to `"video"` for social URLs and `"url"` for web URLs before the task chain dispatches. The extract task's existing social check remains as a defensive fallback.

### Push notification contract

- Existing `NotificationType.IMPORT_NEEDS_REVIEW` and `IMPORT_COMPLETE` push payloads are the primary completion signals after an extension-initiated import. The extension UI closes on presigned PUT success; the user sees the notification when the background task chain finishes. Deep link in the payload targets the Activity Hub (surviving through the `epic-activity-hub-redesign` IA change).

### What does NOT change

- No new queue, Lambda, Step Function, or API Gateway route aside from the one `/imports/upload-url` endpoint. No architectural shifts — this is additive.
- `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, Auth0 config all unchanged. No new secrets.
- Existing `share_import_screen.dart` URL path continues to work as the no-file fallback when a text/URL is shared on Android (or as a secondary iOS handoff).

## Addendum — 2026-04-18 — Meals (Higher-Order Recipe Grouping)

### New models

- **`meals`** — reusable bundle of 2+ recipes. Columns: `id` (UUID PK), `name` (string, required), `description` (text, nullable), `recipe_book_id` (UUID FK to `recipe_books`, required, ondelete CASCADE), `share_token` (string, nullable, unique when non-null), `archived_at` (nullable timestamp, inherited from Base), `created_at`, `updated_at`. Indexes: `(recipe_book_id)` for per-book list, partial unique on `share_token WHERE share_token IS NOT NULL`.
- **`meal_recipes`** — join table between `meals` and `recipes`. Columns: `meal_id` (UUID FK ondelete CASCADE), `recipe_id` (UUID FK ondelete RESTRICT — block component deletion with an in-use-in-meal check), `order_index` (int, not null, default 0), `created_at`. Composite PK `(meal_id, recipe_id)`. Secondary index on `recipe_id` for reverse-lookup ("which meals use this recipe?").

### Schema additions on existing tables

- **`meal_events.meal_id`** (UUID FK to `meals`, nullable, ondelete SET NULL). Check constraint `CHECK (num_nonnulls(recipe_id, meal_id) <= 1)` — both can be null (free-text event), at most one can be non-null. Indexed `(meal_id)` for reverse-lookup in admin stats.
- **`meal_recurrence_rules.meal_id`** — same shape, same constraint, same index pattern as above.

### New endpoints

- `POST /v1/recipe-books/{book_id}/meals` — create Meal inside a book (book write permission enforced via existing `recipe_book_user` check).
- `GET /v1/recipe-books/{book_id}/meals` — list Meals in a book, eager-loads component summaries.
- `GET /v1/meals` — list across all accessible books, paginated.
- `GET /v1/meals/{meal_id}` — Meal detail with hydrated components.
- `PATCH /v1/meals/{meal_id}` — update name/description/components/order; atomic.
- `POST /v1/meals/{meal_id}/recipes` — add a component recipe (body: `recipe_id`, optional `order_index`).
- `DELETE /v1/meals/{meal_id}/recipes/{recipe_id}` — remove a component.
- `POST /v1/meals/{meal_id}/archive` + `POST /v1/meals/{meal_id}/restore` — mirrors recipe archive/restore.
- `POST /v1/meals/{meal_id}/share` — generates/rotates `share_token`.
- `GET /v1/public/meals/{share_token}` — unauthenticated public page.
- `GET /v1/recipes/{recipe_id}/meals` — reverse-lookup ("which Meals include this recipe?") used by the recipe detail screen's Meals section.

### Extended endpoints

- **`POST /v1/meal-events`** — request accepts `meal_id` XOR `recipe_id`. Validation enforces the XOR; same check-constraint enforces it at the DB layer.
- **`PATCH /v1/meal-events/{id}`** — same XOR rule.
- **`POST /v1/meal-recurrence-rules`** — same.
- **`GET /v1/meal-events`** — response payload gains an optional `meal_summary` object (id, name, component count, top-4 component thumbnails) when `meal_id` is set.
- ~~**`POST /v1/shopping-lists/{id}/populate-from-calendar`**~~ — **removed 2026-04-18 per FR-CPMS-1.** Bulk calendar expansion is gone. Per-meal adds route through the existing `populate-from-recipe` endpoint today; a future `POST /v1/meal-events/{event_id}/add-to-shopping-list` will carry the Meal-expansion branch when `mcal-4`'s replacement story lands.
- **`GET /v1/search`** — query extended to OR across Meal names and component recipe names. Existing trigram and semantic indexes reused.
- **`GET /v1/admin/stats`** — gains Meal counts (total, active, archived, top books by count, most-scheduled over 30d).

### MCP tool additions

- `create_meal`, `get_meal`, `list_meals`, `update_meal`, `add_recipe_to_meal`, `remove_recipe_from_meal`, `archive_meal` — all auth-gated by the Meal's recipe_book membership.
- `create_meal_event` — extended to accept `meal_id` as alternative to `recipe_id`.

### Service layer

- `libraries/utils/utils/services/meal_service.py` — CRUD + component attach/detach + sum-within-meal ingredient aggregation helper (`aggregate_meal_ingredients(meal_id) -> list[AggregatedIngredient]`).
- `libraries/utils/utils/tasks/shopping_list_tasks/populate_from_calendar_range.py` (existing) — extended to dispatch to the Meal aggregation path when a meal_event has `meal_id` set.

### Migration

- One alembic revision: `<ts>_add_meals_and_meal_recipes.py`. Creates `meals`, `meal_recipes`, adds `meal_id` columns + check constraints to `meal_events` and `meal_recurrence_rules`, adds indexes. No backfill required — existing rows remain with `meal_id IS NULL`. The check constraints are added with `NOT VALID` then `VALIDATE` to avoid rewriting existing rows on a prod-sized table.

### No infra changes

- No new S3 bucket (Meals don't carry their own images in v1 — collage from component thumbnails is rendered client-side).
- No new IAM policies, no new secrets, no new queues, no new Lambdas.
- Standard `npx nx run api:docker-build` + `npx nx run migrator:docker-build` deploy path.

### Extension to existing consistency rules

- **Directory**: meal handlers under `services/api/src/api/v1/meals/`. Meal schemas under `services/api/src/schemas/meal.py`. Meal MCP tools under `services/api/src/mcp_server/tools/meals.py`. Follows existing shape (recipe, recipe_book, meal_event).
- **Auth**: every Meal mutation checks `recipe_book_user` membership on the Meal's book. Read endpoints respect the same rule. Public `share_token` endpoint is unauthenticated and returns only the limited public shape (name, description, component names, thumbnails; no ingredients/steps unless the component recipe also has its own share token).
- **Audit**: Meal archive/restore writes to `error_logs` with `service="audit"` (matches existing recipe archive pattern).
- **Coverage**: every handler has happy-path, auth-fail, not-found, component-unavailable, and XOR-constraint-violation branches covered to maintain the 100% API coverage bar.
