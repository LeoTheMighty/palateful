---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
status: 'complete'
completedAt: '2026-03-12'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# Palateful - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Palateful, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

- FR1: Users can create recipes with structured fields (title, description, ingredients with quantities/units, ordered steps, prep time, cook time, servings, source attribution, tags)
- FR2: Users can edit any recipe they own, with changes auto-creating a version snapshot when edits modify ingredients, steps, or title (debounced, not every keystroke)
- FR3: Users can view the full version history of any recipe they have access to, including timestamps and diffs between versions
- FR4: Users can restore any previous version of a recipe, which creates a new version (never destroys history)
- FR5: Users can annotate recipes with notes that attach to the current version and persist in the version timeline
- FR6: Users can archive recipes they own, removing them from active views while preserving all data, version history, and fork lineage references
- FR7: Users can favorite/star recipes for quick access
- FR8: Users can attach photos to recipes (hero image, step-by-step photos)
- FR9: Users can restore archived recipes back to active status at any time
- FR10: Users can create personal recipe books (private, visible only to owner)
- FR11: Users can create shared recipe books with role-based access (owner, editor, viewer)
- FR12: Users can fork a recipe from any book they have access to into their own personal book, with lineage tracked (source recipe and book recorded)
- FR13: The system preserves fork lineage references even when the source recipe is archived or the user loses access to the source book
- FR14: Users can move or copy recipes between their own books
- FR15: Users can invite other users to shared recipe books with configurable permissions
- FR16: Users can browse and search within a specific recipe book
- FR17: Users can perform bulk operations on recipes (bulk tag, bulk move between books, bulk archive)
- FR18: Users can archive recipe books, removing them from active views while preserving all contained recipes and their data
- FR19: Users can import recipes by providing a URL, with the system extracting structured recipe data automatically
- FR20: Users can import recipes by photographing physical recipes (OCR pipeline extracts structured data)
- FR21: Users can bulk import recipes from a CSV or URL list, with the process running asynchronously and notifying the user only when intervention is needed
- FR22: Users can review and correct low-confidence imports before they are finalized
- FR23: Users can import recipes via the iOS/Android share sheet from any app (TikTok, Safari, Instagram, etc.)
- FR24: The system preserves source attribution for all imported recipes (original URL, photo, or source reference)
- FR25: Users can enter a hands-free cooking mode for any recipe, with large text, step-by-step navigation, and an ingredient reference strip
- FR26: Users can set and manage multiple concurrent timers during cooking, with background notifications on completion
- FR27: Users can navigate between steps using touch gestures suitable for messy hands (swipe, large tap targets)
- FR28: Users can access cooking mode offline with locally cached recipe data
- FR29: Users are prompted with a post-cook feedback flow after completing cooking mode (rate how it went, add notes, log the cook)
- FR30: Users can interact with an AI assistant via text or voice that performs actions through tool calling (not just chat)
- FR31: The AI assistant can search the user's recipe collection and return relevant results
- FR32: The AI assistant can add notes to recipes on the user's behalf ("make a note to try extra sugar")
- FR33: The AI assistant can provide recipe suggestions based on user queries
- FR34: The AI assistant can answer questions about a recipe's ingredients, steps, or history during cooking mode
- FR35: The AI assistant is available hands-free in cooking mode via voice input
- FR36: Users can search their recipe collection by recipe name, ingredient, tag, or free text
- FR37: The system supports exact match, fuzzy match, and semantic search across recipe content
- FR38: Users can filter search results by recipe book, tags, prep time, and other structured fields
- FR39: Users see a home screen with contextual recipe suggestions (recent, favorites, planned meals) without needing to search
- FR40: Archived recipes are excluded from default search and browsing but can be found via an explicit archive view
- FR41: Users can share recipe books with household members where both parties have full citizen access (not owner + guest)
- FR42: Users can see real-time updates when a shared book member adds, edits, or forks recipes
- FR43: Users can manage a shared real-time shopping list with household members, with items syncing in real-time
- FR44: Users can add recipe ingredients to the shared shopping list with one action
- FR45: Users can check off shopping list items, with changes visible to all members in real-time
- FR46: Users can schedule recipes to a shared meal planning calendar
- FR47: Users can view upcoming planned meals and navigate to the recipe from the calendar
- FR48: Users can add all ingredients from a planned meal to the shopping list
- FR49: Users can generate an aggregate shopping list from multiple planned meals across a date range
- FR50: Users can sign in via Google or Apple accounts
- FR51: Users can manage their profile (display name, preferences)
- FR52: Users can accept or decline invitations to shared recipe books
- FR53: Users receive push notifications for async events (import complete, import needs attention, book shared, timer complete)
- FR54: Users can configure notification preferences per category (opt-in/opt-out)
- FR55: Users can export their entire recipe collection at any time (JSON format minimum, PDF/printable as growth feature)
- FR56: The system never alters, removes, or restricts access to a user's recipe data
- FR57: First-time users experience an onboarding flow that introduces recipe import, recipe books, and cooking mode, and prompts them to complete their first action
- FR58: The system handles empty states gracefully with contextual prompts
- FR59: Users can share a recipe or recipe book via a public link accessible to people without a Palateful account
- FR60: Users can share recipe content via native platform sharing (text, email, messaging apps)
- FR61: Users can access all core features (including cooking mode, OCR via file upload, and voice AI) through a web browser with responsive layout

### NonFunctional Requirements

- NFR1: Core user actions (recipe load, book browsing, search results) complete within 2 seconds at P95 under normal load
- NFR2: AI assistant responses begin streaming within 2 seconds of user input at P95
- NFR3: Shopping list updates propagate to all connected household members within 1 second
- NFR4: Cooking mode transitions (step navigation, timer actions) respond within 200ms at P95, including offline
- NFR5: OCR import jobs complete within 60 seconds from image upload to structured recipe output, per recipe image
- NFR6: Bulk import processes at minimum 10 recipes per minute for URL-based imports
- NFR7: All data encrypted in transit (TLS 1.2+) and at rest (AES-256 for database, S3)
- NFR8: Authentication handled via identity provider with token-based sessions; no plaintext credentials stored
- NFR9: Users can only access recipes and books they own or have been explicitly invited to
- NFR10: API endpoints enforce authorization checks on every request — no data leakage between users
- NFR11: AI assistant tool calls execute with the same permission model as direct user actions (no privilege escalation)
- NFR12: Zero recipe data corruption — the system never silently alters, truncates, or loses recipe content
- NFR13: Data recoverable within 4 hours from automated backups in a disaster scenario
- NFR14: Database backups run daily with 30-day retention minimum
- NFR15: Archive operations are soft deletes — no user data is ever physically removed from the database
- NFR16: Version history is append-only — past versions cannot be modified or deleted, only new versions created
- NFR17: System gracefully degrades when external services are unavailable (AI features degrade to offline mode, OCR queues for retry, core recipe CRUD continues working)
- NFR18: System supports up to 50 concurrent users without performance degradation (friends-and-family scale)
- NFR19: Architecture does not preclude scaling to 10,000+ users without fundamental redesign
- NFR20: Individual recipe collections support up to 5,000 recipes per user without search or browsing performance degradation
- NFR21: Shopping list real-time sync supports up to 5 concurrent editors per list
- NFR22: Cooking mode uses minimum 18pt font with high-contrast colors, readable in bright kitchen lighting
- NFR23: All interactive elements in cooking mode have minimum 48x48dp touch targets (messy hands / elbow navigation)
- NFR24: Voice input provides audio or haptic confirmation so users know their command was received without looking at the screen
- NFR25: AI capabilities are provider-agnostic — the system supports swapping between AI providers without changes to user-facing features or data models
- NFR26: Identity provider integration supports adding new sign-in methods without application changes
- NFR27: OCR pipeline supports swapping processing backends without changing the import user experience
- NFR28: Recipe import supports extensible scraper architecture — adding support for new recipe sites requires only a new scraper module, not system changes
- NFR29: Monthly infrastructure costs remain under $50 for personal/friends-and-family usage tier (≤50 users)
- NFR30: AI API costs are monitored and capped per user to prevent runaway spending
- NFR31: OCR batch jobs use spot/on-demand Batch compute sized to minimize idle cost

### Additional Requirements

**From Architecture:**

- Flutter library installation required: Riverpod 3.0, go_router, dio, freezed + json_serializable, amplify_flutter — added to existing pubspec.yaml, not a new project
- Core architecture setup needed: theme upgrade (Playfair Display serif, dark mode, cooking mode theme), go_router routing configuration, dio JWT interceptors, Riverpod provider structure
- Dual API pattern: REST (dio → FastAPI) for all CRUD/search/auth + GraphQL (amplify_flutter → AppSync) for real-time subscriptions only
- AWS AppSync Terraform module needed for real-time features (shopping list sync, live notifications) — infrastructure, not application code
- CI/CD pipeline via GitHub Actions: lint/test on PR, Docker build + ECR push on merge, Terraform apply, Flutter web deploy
- Shared ECR images: parser dev image reusable for prod — environment variable controls config only
- Two environments only: local (Docker Compose) + prod (AWS) — no staging
- Endpoint class pattern mandatory for all new API operations (with nested Params/Response classes)
- Celery task chains for import pipeline, notification dispatch, AI suggestion engine
- Firebase Cloud Messaging integration for push notifications
- Fastlane for mobile builds (iOS TestFlight, Android Play Store)
- Existing brownfield codebase: 82+ API endpoints already exist across 13 resource domains
- Implementation sequence: Flutter libs → core setup → auth flow → feature modules → AppSync → CI/CD → web responsive
- Deprecated docs context: ignore Next.js/Prisma/Vercel patterns from legacy docs (AUTH0.md, SETUP.md, VERCEL.md, api-reference.md)

**From UX Design:**

- Cooking mode always uses dark theme: chocolate (#4A3728) background, warm ivory (#F5ECD7) text, 64dp+ touch targets
- Typography: Playfair Display serif for recipe titles/headings, system sans-serif for body/UI — editorial warmth
- Contextual zero-scroll home screen: conditional hero card (tonight's meal), persistent search bar, 2-column recipe card grid, contextual sections (recent, favorites, books)
- Full light + warm dark mode support across all screens (not just cooking mode)
- Recipe cards are photo-dominant with Playfair titles — primary visual element throughout app
- Edge-to-edge recipe hero photos on detail screens
- Exception-driven bulk import UX: card-based review, one at a time, swipe to resolve
- Spacing scale formalized: 4px base unit (xxs through xxl)
- Shimmer/skeleton loading states (not spinners) for all server data
- Auto-save with invisible versioning — no "save" button anywhere
- Swipe gestures with tap alternatives (swipe to archive + long-press menu)
- Empty states with contextual prompts (empty book → "Add your first recipe")
- Respect system "Reduce Motion" preference
- Responsive breakpoints: single column mobile, 2-col card grid phone, 3-col tablet, max 720px content width web, max 900px cooking mode web
- Bottom navigation: Home, Books, Cart, Calendar, Profile
- WCAG AA compliance verified across all color pairings
- Onboarding flow prompts first action: import recipes, create a recipe, or explore

### FR Coverage Map

- FR1: Epic 2 - Recipe creation with structured fields
- FR2: Epic 4 - Auto-version snapshot on edit
- FR3: Epic 4 - Version history with timestamps and diffs
- FR4: Epic 4 - Restore previous version (creates new version)
- FR5: Epic 4 - Annotate recipes with version-attached notes
- FR6: Epic 2 - Archive recipes (soft delete)
- FR7: Epic 2 - Favorite/star recipes
- FR8: Epic 2 - Attach photos to recipes
- FR9: Epic 2 - Restore archived recipes
- FR10: Epic 2 - Create personal recipe books
- FR11: Epic 7 - Create shared recipe books with RBAC
- FR12: Epic 7 - Fork recipe with lineage tracking
- FR13: Epic 7 - Preserved fork lineage references
- FR14: Epic 2 - Move/copy recipes between books
- FR15: Epic 7 - Invite users to shared books
- FR16: Epic 2 - Browse/search within a recipe book
- FR17: Epic 2 - Bulk operations (tag, move, archive)
- FR18: Epic 2 - Archive recipe books
- FR19: Epic 3 - URL recipe import
- FR20: Epic 3 - OCR photo recipe import
- FR21: Epic 3 - Bulk import from CSV/URL list
- FR22: Epic 3 - Review/correct low-confidence imports
- FR23: Epic 3 - Share sheet import (iOS/Android)
- FR24: Epic 3 - Source attribution for imports
- FR25: Epic 6 - Cooking mode (large text, step nav, ingredient strip)
- FR26: Epic 6 - Multiple concurrent timers with background notifications
- FR27: Epic 6 - Gesture navigation for messy hands
- FR28: Epic 6 - Offline cooking mode
- FR29: Epic 6 - Post-cook feedback flow
- FR30: Epic 11 - AI assistant via text/voice with tool calling
- FR31: Epic 11 - AI search of recipe collection
- FR32: Epic 11 - AI adds notes to recipes
- FR33: Epic 11 - AI recipe suggestions
- FR34: Epic 11 - AI answers during cooking mode
- FR35: Epic 11 - AI hands-free voice in cooking mode
- FR36: Epic 5 - Search by name, ingredient, tag, free text
- FR37: Epic 5 - Exact, fuzzy, and semantic search
- FR38: Epic 5 - Filter by book, tags, prep time, etc.
- FR39: Epic 5 - Contextual home screen (recent, favorites, planned)
- FR40: Epic 5 - Archive view (excluded from default search)
- FR41: Epic 7 - Shared books with full citizen access
- FR42: Epic 7 - Real-time updates on shared book changes
- FR43: Epic 8 - Shared real-time shopping list
- FR44: Epic 8 - Add recipe ingredients to shopping list
- FR45: Epic 8 - Check off items with real-time sync
- FR46: Epic 9 - Schedule recipes to meal calendar
- FR47: Epic 9 - View planned meals, navigate to recipe
- FR48: Epic 9 - Add planned meal ingredients to shopping list
- FR49: Epic 9 - Aggregate shopping list from date range
- FR50: Epic 1 - Sign in via Google/Apple
- FR51: Epic 1 - Manage profile
- FR52: Epic 7 - Accept/decline invitations
- FR53: Epic 3/6/7 - Push notifications (distributed by type: import→E3, timer→E6, partner→E7)
- FR54: Epic 3 - Notification preferences per category (introduced with first notification type)
- FR55: Epic 10 - Export recipe collection (JSON, PDF)
- FR56: Epic 10 - Data sovereignty guarantee
- FR57: Epic 1 - Onboarding flow
- FR58: Epic 1 - Empty states with contextual prompts
- FR59: Epic 10 - Share via public link
- FR60: Epic 10 - Native platform sharing
- FR61: Epic 10 - Web browser access with responsive layout

## Epic List

### Epic 1: Foundation & Authentication
Users can sign in, set up their profile, and experience a polished onboarding that introduces the app and handles empty states gracefully.
**FRs covered:** FR50, FR51, FR57, FR58
**Notes:** Flutter library installation (Riverpod 3.0, go_router, dio, freezed, amplify_flutter), theme setup (Playfair Display, cream/chocolate palette, light + warm dark mode), go_router routing, dio JWT interceptors, Riverpod provider structure, bottom navigation shell (Home, Books, Cart, Calendar, Profile), CI/CD pipeline via GitHub Actions.

### Epic 2: Recipe Management & Organization
Users can create, edit, organize, and browse their personal recipe collection with recipe books, favorites, photos, archiving, and bulk operations.
**FRs covered:** FR1, FR6, FR7, FR8, FR9, FR10, FR14, FR16, FR17, FR18
**Notes:** Recipe CRUD with structured fields, personal recipe books, photo attachments (hero + step photos), archive/restore (soft delete via archived_at), move/copy between books, bulk tag/move/archive. Photo-dominant recipe cards with Playfair titles. Shimmer loading states. Auto-save.

### Epic 3: Recipe Import Pipeline
Users can populate their collection from any source — URLs, photos, CSV bulk import, or share sheet — with exception-driven review and push notification status updates.
**FRs covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR53 (import notifications), FR54
**Notes:** URL extraction (JSON-LD + AI fallback), OCR via HunyuanOCR/AWS Batch, bulk async import with card-based exception review, iOS/Android share sheet, source attribution. Firebase push notifications introduced here (import complete, needs attention). Notification preferences system established for all future notification types.

### Epic 4: Recipe Versioning & Notes
Users can fearlessly edit recipes knowing every meaningful change is auto-preserved, viewable in a version timeline with diffs, restorable with one tap, and annotatable with notes.
**FRs covered:** FR2, FR3, FR4, FR5
**Notes:** Auto-snapshot on meaningful edits (debounced), append-only version history with timestamps and diffs, restore creates new version (never destroys), notes attached to current version. Invisible by default — version history button always visible but never demanded. No "save" button.

### Epic 5: Search & Discovery
Users can find any recipe instantly through exact, fuzzy, and semantic search, and see a contextual zero-scroll home screen that predicts what they need.
**FRs covered:** FR36, FR37, FR38, FR39, FR40
**Notes:** Unified search with exact → fuzzy (pg_trgm) → semantic (pgvector) pipeline. Filters by book, tags, prep time. Contextual home screen: conditional hero card (tonight's meal), persistent search bar, 2-column recipe card grid, contextual sections (recent, favorites, books). Archive view for archived recipes.

### Epic 6: Cooking Mode
Users can cook hands-free from any recipe with large text, step-by-step navigation, concurrent timers, offline support, and post-cook feedback.
**FRs covered:** FR25, FR26, FR27, FR28, FR29, FR53 (timer notifications)
**Notes:** Dark cooking mode theme (chocolate bg, warm ivory text, 64dp+ touch targets, 24px+ step text, 48px+ timer numerals). Swipe/gesture nav for messy hands. Multiple concurrent timers with critical-priority background notifications (break through DND). Offline via locally cached recipes. Post-cook feedback flow. Screen wake lock.

### Epic 7: Household Collaboration
Household members become full citizens with shared recipe books, recipe forking with lineage, invitations, and real-time awareness of each other's activity.
**FRs covered:** FR11, FR12, FR13, FR15, FR41, FR42, FR52, FR53 (partner/book notifications)
**Notes:** Role-based shared books (owner/editor/viewer), fork-to-personal with lineage tracking (preserved even if source archived), invitation system (accept/decline), real-time updates via AppSync when shared book changes. Push notifications for partner actions and book shares (batched, not every action).

### Epic 8: Shopping Lists
Household members can manage a shared real-time shopping list with items syncing instantly, and add recipe ingredients to the cart with one action.
**FRs covered:** FR43, FR44, FR45
**Notes:** AppSync real-time subscriptions for shopping list sync (<1s propagation). Add recipe ingredients to cart with one tap. Check off items visible to all members in real-time. Optimistic updates. Supports up to 5 concurrent editors.

### Epic 9: Meal Planning
Users can schedule recipes to a shared meal calendar, view upcoming meals, and generate aggregate shopping lists from planned meals across a date range.
**FRs covered:** FR46, FR47, FR48, FR49
**Notes:** Calendar view with recipe links. Add planned meal ingredients to shopping list. Aggregate shopping list from date range (e.g., "this week's groceries"). Integration with home screen hero card (tonight's planned meal).

### Epic 10: Sharing, Export & Cross-Platform
Users can share recipes publicly, export their entire collection, and access all features from a web browser with responsive layout.
**FRs covered:** FR55, FR56, FR59, FR60, FR61
**Notes:** JSON export (PDF/printable as growth feature). Public links accessible without account. Native platform sharing (text, email, messaging). Flutter Web with responsive breakpoints (single column mobile, 2-col phone, 3-col tablet, max 720px web content, max 900px cooking mode web). Data sovereignty guarantee. Fastlane for App Store/Play Store builds.

### Epic 11: AI Assistant
Users have an AI assistant that takes actions through tool calling — searching recipes, adding notes, answering questions mid-cook — all via text or voice, including hands-free in cooking mode.
**FRs covered:** FR30, FR31, FR32, FR33, FR34, FR35
**Notes:** OpenAI function calling with SSE streaming. Voice input in cooking mode (hands-free). Provider-agnostic architecture (swappable AI providers). Same permission model as direct user actions (no privilege escalation). AI cost monitoring and per-user caps.

---

## Addendum — 2026-04-16 — Dogfood Bug Punch List (BUGS.md NEW section)

Three focused epics derived from the PRD addendum of the same date. Only the NEW section of `BUGS.md` (lines 1–20) is addressed; the OLD section was explicitly skipped per user direction.

### Epic: Bugs — Calendar Meal UX  (`epic-bugs-calendar-ux`)
Make the calendar an action surface: meal tap opens a disclosure sheet, plan-meal offers recipe autocomplete, recurrence UI surfaces existing backend columns.
**FRs covered:** FR62, FR63, FR64, FR65
**Stories:** bugs-cal-1 (meal/day detail sheet), bugs-cal-2 (recipe autocomplete), bugs-cal-3 (recurrence UI)
**Dependencies:** None — Flutter-only, reuses existing endpoints.

### Epic: Bugs — Activity Hub Polish  (`epic-bugs-activity-hub`)
Finish what Epic 13 started: fix persistent-unread bug, surface hidden import fields, consolidate Add Recipe's in-progress list into the Activity Hub.
**FRs covered:** FR69, FR70, FR71
**Stories:** bugs-act-1 (fix unread), bugs-act-2 (surface fields), bugs-act-3 (consolidate imports)
**Dependencies:** None — no new backend fields.

### Epic: Bugs — Home Screen Declutter & Foundations  (`epic-bugs-home-and-foundations`)
Grab-bag of high-leverage, low-effort fixes: remove AI chat from home header, consolidate sort+filter, auto-create default shopping list in onboarding + backfill, ship admin-promote script.
**FRs covered:** FR66, FR67, FR68, FR72
**Stories:** bugs-home-1 (remove chat), bugs-home-2 (consolidate sort+filter), bugs-onb-1 (default shopping list), bugs-adm-1 (admin script)
**Dependencies:** None between stories in this epic; can run in parallel.

---

## Epic 1: Foundation & Authentication

Users can sign in, set up their profile, and experience a polished onboarding that introduces the app and handles empty states gracefully.

### Story 1.1: App Shell with Design System & Navigation

As a user,
I want to launch a beautifully themed app with clear navigation,
So that I can orient myself and access all major sections.

**Acceptance Criteria:**

**Given** the Flutter app is installed with all core libraries (Riverpod 3.0, go_router, dio, freezed, amplify_flutter)
**When** I launch the app
**Then** I see a themed interface using the cream/chocolate palette with Playfair Display serif headings
**And** a bottom navigation bar with Home, Books, Cart, Calendar, and Profile tabs
**And** light and warm dark mode are both functional and toggle with system preference
**And** shimmer/skeleton loading states are used for all async content
**And** the app respects the system "Reduce Motion" preference

### Story 1.2: Sign In with Google & Apple

As a user,
I want to sign in with my Google or Apple account,
So that my data is securely tied to my identity.

**Acceptance Criteria:**

**Given** I am on the sign-in screen
**When** I tap "Sign in with Google" or "Sign in with Apple"
**Then** I am authenticated via Auth0 and redirected to the app
**And** a JWT is stored and attached to all subsequent API requests via dio interceptor
**And** if my token expires, it is automatically refreshed without disrupting my session
**And** all API communication uses TLS 1.2+
**And** no plaintext credentials are stored on the device

### Story 1.3: User Profile Management

As a user,
I want to manage my profile with a display name and preferences,
So that my identity is personalized across the app.

**Acceptance Criteria:**

**Given** I am signed in
**When** I navigate to the Profile tab
**Then** I see my display name, email, and profile settings
**And** I can edit my display name and save changes
**And** changes persist across app restarts
**And** the profile screen uses the standard design system styling

### Story 1.4: Onboarding Flow

As a first-time user,
I want to be introduced to the app's key features and prompted to take a first action,
So that I know what Palateful can do and get started quickly.

**Acceptance Criteria:**

**Given** I have just signed in for the first time
**When** the app detects I have no recipes or activity
**Then** I see an onboarding flow introducing recipe import, recipe books, and cooking mode
**And** I am prompted to choose a first action: import recipes, create a recipe, or explore
**And** the onboarding can be skipped and does not appear on subsequent launches
**And** the flow uses Playfair Display headings and warm editorial imagery

### Story 1.5: Empty States with Contextual Prompts

As a user,
I want to see helpful guidance when sections are empty,
So that I know what to do next instead of staring at a blank screen.

**Acceptance Criteria:**

**Given** I have no recipes, books, shopping items, or planned meals
**When** I navigate to any empty section
**Then** I see a contextual prompt (e.g., empty book → "Add your first recipe", empty cart → "Plan a meal to get started")
**And** the prompt includes an actionable button that takes me to the relevant creation flow
**And** the empty state disappears once content is added
**And** empty states use warm, encouraging tone consistent with the design system

### Story 1.6: CI/CD Pipeline Setup

As a developer,
I want automated quality gates on every pull request and automated deployments on merge,
So that code quality is enforced and deployments are reliable.

**Acceptance Criteria:**

**Given** a pull request is opened against the main branch
**When** CI runs
**Then** lint and test checks execute for all affected services
**And** the PR cannot merge without passing checks
**Given** code is merged to main
**When** the CI pipeline runs
**Then** Docker images are built and pushed to ECR
**And** Terraform apply runs for infrastructure changes

---

## Epic 2: Recipe Management & Organization

Users can create, edit, organize, and browse their personal recipe collection with recipe books, favorites, photos, archiving, and bulk operations.

### Story 2.1: Recipe CRUD with Structured Fields

As a user,
I want to create and edit recipes with structured ingredients, steps, and metadata,
So that my recipes are organized and consistently formatted.

**Acceptance Criteria:**

**Given** I am signed in
**When** I tap "+" to create a new recipe
**Then** I can enter title, description, ingredients (with quantity/unit), ordered steps, prep time, cook time, servings, source attribution, and tags
**And** the recipe is saved with auto-save (no save button)
**And** I can edit any field on an existing recipe I own
**And** the recipe detail screen displays all structured fields clearly
**And** ingredients and steps maintain their ordering

### Story 2.2: Personal Recipe Books

As a user,
I want to create personal recipe books and browse recipes within them,
So that I can organize my collection by category, cuisine, or purpose.

**Acceptance Criteria:**

**Given** I am signed in
**When** I navigate to the Books tab
**Then** I see my personal recipe books
**And** I can create a new personal book with a name
**And** I can browse recipes within a specific book with photo-dominant recipe cards
**And** personal books are visible only to me
**And** new recipes can be assigned to a book during creation

### Story 2.3: Recipe Photos

As a user,
I want to attach a hero image and step-by-step photos to my recipes,
So that my collection feels visual and personal.

**Acceptance Criteria:**

**Given** I am viewing or editing a recipe
**When** I add a photo
**Then** I can set a hero image that displays edge-to-edge on the detail screen
**And** I can attach photos to individual steps
**And** photos are uploaded to S3 and cached locally for offline access
**And** recipe cards throughout the app display the hero image prominently

### Story 2.4: Favorites & Quick Access

As a user,
I want to star my favorite recipes,
So that I can quickly find the recipes I use most.

**Acceptance Criteria:**

**Given** I am viewing a recipe or recipe card
**When** I tap the star/favorite icon
**Then** the recipe is marked as a favorite
**And** favorites appear in a dedicated section on the home screen
**And** I can unfavorite a recipe with one tap
**And** favorite status persists across sessions

### Story 2.5: Archive & Restore Recipes

As a user,
I want to archive recipes I no longer actively use and restore them anytime,
So that my active collection stays clean without ever losing a recipe.

**Acceptance Criteria:**

**Given** I own a recipe
**When** I swipe to archive (or use the long-press menu)
**Then** the recipe is removed from active views (home, books, search)
**And** the recipe is soft-deleted via `archived_at` — no data is physically removed
**And** I can access an archive view to see all archived recipes
**And** I can restore any archived recipe back to active status with one tap
**And** all version history and fork lineage references are preserved on archived recipes

### Story 2.6: Move & Copy Recipes Between Books

As a user,
I want to move or copy recipes between my personal books,
So that I can reorganize my collection as it grows.

**Acceptance Criteria:**

**Given** I own a recipe in one of my books
**When** I select "Move to..." or "Copy to..."
**Then** I can choose a destination book from my personal books
**And** moving removes the recipe from the source book and places it in the destination
**And** copying creates a duplicate in the destination while keeping the original
**And** the operation is reflected immediately in both books

### Story 2.7: Bulk Operations

As a user,
I want to perform bulk actions on multiple recipes at once,
So that I can efficiently organize a large collection.

**Acceptance Criteria:**

**Given** I am browsing recipes in a book or search results
**When** I enter multi-select mode (long press or select button)
**Then** I can select multiple recipes
**And** I can bulk add/remove tags on the selected recipes
**And** I can bulk move selected recipes to another book
**And** I can bulk archive selected recipes
**And** a count of selected items is displayed during selection

### Story 2.8: Archive Recipe Books

As a user,
I want to archive entire recipe books I no longer need active,
So that my Books tab stays uncluttered without losing any recipes or data.

**Acceptance Criteria:**

**Given** I own a recipe book
**When** I archive the book
**Then** it is removed from the active Books tab
**And** all contained recipes are preserved (not individually archived)
**And** I can view archived books in an archive section
**And** I can restore an archived book, bringing it and all its recipes back to active status

---

## Epic 3: Recipe Import Pipeline

Users can populate their collection from any source — URLs, photos, CSV bulk import, or share sheet — with exception-driven review and push notification status updates.

### Story 3.1: URL Recipe Import

As a user,
I want to import a recipe by pasting or sharing a URL,
So that I can save recipes I find online without manual data entry.

**Acceptance Criteria:**

**Given** I provide a URL to a recipe page
**When** the system processes the URL
**Then** it extracts structured recipe data (title, ingredients, steps, photo, metadata) using JSON-LD first, falling back to AI extraction
**And** I see a preview card with the extracted data before saving
**And** I can edit any field inline before confirming
**And** the saved recipe preserves source attribution (original URL)
**And** extraction completes within a few seconds for standard recipe sites

### Story 3.2: OCR Photo Import

As a user,
I want to photograph a physical recipe and have it converted to structured data,
So that I can digitize handwritten or printed recipes from cookbooks and cards.

**Acceptance Criteria:**

**Given** I tap the camera import option
**When** I take a photo or select from gallery
**Then** the image is sent to the OCR pipeline (HunyuanOCR via AWS Batch)
**And** structured recipe data is extracted (ingredients, steps, title)
**And** I can review and correct the extracted data before saving
**And** source attribution includes the original photo
**And** OCR completes within 60 seconds per image

### Story 3.3: Bulk Import from CSV/URL List

As a user,
I want to bulk import recipes from a CSV file or list of URLs,
So that I can migrate my entire recipe collection in one session.

**Acceptance Criteria:**

**Given** I upload a CSV file or paste a list of URLs
**When** the bulk import starts
**Then** processing runs asynchronously via Celery task chain
**And** I see a progress indicator ("34 of 103 processed")
**And** I can leave the app and processing continues in the background
**And** the system processes at minimum 10 recipes per minute for URL imports
**And** high-confidence results are auto-accepted without my intervention

### Story 3.4: Exception Review Queue

As a user,
I want to review and correct only the imports that need attention,
So that I don't have to babysit every import — just fix the exceptions.

**Acceptance Criteria:**

**Given** a bulk or individual import produces low-confidence results
**When** I open the exception review queue
**Then** I see flagged items one at a time as cards (swipe to resolve)
**And** dead links show cached title with options to enter manually or skip
**And** low-confidence OCR shows the AI guess side-by-side with the original image
**And** items with no detected structure show the AI's best parse for inline editing
**And** resolved items become finalized recipes in my collection

### Story 3.5: Share Sheet Import

As a user,
I want to share a recipe link from any app (TikTok, Safari, Instagram) directly to Palateful,
So that saving a recipe I discover is a one-tap action.

**Acceptance Criteria:**

**Given** I see a recipe in any app on my phone
**When** I tap Share → Palateful
**Then** Palateful receives the URL and begins extraction
**And** I see a preview card with extracted recipe data
**And** I can save to my default or chosen recipe book with one tap
**And** a toast confirms "Recipe saved to [Book Name]"
**And** the entire flow completes in under 5 seconds for standard recipe sites

### Story 3.6: Push Notifications & Notification Preferences

As a user,
I want to receive push notifications when imports complete or need attention, and control which notifications I receive,
So that I'm informed without being overwhelmed.

**Acceptance Criteria:**

**Given** a background import completes or needs attention
**When** the system sends a notification
**Then** I receive a push notification via Firebase Cloud Messaging (e.g., "Import complete — 3 need attention")
**And** tapping the notification opens the relevant screen (import results or exception queue)
**Given** I navigate to notification settings
**When** I view notification categories
**Then** I can opt in/out per category (import status, timer alerts, partner actions, etc.)
**And** my preferences persist and are respected for all future notifications

---

## Epic 4: Recipe Versioning & Notes

Users can fearlessly edit recipes knowing every meaningful change is auto-preserved, viewable in a version timeline with diffs, restorable with one tap, and annotatable with notes.

### Story 4.1: Auto-Versioning on Recipe Edit

As a user,
I want my recipe edits to automatically create a version snapshot when I change ingredients, steps, or title,
So that I never have to think about saving — it just happens.

**Acceptance Criteria:**

**Given** I edit a recipe I own
**When** I modify ingredients, steps, or title (debounced — not every keystroke)
**Then** the system auto-creates a new version snapshot with the previous state
**And** the version is timestamped and stored as append-only (cannot be modified or deleted)
**And** non-meaningful edits (description tweaks, tag changes) do not trigger new versions
**And** there is no "save" button — changes persist automatically
**And** the user is not interrupted or notified about version creation (invisible by default)

### Story 4.2: Version History & Diffs

As a user,
I want to view the full version history of any recipe with diffs between versions,
So that I can see exactly what changed and when.

**Acceptance Criteria:**

**Given** I am viewing a recipe I have access to
**When** I tap the version history button
**Then** I see a timeline of all versions with timestamps
**And** I can select any two versions to see a diff (what was added, removed, changed)
**And** the diff clearly highlights ingredient and step changes
**And** the version count is visible on the recipe detail screen (e.g., "v3" badge) but unobtrusive

### Story 4.3: Restore Previous Version

As a user,
I want to restore any previous version of a recipe with one tap,
So that I can go back to what worked without losing any history.

**Acceptance Criteria:**

**Given** I am viewing the version history of a recipe I own
**When** I tap "Restore" on a previous version
**Then** a new version is created with the content of the selected version (never destroys history)
**And** the version timeline shows the restore action clearly (e.g., "Restored from v2")
**And** all previous versions remain accessible in the timeline
**And** the recipe detail screen reflects the restored content immediately

### Story 4.4: Recipe Notes

As a user,
I want to annotate my recipes with notes that attach to the current version,
So that I can capture cooking observations and ideas within the recipe's timeline.

**Acceptance Criteria:**

**Given** I am viewing a recipe I have access to
**When** I add a note (via text input on the recipe detail screen)
**Then** the note is attached to the current version and persists in the version timeline
**And** notes are visible on the recipe detail screen below the steps
**And** notes from previous versions are visible in the version history view
**And** I can add multiple notes to the same version
**And** notes include a timestamp

---

## Epic 5: Search & Discovery

Users can find any recipe instantly through exact, fuzzy, and semantic search, and see a contextual zero-scroll home screen that predicts what they need.

### Story 5.1: Recipe Search by Name, Ingredient, Tag & Free Text

As a user,
I want to search my recipe collection by typing anything — a recipe name, an ingredient, a tag, or free text,
So that I can find what I'm looking for without knowing the exact title.

**Acceptance Criteria:**

**Given** I tap the search bar
**When** I type a query
**Then** results appear showing recipes matching by name, ingredient, tag, or free-text content
**And** results display as photo-dominant recipe cards consistent with the design system
**And** results return within 2 seconds at P95
**And** an empty search shows a helpful prompt, not a blank screen
**And** search works across all recipes I have access to (personal + shared books)

### Story 5.2: Fuzzy & Semantic Search

As a user,
I want search to be forgiving of typos and understand what I mean even when I don't use exact words,
So that I always find what I'm looking for.

**Acceptance Criteria:**

**Given** I enter a search query
**When** exact matches exist
**Then** they appear first in results
**And** fuzzy matches (typos, partial words) via pg_trgm appear next
**And** semantic matches (conceptually similar) via pgvector appear after
**And** the search pipeline runs exact → fuzzy → semantic in sequence, combining results
**And** searching "chicken pasta" finds recipes titled "Creamy Garlic Chicken Penne"
**And** searching "chiken" (typo) still returns chicken recipes

### Story 5.3: Search Filters

As a user,
I want to filter search results by recipe book, tags, prep time, and other fields,
So that I can narrow down results when I know what kind of recipe I want.

**Acceptance Criteria:**

**Given** I have search results displayed
**When** I apply filters
**Then** I can filter by recipe book (show only recipes from a specific book)
**And** I can filter by tags
**And** I can filter by prep time range
**And** I can filter by cook time range
**And** filters combine (AND logic) and update results immediately
**And** active filters are visible and individually removable

### Story 5.4: Contextual Zero-Scroll Home Screen

As a user,
I want the home screen to show me the right recipe before I search — based on what's planned, what I've cooked recently, and what I love,
So that most sessions start and end without needing to search at all.

**Acceptance Criteria:**

**Given** I open the app
**When** the home screen loads
**Then** I see a conditional hero card at the top if a meal is planned for today (large photo, Playfair title, "Start Cooking" CTA)
**And** a persistent search bar is always visible (below hero or at top when no hero)
**And** a 2-column recipe card grid shows my collection
**And** contextual sections appear: Recently Cooked, Favorites, Your Books
**And** the home screen is usable in 1-2 taps with zero scrolling past irrelevant content
**And** when no meal is planned, the search bar and card grid are the primary experience

### Story 5.5: Archive View

As a user,
I want archived recipes excluded from search and browsing but accessible via a dedicated archive view,
So that my active collection stays clean while nothing is ever truly gone.

**Acceptance Criteria:**

**Given** I have archived recipes
**When** I search or browse my collection
**Then** archived recipes do not appear in results
**And** I can access an explicit archive view (e.g., from Profile or Settings)
**And** the archive view shows all archived recipes with the same card layout
**And** I can restore any archived recipe from the archive view
**And** I can search within the archive view

---

## Epic 6: Cooking Mode

Users can cook hands-free from any recipe with large text, step-by-step navigation, concurrent timers, offline support, and post-cook feedback.

### Story 6.1: Cooking Mode Core Experience

As a user,
I want to enter a hands-free cooking mode with large text, one step per screen, and an ingredient reference strip,
So that I can follow a recipe without squinting or scrolling while cooking.

**Acceptance Criteria:**

**Given** I am viewing any recipe
**When** I tap "Start Cooking"
**Then** cooking mode activates with the dark theme (chocolate #4A3728 background, warm ivory #F5ECD7 text)
**And** one step is displayed per screen with 24px+ step text and 32px step number
**And** a floating ingredient strip is accessible for quick reference
**And** the screen wake lock is enabled (screen stays on)
**And** step transitions respond within 200ms
**And** minimal chrome — step content fills the entire screen

### Story 6.2: Gesture Navigation for Messy Hands

As a user,
I want to navigate between cooking steps using swipe gestures and large tap targets,
So that I can interact with the app when my hands are messy.

**Acceptance Criteria:**

**Given** I am in cooking mode
**When** I swipe left/right
**Then** I navigate to the next/previous step
**And** all interactive elements have minimum 64dp touch targets
**And** a progress indicator shows which step I'm on (e.g., "Step 3 of 8")
**And** I can tap large forward/back areas as an alternative to swiping
**And** gestures provide haptic feedback on step transitions

### Story 6.3: Concurrent Timers with Background Notifications

As a user,
I want to set and manage multiple concurrent timers during cooking that alert me even when the app is backgrounded,
So that I never miss a timing step.

**Acceptance Criteria:**

**Given** I am in cooking mode and a step mentions a timed action
**When** I start a timer
**Then** the timer displays with 48px+ numerals and counts down
**And** I can run multiple timers simultaneously
**And** timers continue running when the app is backgrounded
**And** timer completion triggers a critical-priority push notification via Firebase (breaks through DND)
**And** tapping the notification returns me to cooking mode
**And** I can cancel or restart any active timer

### Story 6.4: Offline Cooking Mode

As a user,
I want cooking mode to work fully offline with cached recipe data,
So that I can cook reliably even with poor kitchen Wi-Fi.

**Acceptance Criteria:**

**Given** I have previously viewed a recipe while online
**When** I enter cooking mode without network connectivity
**Then** all recipe data (ingredients, steps, photos) loads from local cache
**And** step navigation, timers, and the ingredient strip all function offline
**And** a subtle offline indicator appears (not alarming)
**And** any notes or changes made offline are queued and sync when connectivity returns

### Story 6.5: Post-Cook Feedback Flow

As a user,
I want to be prompted for quick feedback after finishing cooking mode,
So that I can capture how it went and add notes while the experience is fresh.

**Acceptance Criteria:**

**Given** I reach the last step and tap "Done cooking"
**When** cooking mode ends
**Then** I see a brief feedback flow: rate how it went (simple rating), add optional notes
**And** the cook is logged (date, recipe, rating)
**And** notes from the feedback flow are attached to the recipe (per Epic 4 versioning)
**And** I can skip the feedback flow entirely
**And** the flow transitions back to the recipe detail screen

---

## Epic 7: Household Collaboration

Household members become full citizens with shared recipe books, recipe forking with lineage, invitations, and real-time awareness of each other's activity.

### Story 7.1: Shared Recipe Books with Role-Based Access

As a user,
I want to create shared recipe books and control who can view, edit, or manage them,
So that my partner and I can collaborate on recipe collections with clear permissions.

**Acceptance Criteria:**

**Given** I am signed in
**When** I create a new recipe book and set it as "shared"
**Then** I am the owner with full control
**And** the book is distinguishable from personal books in the UI (visual indicator)
**And** owner can add/edit/delete recipes and manage members
**And** editors can add/edit recipes but not manage members or delete the book
**And** viewers can browse and cook from recipes but not modify them
**And** authorization is enforced on every API request — no data leakage between users

### Story 7.2: Invitation System

As a user,
I want to invite others to my shared recipe books and manage pending invitations,
So that I can build my household's shared collection.

**Acceptance Criteria:**

**Given** I own a shared recipe book
**When** I invite another user by email or invite link
**Then** the invitee receives the invitation (in-app and optionally via push notification)
**And** the invitee can accept or decline the invitation
**And** on acceptance, they gain the assigned role (editor or viewer)
**And** I can see pending invitations and revoke them
**And** invite links can be shared externally and claimed on signup
**And** I can change a member's role or remove them from the book

### Story 7.3: Recipe Forking with Lineage

As a user,
I want to fork a recipe from any book I have access to into my personal book,
So that I can create my own version while preserving where it came from.

**Acceptance Criteria:**

**Given** I am viewing a recipe in a shared book (or any book I have access to)
**When** I tap "Make My Copy" (fork)
**Then** a copy is created in my personal book as version 1
**And** the fork displays a lineage badge: "Forked from: [Recipe Name] ([Book Name])"
**And** my edits create new versions (v2+) on the fork — the original is untouched
**And** lineage references are preserved even if the source recipe is archived
**And** lineage references are preserved even if I lose access to the source book

### Story 7.4: Real-Time Shared Book Updates

As a user,
I want to see real-time updates when my partner adds, edits, or forks recipes in our shared books,
So that our shared collection feels alive and collaborative.

**Acceptance Criteria:**

**Given** I am viewing a shared recipe book
**When** another member adds, edits, or forks a recipe
**Then** the change appears in my view without manual refresh
**And** real-time updates are delivered via AWS AppSync GraphQL subscriptions
**And** updates work while the app is in the foreground
**And** the AppSync Terraform module is deployed and integrated with Auth0 JWT

### Story 7.5: Partner Activity Notifications

As a user,
I want to receive push notifications when my partner shares a book with me or makes notable changes,
So that I stay aware of household cooking activity without constant checking.

**Acceptance Criteria:**

**Given** my partner performs a notable action (shares a book, adds a recipe to a shared book)
**When** the notification is dispatched
**Then** I receive a push notification via Firebase
**And** partner actions are batched (not every single edit triggers a notification)
**And** tapping the notification navigates to the relevant book or recipe
**And** notification preferences (established in Epic 3) include a "partner activity" category I can toggle

---

## Epic 8: Shopping Lists

Household members can manage a shared real-time shopping list with items syncing instantly, and add recipe ingredients to the cart with one action.

### Story 8.1: Shared Real-Time Shopping List

As a user,
I want to manage a shared shopping list with my household where items sync in real-time,
So that we always see the same list without texting "did you get the lemons?"

**Acceptance Criteria:**

**Given** I am signed in and have a household connection (via shared books from Epic 7)
**When** I navigate to the Cart tab
**Then** I see a shared shopping list with all items
**And** items I add appear on my partner's list within 1 second
**And** real-time sync is powered by AppSync subscriptions (reusing infrastructure from Epic 7)
**And** the list supports up to 5 concurrent editors without conflicts
**And** items display with checkboxes and are grouped logically
**And** I can manually add items by typing (not just from recipes)

### Story 8.2: Add Recipe Ingredients to Shopping List

As a user,
I want to add all ingredients from a recipe to the shopping list with one tap,
So that I can go from "let's make this" to "ingredients on the list" instantly.

**Acceptance Criteria:**

**Given** I am viewing a recipe
**When** I tap "Add to Cart" (or similar)
**Then** all ingredients from the recipe are added to the shared shopping list
**And** duplicate ingredients are handled intelligently (don't add "2 eggs" if eggs are already on the list — combine or flag)
**And** items are attributed to the source recipe for context
**And** a toast confirms the action with the count of items added
**And** my partner sees the new items appear in real-time

### Story 8.3: Check Off Items with Real-Time Sync

As a user,
I want to check off shopping list items at the store and have my partner see the updates live,
So that we don't double-buy when shopping separately.

**Acceptance Criteria:**

**Given** I am at the store viewing the shared shopping list
**When** I check off an item
**Then** the item shows as checked on my partner's device within 1 second
**And** checked items move to a "completed" section (not removed immediately)
**And** I can uncheck an item if I made a mistake
**And** I can clear all completed items when the shopping trip is done
**And** optimistic updates ensure the UI responds instantly even before server confirmation

---

## Epic 9: Meal Planning

Users can schedule recipes to a shared meal calendar, view upcoming meals, and generate aggregate shopping lists from planned meals across a date range.

### Story 9.1: Schedule Recipes to Meal Calendar

As a user,
I want to schedule recipes to specific dates on a shared meal calendar,
So that my household knows what we're cooking this week.

**Acceptance Criteria:**

**Given** I am viewing a recipe or browsing my collection
**When** I tap "Plan for..." or drag a recipe onto the calendar
**Then** I can pick a date and optional meal slot (breakfast, lunch, dinner, snack)
**And** the recipe appears on the shared calendar for that date
**And** my partner can see planned meals on their calendar
**And** I can remove or reschedule a planned meal
**And** the Calendar tab shows a week/month view with recipe thumbnails on planned dates

### Story 9.2: Browse Planned Meals & Navigate to Recipe

As a user,
I want to view upcoming planned meals and jump straight to the recipe,
So that I can quickly see what's coming up and start cooking.

**Acceptance Criteria:**

**Given** I navigate to the Calendar tab
**When** I view upcoming days
**Then** I see planned meals with recipe photo, title, and prep time
**And** tapping a planned meal navigates directly to the recipe detail screen
**And** today's planned meal feeds into the home screen hero card (from Epic 5)
**And** past meals remain visible on the calendar as a cooking log
**And** days with no planned meals show an empty state with a prompt to plan

### Story 9.3: Add Planned Meal Ingredients to Shopping List

As a user,
I want to add ingredients from a planned meal to the shopping list,
So that planning and shopping are connected without manual effort.

**Acceptance Criteria:**

**Given** I have a meal planned on the calendar
**When** I tap "Add ingredients to cart" on the planned meal
**Then** all ingredients from that recipe are added to the shared shopping list
**And** the behavior matches Epic 8 Story 8.2 (duplicate handling, source attribution, real-time sync)
**And** a toast confirms items were added

### Story 9.4: Aggregate Shopping List from Date Range

As a user,
I want to generate a combined shopping list from all planned meals across a date range,
So that I can do one grocery run for the whole week.

**Acceptance Criteria:**

**Given** I have multiple meals planned across several days
**When** I select a date range (e.g., "This Week") and tap "Generate Shopping List"
**Then** ingredients from all planned meals in that range are aggregated into the shopping list
**And** duplicate ingredients across recipes are combined (e.g., two recipes needing eggs → total egg count)
**And** items are attributed to their source recipes for context
**And** the aggregated list syncs to my partner in real-time via the shared shopping list

---

## Epic 10: Sharing, Export & Cross-Platform

Users can share recipes publicly, export their entire collection, and access all features from a web browser with responsive layout.

### Story 10.1: Export Recipe Collection

As a user,
I want to export my entire recipe collection at any time,
So that I always own my data and can take it with me.

**Acceptance Criteria:**

**Given** I navigate to Profile → Export
**When** I tap "Export Collection"
**Then** my full recipe collection is exported as JSON (all recipes, ingredients, steps, notes, version history, book assignments)
**And** the export downloads as a file to my device
**And** the export includes all data — nothing is omitted or altered
**And** the system never restricts access to this feature (data sovereignty guarantee)
**And** PDF/printable export is noted as a future enhancement but not required for this story

### Story 10.2: Share Recipe via Public Link

As a user,
I want to share a recipe or recipe book via a public link that anyone can view without an account,
So that I can share my recipes with friends and family who don't use Palateful.

**Acceptance Criteria:**

**Given** I am viewing a recipe or recipe book I own
**When** I tap "Share Link"
**Then** a public URL is generated that displays the recipe/book in a read-only view
**And** the link is accessible without a Palateful account
**And** the public view shows the recipe with full formatting (photo, ingredients, steps)
**And** viewers without an account can see the recipe but cannot edit, fork, or interact
**And** I can revoke a public link at any time

### Story 10.3: Native Platform Sharing

As a user,
I want to share a recipe via text, email, or messaging apps using the native share sheet,
So that I can send recipes however my friends prefer to communicate.

**Acceptance Criteria:**

**Given** I am viewing a recipe
**When** I tap the share icon
**Then** the native platform share sheet opens
**And** the shared content includes recipe title, a brief summary (ingredients + steps), and optionally the public link
**And** sharing works via text, email, WhatsApp, iMessage, and any installed messaging app
**And** the shared format is clean and readable (not raw JSON or a wall of text)

### Story 10.4: Flutter Web with Responsive Layout

As a user,
I want to access all core features — including cooking mode, OCR via file upload, and voice AI — through a web browser,
So that I can use Palateful from my laptop on the kitchen counter or desktop at the couch.

**Acceptance Criteria:**

**Given** I navigate to the Palateful web app in a modern browser (Chrome, Safari, Firefox — last 2 versions)
**When** the app loads
**Then** all core features work: recipe browsing, creation, import (file upload for OCR), cooking mode, shopping list, calendar, search
**And** layout is responsive: single column mobile, 2-column card grid on phone widths, 3-column on tablet, max 720px content width on desktop, max 900px for cooking mode
**And** cooking mode works on web with large type and voice AI (browser microphone API)
**And** OCR import supports file upload (drag-and-drop or file picker) and webcam as secondary option
**And** authentication works on web (Auth0 web flow)

### Story 10.5: Mobile App Store Builds

As a developer,
I want automated mobile build pipelines for iOS and Android,
So that the app can be published to TestFlight and Play Store reliably.

**Acceptance Criteria:**

**Given** a release is ready
**When** the build pipeline runs via Fastlane
**Then** an iOS build is generated and uploaded to TestFlight
**And** an Android build is generated and uploaded to Play Store (internal testing)
**And** build signing is configured for both platforms
**And** the pipeline can be triggered manually or on tagged releases

---

## Epic 11: AI Assistant

Users have an AI assistant that takes actions through tool calling — searching recipes, adding notes, answering questions mid-cook — all via text or voice, including hands-free in cooking mode.

### Story 11.1: AI Chat with Tool Calling

As a user,
I want to interact with an AI assistant via text that performs real actions through tool calling,
So that I can manage my recipes conversationally instead of navigating menus.

**Acceptance Criteria:**

**Given** I open the AI assistant (via chat screen or contextual entry point)
**When** I type a message
**Then** the AI responds via SSE streaming (response begins within 2 seconds)
**And** the AI can execute tool calls — not just chat, but take actions on my behalf
**And** tool calls execute with my permission model (no privilege escalation — the AI can only access what I can access)
**And** the AI architecture is provider-agnostic (swappable between OpenAI, Claude, etc. without user-facing changes)
**And** AI API costs are tracked per user with configurable caps

### Story 11.2: AI Recipe Search

As a user,
I want to ask the AI to find recipes in my collection using natural language,
So that I can search conversationally ("what's that chicken dish I made last month?").

**Acceptance Criteria:**

**Given** I am chatting with the AI assistant
**When** I ask about recipes in my collection (e.g., "find pasta recipes", "what did I cook last week?")
**Then** the AI searches my recipe collection via tool call and returns relevant results
**And** results include recipe names, books, and key details
**And** I can tap a result to navigate to the recipe
**And** the AI leverages the same search infrastructure (exact/fuzzy/semantic) from Epic 5

### Story 11.3: AI Adds Notes to Recipes

As a user,
I want to tell the AI to add a note to a recipe on my behalf,
So that I can capture ideas without navigating to the recipe and typing manually.

**Acceptance Criteria:**

**Given** I am chatting with the AI assistant
**When** I say "add a note to [recipe] — try adding more garlic next time"
**Then** the AI identifies the correct recipe and attaches the note via tool call
**And** the note is attached to the current version (per Epic 4 versioning)
**And** the AI confirms the action: "Added note to [Recipe Name]"
**And** the note is visible on the recipe detail screen and in version history

### Story 11.4: AI Recipe Suggestions

As a user,
I want to ask the AI for recipe suggestions based on what I have or what I'm in the mood for,
So that I get personalized ideas from my own collection.

**Acceptance Criteria:**

**Given** I am chatting with the AI assistant
**When** I ask for suggestions (e.g., "what should I cook tonight?", "something quick with chicken")
**Then** the AI searches my collection and suggests relevant recipes with reasoning
**And** suggestions are drawn from MY recipes (not generated from scratch)
**And** the AI considers context if available (recent cooks, favorites, planned meals)
**And** I can tap a suggestion to view the full recipe

### Story 11.5: AI in Cooking Mode — Questions & Answers

As a user,
I want to ask the AI questions about my recipe's ingredients, steps, or history while I'm cooking,
So that I get instant answers without leaving cooking mode.

**Acceptance Criteria:**

**Given** I am in cooking mode
**When** I ask the AI a question (e.g., "can I substitute butter for oil?", "what was step 3?", "how did I make this last time?")
**Then** the AI answers using the current recipe's data as context
**And** the AI can reference specific ingredients, steps, and version history
**And** the response appears within cooking mode (overlay or inline) without disrupting step navigation
**And** the interaction does not exit cooking mode

### Story 11.6: Hands-Free Voice Input in Cooking Mode

As a user,
I want to interact with the AI via voice while cooking,
So that I can ask questions and add notes without touching my phone.

**Acceptance Criteria:**

**Given** I am in cooking mode
**When** I activate voice input (tap microphone or wake word)
**Then** my speech is transcribed and sent to the AI as a text query
**And** the AI can perform all actions available via text (search, notes, questions, suggestions)
**And** voice input provides audio or haptic confirmation that the command was received
**And** the AI's response is displayed on screen (and optionally read aloud)
**And** the entire interaction works hands-free — I don't need to touch the screen to complete the flow
