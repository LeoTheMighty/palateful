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


---

## Addendum — 2026-04-17 — Recurring Meal Plans (slot-based)

Two epics, sequential. Epic 2 depends on Epic 1 (rules table + materialization land first; edit-scope and manage screen follow).

- **epic-recurring-meals-foundation** — user sees: tap "Repeats: Never" in the plan-meal sheet, pick one-or-more weekdays, pick weekly-or-biweekly, tap Add — every Monday & Wednesday dinner now shows the chosen recipe for 9 weeks, each tile marked with a subtle repeat glyph. From a recurring occurrence the user can End Series Today. Touches: **frontend + backend + infra** (new migration, nightly worker job).
- **epic-recurring-meals-editing** — user sees: tapping Reschedule / swap recipe / unschedule on a recurring occurrence surfaces a "This one / This and following / All" prompt; a new "Recurring plans" section under Profile lists every rule with next-occurrence dates and one-tap series management; monthly-nth-weekday ("first Saturday dinner") grammar is available. Touches: **frontend + backend** (no new infra).

---

## Addendum — 2026-04-17 — Import Bug Punch List (BUGS.md NEW lines 5–7)

Two epics, parallelizable. The structured-ingredients epic is Flutter-heavy with no backend changes; the photo-pipeline epic is backend-heavy with a thin Flutter audit. Locked decisions (from 2026-04-17 user batch): Bug 1 lands the new editor in both Review Import and the recipe wizard; Bug 2 auto-promotes the photo-import source as the recipe hero (no Snap Picture, no per-ingredient crops); Bug 3 auto-detects multiple recipes per photo via extractor prompt + server-side fan-out (no manual split UI in v1).

- **epic-bugs-import-structured-ingredients** — user sees: every ingredient row in both Review Import and the recipe wizard becomes a structured row with quantity, unit (dropdown of common units with free-text fallback), name, notes, and an optional toggle. Saved structured fields persist on the recipe and survive cooking-mode display. Replaces today's single-text-field gap that hid quantity/unit/notes after extractor commit `4f0de4c`. Touches: **frontend** (heavy), **backend** (none — endpoints already accept structured shape), **infra** (none).
- **epic-bugs-import-photo-pipeline** — user sees: (a) when they import a photo of a recipe, the recipe ends up with that photo as its hero image (instead of no image at all); (b) when one photo contains two recipes (cookbook facing pages, side-by-side cards), the import queue surfaces two cards to review instead of mashing them into one mangled item. Touches: **frontend** (small audit only — Review Import already handles N cards), **backend** (heavy — extractor prompt rewrite, parser_batch_completion fan-out, S3 promotion in create_recipe_task, eval fixtures), **infra** (small — new permanent recipe-images S3 prefix + IAM grant for worker).

---

## Addendum — 2026-04-17 — Calendar Management & Sharing (multiple switchable calendars, full co-edit)

Two epics, sequential. Epic 2 depends on Epic 1 (calendars table + backfill + switcher land first; sharing/invite flow builds on top). Locked decisions (from 2026-04-17 user batch): owner+editor roles only (no viewer), switcher UX (not overlay), "My Calendar" default auto-created + backfilled for every user, shopping-list auto-populate unions across all accessible calendars.

- **epic-calendars-foundation** — user sees: on first app open after deploy, the Calendar tab header reads "My Calendar ▾" with every existing meal intact. Tapping the chevron opens a switcher; tapping **New Calendar** adds "Meal Prep" and Leo's switcher now shows both. Switching to Meal Prep shows an empty grid, scheduling a meal there puts it on Meal Prep only. He can rename or delete a calendar from settings, and move an existing meal between calendars via the meal detail sheet. Touches: **frontend + backend + infra** (new migration + backfill, no new AWS resources).
- **epic-calendars-sharing** — user sees: from Calendar Settings on the Meal Prep calendar, Leo taps **Share** and invites his fiancee by email (or copies an invite link). She gets a push, accepts, and "Meal Prep" now appears in her switcher under "Shared with Me". She schedules Tuesday's dinner; Leo sees it on his device. From the members screen he can promote her to owner or remove her. Editors can leave at any time. Touches: **frontend + backend** (invitation-system extension, no new infra).

---

## Addendum — 2026-04-17 — Home/Notification Bug Punch List (BUGS.md lines 2–5)

Two epics, parallelizable. The home-polish epic is a Flutter-only cleanup pair; the notifications epic is a cross-layer proof-of-life. Locked decisions (from 2026-04-17 user batch): (1) straight delete of the home header's add-image icon (no replacement); (2) iOS-first notifications with an admin-only test-push button as the proof-of-life trigger — real event firehose is explicitly follow-up; onboarding adds a permission-prompt step; local dev runs `PushNotificationService` in log-only mode with no Firebase creds required; (3) post-add-recipe nav fix is scoped to the share-sheet's `context.go('/')` calls and the review-list hub's terminal actions — text/PDF/spreadsheet/audio still route through the review hub, only the terminal pop changes.

- **epic-bugs-home-polish** — user sees: the home header no longer has the camera/image shortcut icon (only Recipe Books, search, Pantry, and the sort/filter funnel remain). When they finish a share-sheet import or approve items from a review-list import hub, they land back on the screen they launched from — the book they were browsing, or wherever the share-sheet interrupted — instead of being bounced to home. Photo import and recipe-book-detail flows are unchanged, they were the exemplar. Touches: **frontend** only (no backend, no infra).
- **epic-notifications-ios-proofoflife** — user sees: during first-time onboarding, one new screen asks "turn on notifications?" with honest copy about what events will fire. Later, from the admin dashboard, Leo taps "Send test push to myself" and a real push lands on his iPhone within seconds. The round-trip is proven end-to-end — iOS registers with APNs, Firebase delivers, the backend logs every send attempt (success or failure) — and local dev runs the backend without any Firebase credentials in log-only mode. Real event triggers (import-complete, partner activity) stay off, turned on in a follow-up story once the plumbing is proven. Touches: **frontend** (iOS native + onboarding) **+ backend** (log-only mode, send-failure logging, admin test-push endpoint, onboarding state field) **+ infra** (`.env.example` + `docs/PUSH_NOTIFICATIONS.md`; no new AWS).


---

## Addendum — 2026-04-18 — Operator Observability: Latency Metrics & User Feedback Inbox

Two epics, parallelizable. Locked decisions (from 2026-04-18 user batch): (1) **latency storage in Postgres** with a new `BatchedLatencyWriter` primitive — no Datadog, no Prometheus, no CloudWatch EMF; (2) **dedicated `/admin/metrics` page** with percentile tables + sparklines (not just dashboard cards); (3) **push + unread-badge** for new-feedback admin alerts (email-via-SES deferred); (4) **read-only feedback inbox** with Mark Read / Archive — no reply UI; (5) **prod fetch script mirrors `promote_admin.py`**.

- **epic-observability-latency** — user sees: admin taps a new "Metrics" card on the admin dashboard → lands on `/admin/metrics`, a page with two sections (Endpoints, Tasks), each a sortable table of p50 / p95 / p99 / sample_count / error_rate per `(method, normalized_path)` or `task_name`, a 1h / 24h / 7d window selector, and a 24-bucket sparkline per row. The dashboard itself gains an "Overall p95 (24h)" number and a "Slowest endpoint" strip linking to the full page. Under the hood a new `BatchedLatencyWriter` primitive captures samples from FastAPI middleware and Celery signal handlers into two append-only tables; a nightly beat task prunes >30d. Touches: **backend** (migration for `request_latencies` + `task_latencies`, writer + middleware + Celery hooks, 2 aggregation endpoints, admin stats extension, nightly prune task) **+ frontend** (`AdminMetricsScreen`, dashboard card, sparkline widget) **+ infra** (None — pure Postgres tables via existing migrator; no AWS changes).
- **epic-user-feedback** — user sees: opens Profile → Settings → taps "Send Feedback" → a sheet appears with a category dropdown (Bug / Idea / Praise / Other), a free-text body field with a character count, Send button → snackbar confirms submission (or queues offline for retry). Admin sees: a push notification lands on their phone ("New Palateful feedback from Jane: <preview>") and a badge on the Feedback card in the admin dashboard. Tapping the card opens `AdminFeedbackScreen` — a paginated list filtered by Unread / Read / Archived / All; each item expands to a detail drawer with body + context + Mark Read / Archive actions. Leo separately runs `python services/api/scripts/fetch_feedback.py --since 30d --format csv` on the prod DB for bulk triage / export. Touches: **backend** (migration for `user_feedbacks` + `NotificationType.NEW_FEEDBACK`, user submit endpoint, 2 admin endpoints, Celery fan-out task, admin stats extension, prod fetch script) **+ frontend** (`FeedbackSheet` + Profile entry, `AdminFeedbackScreen` + dashboard badge card) **+ infra** (None — reuses existing RDS + FCM; no new AWS).




---

## Addendum — 2026-04-18 — Activity Hub Redesign & Import Experience Overhaul

Three epics. Epic 2 depends on Epic 1 (rows exist before caret expansion lands on them). Epic 3 is independent and can ship in parallel. Locked decisions (from 2026-04-18 user batch): (1) top-of-screen tabs inside a single `/activity` route — Notifications | Imports — no new bottom-nav tab; (2) collapsed-by-default caret expansion per row as the "information-heavy" rich view Leo wants back; (3) blue (In Progress) is read-only — no swipe; all other import states archive with 3s snackbar-undo; "See all" footer holds archived + older history; (4) confidence score built end-to-end this release (extractor → backend → UI), no coarse placeholder; (5) one-line ingredient row with notes + optional behind a caret; (6) unit normalization end-to-end (extractor prompt enum + backend alias table + client coerce-on-blur) — one source of truth mirrored to Flutter via `GET /v1/units/aliases`.

- **epic-activity-hub-redesign** — user sees: opens `/activity` and lands on a two-tab screen — **Notifications** (invitations, partner activity, meal reminders, chronological) and **Imports** (sectioned by state: **In Progress** blue / **Needs Review** yellow / **Failed** red / **Auto-Imported** green — each section a header chip with count, most-recent first). Swipe left on any Notifications row archives it with 3s undo. Swipe on imports works the same — except blue rows, which have no swipe (cancel stays a detail-screen flow). A **See all** footer on the Imports tab expands to reveal archived imports + anything older than 30 days in muted type. The old `/activity/import-history` route is retired; deep links to it redirect. The `LiveImportStrip` on Add Recipe stays a slim one-liner that deep-links to the new `?tab=imports`. Touches: **frontend** (activity screen rewrite, new tab widget, four color-section renders, semantic import-state color tokens, swipe wiring, "See all" footer) **+ backend** (small — new `POST /v1/user-activities/{id}/archive` endpoint + archive status on the activity model; retirement of `/activity/import-history` is frontend-only since it was a route, not an endpoint) **+ infra** (None — no new AWS, no new migrations beyond the archive column).

- **epic-import-row-rich-detail** — user sees: every import row in the Imports tab (all four states) has a caret toggle. Tapping it expands the row inline to reveal the rich "information-heavy" view — a stage timeline (parsed / extracted / matched / created, each with ✓ / ⏳ / ✗), raw parser text preview (the OCR output Leo loved seeing on the old Add Recipe in-progress list), confidence score (surfaced prominently on yellow Needs Review rows, lower-key on other states), retry history, error detail when failed, source reference (URL / photo thumbnail / text preview). Extraction produces a self-reported confidence score on every import; the backend exposes it and the UI renders it. All three extractors emit the score; malformed LLM output falls back to a heuristic (ingredient-match × step-presence × title-presence) computed server-side. Touches: **frontend** (caret widget on ImportRow, stage-timeline widget, confidence badge with low/med/high glyphs, raw-text preview collapsible, session-scoped expansion memory) **+ backend** (expose `last_successful_stage` + `last_retry_at` on GetImportItem; new `GET /v1/import-items/{id}/telemetry` derived over `error_logs` filtered by `import_item_id`; extractors emit + persist `confidence_score` on `parsed_recipe`; heuristic fallback on malformed LLM output; new index on `error_logs(import_item_id, created_at)`) **+ infra** (None — new migration for `last_retry_at` column + error_logs index, no new AWS).

- **epic-review-import-ingredient-polish** — user sees: opens Review Import on a pending import and every ingredient fits on one tap-target line — `[qty] [unit▾] [name] [caret] [delete]`. Notes and the optional toggle live behind the caret; caret auto-opens for ingredients that have notes or are optional so existing data isn't hidden. A subtle dot on collapsed carets signals "this row has more". Every unit is the canonical abbreviated token — `tbsp` not `tablespoon`, `tsp` not `teaspoon` — because the extractor prompt enumerates the enum and the backend runs every write through an alias table (`tablespoon → tbsp`). The `UnitInput` Flutter widget coerces typed text on blur using a synced alias map fetched from `/v1/units/aliases` so the user typing "tablespoon" sees it auto-snap to "tbsp". An inline badge renders on ingredient rows whose canonical ingredient was auto-created (pending_review) via the Story 13.3 find-or-create path so the user knows a new ingredient entered the catalog. Touches: **frontend** (StructuredIngredientRow rewrite to one line, caret-expanded notes/optional, auto-expand rule, `UnitInput` coerce-on-blur + alias fetch + session cache, `IngredientRowStateBadge`) **+ backend** (new `unit_aliases` table + seed migration; `normalize_unit_display` helper wired into every write path — `extract_recipe_task`, `approve_import_item`, recipe create/update, wizard save — with unit tests per path; `GET /v1/units/aliases` endpoint with 24h Cache-Control; extractor-prompt rewrites to enumerate canonical tokens across AI + vision + text extractors) **+ infra** (None — no new AWS, one migration for `unit_aliases` + seed rows).

## Addendum — 2026-04-18 — Universal Share-to-Palateful

FR23 (share-sheet import) is marked complete in the primary coverage map above, but the end-to-end flow is broken on iOS (no Share Extension target) and narrow on Android (text-only MIME filters). This addendum lands four epics that close FR23 and extend ingest to every source type the backend already understands plus local video files. Detailed epic files live at `_bmad-output/planning-artifacts/epic-share-*.md`. Locked UX decisions from the `/dev-plan` loop are in the PRD addendum of the same date.

### Epic: Share Backend Foundations (`epic-share-backend-foundations`)

Backend and infrastructure plumbing to accept file-based shares: presigned S3 upload endpoint, new `video_file` source_type with ffmpeg audio extraction, social URL routing moved to the endpoint, new imports S3 bucket.
**User sees:** no direct UI; unblocks iOS/Android extensions to actually send and process any file. Attribution for Pinterest/TikTok URLs becomes correct at creation time.
**Touches:** backend, infrastructure.
**FRs covered:** FR-SHR-3, FR-SHR-4 (upload contract), FR-SHR-7 (partial), FR-SHR-8.

### Epic: iOS Share Extension (`epic-share-ios-extension`)

New `PalatefulShare` Xcode target with a minimal SwiftUI confirmation sheet. Extension uploads directly to S3 via presigned URL and calls the import API without depending on the main app. Push notification fires when processing completes. Reuses the existing `group.com.palateful.app` App Group.
**User sees:** taps Share on iOS for a URL / photo / PDF / video → "Save to Palateful" sheet appears → optional recipe book → Save → extension closes → push notification when ready.
**Touches:** frontend (iOS native), infrastructure (App Store Connect provisioning + Xcode Cloud).
**FRs covered:** FR-SHR-1, FR-SHR-4.

### Epic: Android Share Entry Point (`epic-share-android-entrypoint`)

AndroidManifest MIME expansion (`image/*`, `video/*`, `audio/*`, `application/pdf`, spreadsheet types, `*/*` fallback), runtime permissions for Android 13+, and a content-aware rewrite of `_handleSharedFiles` that disambiguates by MIME type + extension + content prefix before routing.
**User sees:** taps Share on Android from Photos / Files / Chrome → Palateful appears as a target → app opens to landing screen → recipe imports.
**Touches:** frontend (Android manifest + Flutter).
**FRs covered:** FR-SHR-2, FR-SHR-6 (routing half), FR-SHR-7 (partial).

### Epic: Universal Receiving UX (`epic-share-receiving-ux`)

New `/recipes/add/receive` landing screen with content-type detection and progress context. All typed import screens (`photo`, `pdf`, `audio`, `spreadsheet`, `video_file`) accept a pre-selected file path and skip their own file pickers. Graceful "we can't process this" fallback screen for unsupported types.
**User sees:** receives any shared content → landing screen says "Importing recipe from TikTok" / "Reading your PDF" / "Transcribing audio" for ≤2s → routes to the existing import activity feed with the job already running.
**Touches:** frontend only (Flutter).
**FRs covered:** FR-SHR-5, FR-SHR-6, FR-SHR-7.

### Dependency order

- **Epic 1 (backend) must land before Epic 2 (iOS extension)** — extension needs the presigned upload endpoint and the `s3_key` import contract.
- **Epic 1 and Epic 3 (Android)** can run in parallel; Android wiring doesn't depend on the extension upload flow.
- **Epic 4 (Flutter UX)** depends on Epic 1 (pre-filled screens need the backend to accept s3_key) and Epic 3 (Android handoff).
- **Recommended sequence:** 1 → 3 → 4 → 2, or 1 + 3 in parallel, then 4, then 2. Total single-engineer effort ≈ 5–7 weeks; 3–4 weeks with one backend + one iOS engineer parallel.

### Retired

`_bmad-output/planning-artifacts/epic-media-import.md` is superseded by this addendum. Story 5 (Add Recipe Sheet redesign) already shipped as Media.5; Stories 1–4 (social URL router, audio fallback, PDF, audio files) are already live in the backend per research conducted during this planning loop. The remaining delta — extension entry points, video file ingest, receiving UX — is what the four epics above cover.

## Addendum — 2026-04-18 — Android Play Store launch + CI hardening

Four new epics ship Palateful onto the Google Play Store (internal track, YOLO path) and make the CI tag→Play flow reliable. Operator has no Android device; validation leans on Play Console's Pre-Launch Report + Firebase Test Lab soft-smoke + a small internal-track tester group.

### Epic: Android Privacy Policy Page (`epic-android-privacy-policy-page`)

Static `app/web/privacy.html` served by the existing Flutter-web Cloudflare Pages deploy. Enumerates Firebase / Auth0 / S3 user-media / LLM subprocessors / Play Billing / GDPR-CCPA-COPPA stance / deletion flow. Unblocks every other Android epic (Play Console Store Listing + Data Safety form both require a public privacy URL).
**User sees:** https://palateful.app/privacy returns a readable page; the URL pastes into Play Console forms without validation errors.
**Touches:** frontend (Flutter web static asset), infrastructure (Cloudflare Pages — no workflow change needed; static files under `app/web/` already deploy).

### Epic: Android Release Hardening (`epic-android-release-hardening`)

App-layer cleanup so the first AAB sails through Play Console review: POST_NOTIFICATIONS + runtime prompt + FCM notification channel, adaptive launcher icon + 512×512 Play Store icon, removal of over-declared READ_MEDIA_* permissions (amends `sae-1`), HTTPS App Links + `.well-known/assetlinks.json`, Crashlytics native-symbol upload config, local release-mode smoke.
**User sees:** Push notifications actually arrive on Android 13+ installs; launcher icon is crisp on Pixel devices; `https://palateful.app/...` links open the app directly.
**Touches:** frontend (Android manifest + Flutter + res/), infrastructure (web: assetlinks.json).

### Epic: Android CI Hardening (`epic-android-ci-hardening`)

`mobile-builds.yml` android-build job is stitched end-to-end: Flutter channel unified with ci.yml (`stable`, pinned version), Gradle cache added, pre-build analyze + test gate, Crashlytics symbol upload step, Firebase Test Lab soft-smoke step, new `promote-android.yml` workflow for manual track promotion (internal → closed → production) gated by the `production` GitHub environment.
**User sees:** no change to app UI; pushing `v1.2.3` reliably drops an AAB on Play Store internal track; promoting to production is a one-click workflow_dispatch later.
**Touches:** infrastructure (CI + Fastlane). No user-visible UI change.

### Epic: Android Play Console Launch (`epic-android-play-console-launch`)

`ANDROID.md` at repo root is the manual runbook for the human-only steps: keystore generation, `base64` → GitHub Secret, Google Play Developer signup as "Palateful" (Personal account, $25), GCP service account for Fastlane, first AAB upload, Data Safety form (paste-ready blocks), Content Rating (IARC Teen 13+), Target Audience (13+), Sensitive Permissions Declaration (SCHEDULE_EXACT_ALARM justification), Google Group for tester recruitment, Play App Signing enrollment. `app/android/play-store-assets/` holds the 512×512 icon, 1024×500 feature graphic, and 2–4 screenshots, version-controlled.
**User sees:** Palateful listed on the Play Store internal track with proper metadata, privacy policy, and content rating; friends/family with Android devices can install via opt-in URL.
**Touches:** documentation (repo-root `ANDROID.md`), assets (store listing graphics), Play Console + Google Cloud Platform + GitHub Secrets (manual).

### Ordering

```
android-privacy-policy-page         ← no blockers, unblocks Play Console
  └─ android-release-hardening      ← app-layer cleanup; App Links can reference live /privacy
       └─ android-ci-hardening      ← CI tests the hardened AAB + adds promotion workflow
            └─ android-play-console-launch  ← docs reference all three; first manual upload happens here
```

Epics 1–3 are `/dev`-runnable code/CI work. Epic 4 is partially code (`ANDROID.md`, store assets) and partially a human runbook (Play Console clicks). The four-epic chain is a single release train — the only things that can ship standalone are `android-privacy-policy-page` (web-only) and small parts of `android-release-hardening`; everything else is gated by the previous epic landing.


---

## Addendum — 2026-04-18 — Push Notifications Diagnostics & Hardening

User report: "Still seeing issues with push notifications. Never been asked for permissions. TestFlight has push enabled, logging out/in and toggling settings does nothing." Trace identified the root causes: (a) onboarding permission step only runs for new accounts — existing accounts past onboarding are permanently locked out of the prompt path; (b) every failure in `push_notification_service.dart` + `AppDelegate.swift` uses `debugPrint`, which is stripped in TestFlight release builds, so failures are silent; (c) boot-time `ensureRegistered()` already aims at the right behavior but has no retry and no observability.

**epic-notifications-push-diagnostics-hardening** — user sees: (a) on next TestFlight launch with `notDetermined` status, OS permission prompt fires automatically; (b) with `denied` status, existing Profile → Notifications warning already shows Open Settings CTA (no change). — touches: frontend (Flutter `push_notification_service.dart`, `notification_preferences_screen.dart`, iOS `AppDelegate.swift`), backend (new admin health endpoint), no infrastructure. Stories: push-diag-1 (ErrorReporter integration across all push failure paths — Flutter + iOS MethodChannel bridge), push-diag-2 (harden loud-on-boot prompt with bounded retry + breadcrumbs + race-safe Firebase init), push-diag-3 (admin per-user push health endpoint + dashboard panel + runbook docs in `docs/PUSH_NOTIFICATIONS.md`). Depends on epic-notifications-ios-proofoflife (done).


---

## Addendum — 2026-04-18 — Meals (Higher-Order Recipe Grouping)

User wants to group 2+ recipes into a single named "meal" (e.g., Lemon Dressing + Kale and Collards Salad). First-class, reusable, schedulable onto the calendar, browseable alongside recipes with a clear visual cue. Four vertical epics — one foundational end-to-end MVP plus three parallelizable follow-ons. Locked decisions (from 2026-04-18 user batch): reusable template model; lives inside a `recipe_book` and inherits sharing via `recipe_book_user`; user-facing name is **"Meal"** with DB table `meals` (existing `meal_events` / `meal_recurrence_rules` unchanged); manual multi-select picker in v1, AI-pairing suggestions deferred. Schema: new `meals` + `meal_recipes` tables, dual nullable FK (`meal_id`) added to `meal_events` + `meal_recurrence_rules` with `num_nonnulls(recipe_id, meal_id) <= 1` check constraint — fully backward-compatible with existing single-recipe scheduling.

### Epic: Meals — Create & View (`epic-meals-create-and-view`)

Foundational end-to-end MVP. Backend: new `meals` + `meal_recipes` tables, full CRUD API under `/v1/meals` and `/v1/recipe-books/{book_id}/meals`, archive/restore, auth via existing `recipe_book_user`. Flutter: "Create Meal from selected" action in the recipe-book detail screen's existing multi-select mode, standalone "New Meal" flow with multi-select picker, Meal detail screen reusing the recipe-detail scroll shell with a component-recipes list + collage hero. Meal tile variant in the book grid with an "N recipes" badge.
**User sees:** "I select Kale Salad + Lemon Dressing in my book, tap Create Meal, name it 'Kale Salad Meal', and open it from my book grid."
**Touches:** frontend, backend. No infrastructure.

### Epic: Meals — Discoverability (`epic-meals-discoverability`)

Home grid, global search, favorites, and archive view all surface Meals alongside recipes with the same "N recipes" badge. Search matches on Meal name/description AND on any component recipe's name (searching "dressing" finds the "Kale Salad Meal"). Recipe detail screen gains a "Used in these Meals" section powered by the reverse-lookup endpoint. Existing `RecipeCard` widget is extended — not forked — to carry an optional `mealComponentCount`.
**User sees:** "My Meals show up in search and on the home screen alongside recipes, clearly marked as Meals. From a recipe, I can see which Meals include it."
**Touches:** frontend, backend (search query extension, new `GET /v1/recipes/{id}/meals`). No infrastructure.
**Depends on:** epic-meals-create-and-view.

### Epic: Meals — Calendar Integration (`epic-meals-calendar`)

Cross-layer. Backend: `meal_events.meal_id` + `meal_recurrence_rules.meal_id` nullable FKs with XOR check, `POST /v1/meal-events` + `/v1/meal-recurrence-rules` accept `meal_id` XOR `recipe_id`, `ListMealEvents` hydrates a `meal_summary` on responses, `PopulateFromCalendarRange` expands a meal_event's Meal into its components with sum-within-meal dedupe for shopping. Flutter: plan-meal-sheet Recipe/Meal segmented toggle, calendar grid + day sheet render meal events with Meals as "MealName (N recipes)" + stack icon, meal detail sheet exposes "Open Meal" deep-link and a component chooser on "Open Recipe", Profile → Recurring Plans screen renders Meal rules.
**User sees:** "I tap Tuesday dinner on the calendar, toggle to Meal, pick my Kale Salad Meal, save. Tuesday shows 'Kale Salad Meal (2 recipes)'. I tap Add to Shopping List and both recipes' ingredients show up with 2 tbsp olive oil combined."
**Touches:** frontend, backend. No infrastructure.
**Depends on:** epic-meals-create-and-view.

### Epic: Meals — Sharing & AI Tools (`epic-meals-sharing-and-ai`)

Parallel small epic. Backend: `meals.share_token` column, `POST /v1/meals/{id}/share` to generate/rotate, `GET /v1/public/meals/{token}` unauthenticated preview (name + description + component names + thumbnails; component ingredients/steps only if the component recipe itself has a share token). Flutter: Meal detail screen "Share" action opens a share sheet with Copy Link + Native Share, public meal page rendered as a read-only detail. MCP tools `create_meal`, `get_meal`, `list_meals`, `update_meal`, `add_recipe_to_meal`, `remove_recipe_from_meal`, `archive_meal`; `create_meal_event` extended to accept `meal_id`. AI chat can assemble a Meal via tool-calling.
**User sees:** "I tap Share on my Kale Salad Meal and get a public link I can text to a friend. I ask the AI 'make a meal with my Lemon Dressing and a kale salad' and it creates the meal."
**Touches:** frontend, backend, MCP tools. No infrastructure.
**Depends on:** epic-meals-create-and-view.

### Ordering

```
meals-create-and-view         ← foundational; blocks the rest
  ├─ meals-discoverability    ← parallelizable after foundation
  ├─ meals-calendar           ← parallelizable after foundation
  └─ meals-sharing-and-ai     ← parallelizable after foundation
```

Epic 1 ships the core noun and its principal verbs. Epics 2, 3, 4 can run in parallel after Epic 1 lands. No infrastructure changes in any of the four — all additive schema + endpoints on the existing stack.


---

## Addendum — 2026-04-18 — Calendar: Per-Meal Shopping Add

Single focused epic. Replaces the calendar's bulk "Add week to shopping list" AppBar button with a visible per-meal `Icons.add_shopping_cart_outlined` on every calendar card that has a linked recipe. Deletes the backend endpoint `POST /v1/shopping-lists/{list_id}/populate-from-calendar` + its impl + its two test sites (dedicated file and coverage-gap class). Reuses the existing `_addIngredientsFromEvent` handler verbatim (default-list resolution + `populateFromRecipe`). Adds a client-only session-persistent "added" check-mark indicator (`Set<String> _addedEventIds` cleared on `_loadEvents`). Driven by a dogfood bug — the bulk path produced 12 garbage items because `ingredients.canonical_name` sometimes holds the raw recipe line; per-meal adds reduce the blast radius to 1 meal's worth per tap and let the user pick which meals to shop for. The canonical-name data fix is tracked separately. Cross-epic: `epic-meals-calendar` loses story `mcal-4` (marked `deleted`); that epic's end-user flow step 7 will use a new per-event endpoint at implementation time (FR-CPMS-7).

### Epic: Calendar — Per-Meal Shopping Add (`epic-calendar-per-meal-shopping-add`)

**User sees:** "Every planned meal in my calendar has a small shopping-cart icon; I tap one, its ingredients land on my default shopping list with a snackbar, and the icon flips to a muted check mark so I know I already added it."
**Touches:** frontend, backend. No infrastructure, no migrations, no new env vars.
**Stories:**
- `cpms-1` — Flutter: remove weekly AppBar button + handler + `populateFromCalendarRange` + `populateShoppingListFromCalendar`; add per-card icon button wired to `_addIngredientsFromEvent` with `_addedEventIds` session-persistent indicator.
- `cpms-2` — Backend: delete `populate_from_calendar.py`, router entry, `__init__.py` export, `test_populate_from_calendar.py`, and `TestPopulateFromCalendarExtended` class in `test_coverage_gaps.py`. Update `docs/SHARED_SHOPPING_CART.md`.

## Addendum — 2026-04-20 — Cook Mode Polish & Timer Autodetection

Two parallelizable epics addressing dogfood regressions in Epic 6 (Cook Mode): (a) colour scheme is jarring because cook mode force-applies `AppTheme.dark()` and uses `colorScheme.primary` (terracotta) as a full-surface background, mixing Material roles with a custom `appColors.*` extension; (b) navigating **back** to a prior step still renders it as completed (line-through + green border) because `_completedSteps` is never cleared; (c) timer autodetection lives in a single client-side regex that misses ranges, decimals, aliases, and multiple matches — meanwhile `recipe_step.timers` (JSONB) has been in the DB since 2026-01-29 but no extractor populates it. User ask: fix colours end-to-end (theme-aware), untoggle completion on back-nav, and build hybrid timer extraction (backend primary + upgraded regex fallback + always-visible manual escape hatch in the header). **Keep as-is:** ingredient toggle strip — the one thing that works.

### Epic: Cook Mode Polish (`epic-cook-mode-polish`)

**User sees:** "Cook mode opens in the same theme as the rest of the app — no jarring orange slab — and if I go back to a prior step because I forgot something, the step no longer shows as crossed-out 'done'. The ingredient toggles still work exactly like before."
**Touches:** frontend. No backend, no infrastructure.
**Stories:**
- `cmp-1` — New `CookModeTheme` ThemeExtension (tokens: `cookSurface`, `cookOnSurface`, `cookAccent`, `cookProgress`, `cookCompleted`, `cookTimer`, …). Registered on `AppTheme.light()` + `.dark()`.
- `cmp-2` — Migrate `cook_mode_screen.dart` to the new tokens; drop the forced-dark `Theme(…)` wrap.
- `cmp-3` — Migrate sub-widgets (`step_navigator.dart`, `ingredient_strip.dart`, `cook_mode_chat_sheet.dart`, `post_cook_feedback_sheet.dart`). Ingredient strip: tokens only, behaviour identical.
- `cmp-4` — `_goToStep(step)` removes `step` from `_completedSteps` when navigating backward; StepNavigator pill never shows a check for `_currentStep`.
- `cmp-5` — Golden tests for both themes; Epic 6 regression sweep.

### Epic: Cook Mode Timers — Extraction + Manual Escape Hatch (`epic-cook-mode-timers`)

**User sees:** "When I cook, the right timer buttons just appear below each step — and if they don't, I can always tap the timer icon in the header to add one by hand. Timers behave the same regardless of how they got there."
**Touches:** frontend, backend. No infrastructure.
**Stories:**
- `cmt-1` — Extractor schema + `ExtractedStep` + `ai_extractor` prompt emit per-step `timers: [{duration_minutes, label}]`. Clamp & filter invalid values without failing import.
- `cmt-2` — `create_recipe_task` persists `timers`; clamp-on-drop writes one `service="api", error_type="TimerClamp"` audit row.
- `cmt-3` — Extend 3+ eval fixtures with ground-truth timers; new `timer_extraction_f1` metric (soft gate at ≥0.7).
- `cmt-4` — Flutter: prefer `step.timers` over regex; new `step_timers_row.dart` (up to 4 + "+N more"); upgraded regex (multi-match, ranges, decimals, aliases) in `timer_regex.dart`.
- `cmt-5` — Always-visible manual timer icon in the cook-mode header; `ManualTimerSheet` bottom sheet; routes through existing `_startTimer`.
- `cmt-6` — End-to-end widget regression sweep covering all three paths (extracted / regex / manual).

---

## Addendum — 2026-04-20 — Activity Hub polish (two epics)

### Epic: `epic-activity-badge-integrity` (planned 2026-04-20)

**User sees:** The bell number in the bottom nav now matches what's actually actionable — unread notifications + in-progress / needs-review / failed imports. No more ghost counts for items that aren't visible anywhere. Tapping the bell opens whichever tab has more to look at.

**Touches:** backend (unread-count endpoint refactor, dead user_activity write removal), frontend (badge wiring, bottom-nav tap destination). No infra.

**Depends on:** none (extends the shipped `activity-hub-redesign`).

### Epic: `epic-activity-full-history` (planned 2026-04-20)

**User sees:** Scroll back through every notification and every import you've ever had, regardless of age, archive state, or read state. Both tabs gain a `See all (N)` footer with lazy pagination. "All Set" / "All clear" empty states carry an inline `See past …` link when history exists.

**Touches:** backend (cursor pagination on activities + import-items + import-jobs, new see-all-count endpoints), frontend (Notifications See-all footer, Imports See-all pagination, empty-state gateway link). No infra.

**Depends on:** `epic-activity-badge-integrity` (reads the new `unread-count` payload shape; uses the new `NOTIFICATION_TAB_TYPES` allow-list).

## Addendum — 2026-04-20 — Ingredient canonicalization retired

### Epic: `epic-ingredients-string-simplification` (planned 2026-04-20, refined via party-mode)

**User sees:** Recipes import and display exactly as before, but the system no longer canonicalizes ingredient names across recipes. Shopping lists built from Meals with overlapping ingredients show duplicate line items (e.g. "olive oil × 2" adjacent on the list). Pantry no longer cross-references the shopping list — the "I already have this, skip it" affordance is gone. Ingredient autocomplete in recipe create/edit is replaced with plain text entry (autocomplete-rebuild is a future epic). Pending-review ingredient badge disappears. Admin surface does not change (no pending-review queue existed).

**What gets ripped out (one epic, 5 stories):**
- Runtime: `match_ingredients_task` (467 LOC), `ingredient_resolver.py` (88 LOC), MCP `_resolve_ingredient` matcher, `aggregate_meal_ingredients` dedup, `check_pantry` path, all `ingredient.category` readers.
- Endpoints: `GET /v1/ingredients/search`, `POST /v1/ingredients`, `GET /v1/ingredients/{id}`.
- Schema: `ingredient_substitutions` table (empty in prod), `ingredient_matches` cache table, HNSW + pg_trgm indexes on ingredients, `search_ingredients_fuzzy()` function, columns `embedding` / `parent_id` / `pending_review` / `is_canonical` / `aliases` / `category` from `ingredients`, unique constraint on `ingredients.canonical_name`.
- Flutter: `ingredient_search.dart` server call, `ingredient_row_state_badge.dart` (96 LOC) + its test (95 LOC), `searchIngredients / createIngredient / getIngredient` API-client methods, pending-review decoder paths.
- Eval: `ingredient_matching_evaluator.py` and its eval-config registration.
- Seeder: `services/migrator/seeds/ingredients.py`. Scraper source (`services/ingredient-scraper/`) stays untouched but gains a dated "no live consumer" README note.

**What gets retained as placeholder:** `shopping_list_items.already_have_quantity` column (always-NULL, future-hook for pantry-check revival).

**Cross-epic rescope:** `epic-review-import-ingredient-polish` (backlog) loses `riip-4`'s pending-review annotation half and all of `riip-7` (IngredientRowStateBadge). riip-1/2/3/5/6/8 unaffected.

**Known regressions user has accepted:** duplicate shopping-list items; no pantry cross-check; no ingredient autocomplete; `shopping_list_items.category` always NULL; no pending-review admin queue.

**Touches:** backend (large — matcher + MCP + aggregate + pantry-check + 4 category readers + schema migration + endpoint deletion + eval config), frontend (medium — autocomplete removal + badge deletion + import-item decoder), infra (none). PRD + architecture.md carry dated addenda; `epic-review-import-ingredient-polish.md` carries a dated rescope note; `INGREDIENT_SCRAPER_DESIGN.md` carries a dated "design frozen" note.

**Depends on:** nothing new; touches code from completed epics (`epic-calendar-per-meal-shopping-add`, `epic-meals-calendar`, `epic-pantry`, `epic-notifications-*` unaffected).

**Future placeholder (backlog, not this epic):** *Ingredient autocomplete rebuild* — user-history-backed, frozen-seed, or LLM-completion-driven. Pick one when the UX pain warrants it.

---

## Addendum — 2026-04-20 — Home Meal promotion

### Epic: `epic-meals-home-promotion` (backlog, Flutter-only)

**User sees:** Long-press a recipe on home to enter selection mode, tap another recipe to turn them into a Meal with one action — or tap an existing Meal in the selection to add recipes to it. Bulk-archive works across recipes + Meals in the same selection. A refreshed MealTile shows the component recipes by name right on the card, with a "Meal" accent pill and favorite star parity with RecipeCard. Two new client-side filters: Show [All / Recipes only / Meals only] and "Hide components of Meals."

**Touches:** frontend only (Flutter — `home_screen.dart`, `filter_bottom_sheet.dart`, `meal_tile.dart`, plus 4 new home widgets); backend none; infra none.

**Stories (5):**

1. **hmp-1** — MealTile v2: component chips + accent chrome ("Meal" pill + 2-px border) + favorite star overlay + selected-state checkmark. Ships independently as a visible Day-1 polish win.
2. **hmp-2** — Home selection mode: long-press entry, `SelectionAppBar` swap, `HomeSelectionController` state machine, bulk-bar scaffold with correct labels but stub actions. Retires the old `_showRecipeActions` home sheet.
3. **hmp-3** — Bulk actions wired live: Create Meal (opens foundation's CreateMealSheet), Add to "<Meal>" (iterates `POST /v1/meals/{id}/recipes` with client-side dedup), Archive (parallel `bulkArchiveRecipes` + per-Meal `archiveMeal`); shared partial-failure snackbar + dialog pattern.
4. **hmp-4** — FilterBottomSheet gains a Show axis ([All / Recipes only / Meals only]) + "Hide components of Meals" toggle; both client-side, instant apply.
5. **hmp-5** — Zero-Meal zero-regression widget test, selection + filter interaction, refresh-while-selected, a11y sweep.

**Depends on:** foundation + discoverability (both done). **Parallelizable with:** sharing-and-ai, cook-mode-polish, cook-mode-timers. **Soft conflict with:** `epic-bugs-home-polish` (both modify `home_screen.dart`).

**Locked decisions (pre-party-mode):**
- Gesture: long-press (A) — no pencil toggle, no FAB. Selected 2026-04-20.
- Bulk bar is context-sensitive with one primary action + Archive secondary. Selected 2026-04-20.
- Filters are client-side only — zero backend surface. Compute `componentRecipeIds` from the already-loaded `meals` list. Selected 2026-04-20.
- Visual: G2 + G3 (component chips + accent chrome), plus favorite-overlay parity fix. Selected 2026-04-20.
- Old home long-press sheet (Start Cooking / Archive) is retired — both actions already exist on recipe detail per research. Selected 2026-04-20.

## Addendum — 2026-04-20 — Extractor field-level inference

### Epic: `epic-extractor-field-inference` (planned 2026-04-20, refined via party-mode)

**User sees:** On Review Import (and Recipe Edit for any recipe imported after this epic ships), recipe-level fields the AI guessed — cook time, prep time, total time, servings, description, cuisine, category, primary vibe, secondary vibe — render with a small ✨ sparkle icon next to the field label. Tapping opens a short explainer ("AI guessed this value. Verify or edit it below — your correction helps the extractor learn."). Any edit removes the sparkle immediately; on Review Import the correction dispatches silently to a new `POST /v1/import-items/{id}/corrections` endpoint that writes one `error_logs` row (`service="audit"`, `error_type="InferredFieldCorrected"`, metadata `{field, original, corrected, was_inferred}`). Extraction confidence is penalized proportionally (`0.05 × min(inferred_count, 5)`, cap 0.25) so guess-heavy imports correctly flip to yellow "needs review".

**What gets built (one epic, 8 stories — ~6.5 days):**
- Backend foundations (efi-1): `EXTRACTOR_INFER_MISSING_FIELDS` flag + `INFERABLE_FIELDS` allow-list (9 fields) + `inference_prompt.py` + `inference_guardrails.py` (clamp/truncate/validate + audit log) + `apply_inference_penalty` + `log_inferred_field_clamp` helper with AST-lint enforcement.
- Extractor prompt rewrites (efi-2): ai / vision / text extractors splice in the inference rule; `ExtractedRecipe.inferred_fields: list[str]` added; schema extended; `json_ld` untouched (always emits `[]`).
- Persistence wiring (efi-3): `extract_recipe_task` runs guardrails + penalty + persist; `recipes.inferred_fields JSONB` migration; `create_recipe_task` copy; `GetRecipe` / `UpdateRecipe` surface + shrink-only validation enforcing `new_set ⊆ old_set`.
- API surface (efi-4): `inferred_fields` hoisted at response root on `GetImportItem` / `list_import_items` / `list_import_jobs`; new `POST /v1/import-items/{id}/corrections` endpoint; server resolves original from `parsed_recipe` to minimize client trust surface.
- Flutter primitives (efi-5): `InferredFieldBadge` widget (`Icons.auto_awesome`, 14pt, tertiary tint, 40pt tap target, bottom-sheet explainer); `kInferableFields` constant; `submitImportCorrection` API-client method; `ImportItem.inferredFields` + `Recipe.inferredFields` decoders.
- Review Import wiring (efi-6): badge on 9 field labels + dismiss-on-first-edit + 1500ms debounced dispatch on focus-loss; approval payload ships mutated `inferred_fields`.
- Recipe Edit wiring (efi-7): badge + dismiss-on-edit; `UpdateRecipe` round-trip sends shrunken `inferred_fields`; NO correction dispatch in v1 (deferred).
- Eval (efi-8): `field_inference_accuracy` + `hallucination_rate` metrics + baseline + per-extractor breakdown; soft gates only in v1.

**Out of scope (explicit deferrals):**
- Per-ingredient inference (qty / unit / notes) — follow-up epic `epic-extractor-ingredient-inference` informed by correction-log data from this epic.
- Recipe-Edit correction dispatch — badge UX wired, POST round-trip waits for a future consolidated corrections dashboard.
- Hard CI gates on the new eval metrics — measured + reported in v1; tuned post-ship once real traffic data accumulates.
- Retroactive enrichment of legacy `parsed_recipe` rows — no backfill; they render as `inferred_fields: []`.
- Admin UI for reading correction logs — SQL-queryable only in v1.
- `inferred_fields` diff / highlight in recipe version history — low-value for v1.
- Vibe taxonomy expansion — provenance-only change; the existing two vibe slots stay.

**Touches:** backend (extractors × 3 prompt + parsing, `extract_recipe_task`, `create_recipe_task`, `GetRecipe` / `UpdateRecipe`, new `submit_correction` endpoint, recipes migration, eval suite); frontend (1 new widget + 2 screen wirings + model + API-client + 1 constant); infra (none — feature flag reuses existing ECS env-var pattern).

**Depends on:** none new. Coordinate merge order with `epic-cook-mode-timers` (cmt-1, cmt-2) and `epic-review-import-ingredient-polish` (riip-3) only if two of those ship simultaneously — they all touch the three LLM extractors' prompts; combined PR acceptable. Flag coordination: `EXTRACTOR_INFER_MISSING_FIELDS` flips last (after `EXTRACTOR_EMIT_CONFIDENCE` and `EXTRACTOR_EMIT_CANONICAL_UNITS`).

---

## Addendum — 2026-04-21 — Performance Health Initiative (3 epics)

### epic-perf-infra-and-measurement

**user sees:** the app snaps on every screen — cold-start p95 drops ~30–50%, slow-query log + `analyze_latency.py` make the next regression provable in minutes. **Touches:** frontend: no; backend: yes (new ops script, new Redis JWKS wiring, pool config); infra: yes (RDS upgrade + param group + PI, Redis, ECS task bump, ALB tuning, `CONCURRENTLY` migration backport).

### epic-perf-backend-query-tuning

**user sees:** list screens (home meals, shopping lists, activity, calendar, search, meal events) return in under 300ms at p95 even after a few months of use. **Touches:** frontend: no; backend: yes (N+1 closures + eager-loads + redundant-query dedup in ~8 endpoints); infra: no (no new indexes beyond per-story additions, no terraform).

### epic-perf-flutter-client-polish

**user sees:** activity badge no longer double-refreshes, recipe detail re-opens instantly, images don't redownload, home filter stays snappy. **Touches:** frontend: yes (consolidated `activityHubProvider`, `CachedNetworkImage` sweep, detail keep-alive, home filter regression fix); backend: no (uses existing endpoints); infra: no.

## Addendum — 2026-04-21 — Notifications Comprehensive Coverage

Test push works end-to-end on Leo's iPhone (commits `4827d96`, `7fe41d9`). Now bringing every other notification up to the same proven-working bar — rich copy, per-category prefs, scheduled reminders, timer quick actions on both platforms, Live Activities, partner activity. See `prd.md` "Notifications Comprehensive Coverage" addendum for the full rationale.

- [epic-notifications-foundation-prefs-copy](epic-notifications-foundation-prefs-copy.md) — **User sees:** Profile → Notifications shows per-category toggles (Meals, Timers, Shopping, Partner activity, Imports, Friends/invitations); existing import push is rich ("Your Sweet Potato Quiche needs a review") with cover image; meal pushes deep-link to a specific meal detail screen. — **Touches:** frontend, backend (one migration). **Blocks all other notification epics.**
- [epic-notifications-meal-reminders](epic-notifications-meal-reminders.md) — **User sees:** Meal create sheet has a "Remind me at" time picker (defaulted to slot's default); at that time, every accepted participant gets a push with the recipe name; tapping opens meal detail. — **Touches:** frontend, backend (one migration + Celery beat task). **Depends on:** foundation.
- [epic-notifications-timer-actions-live-activities](epic-notifications-timer-actions-live-activities.md) — **User sees:** Active cooking timer appears in Dynamic Island + lock screen with live countdown; expiration push shows +2/+5/Reset/Stop on iOS AND Android; if app is foreground, an Apple-style overlay shows the same actions. — **Touches:** frontend, iOS native (no changes — Swift UI already exists). **Depends on:** foundation.
- [epic-notifications-partner-activity](epic-notifications-partner-activity.md) — **User sees:** Pushes when a partner forks/notes/cooks your recipe (with cover image); meal-invite acceptance pings back to the inviter; 2-hour deferred "How did your X turn out?" prompt after a cook log. — **Touches:** backend (event hooks + one Celery delay task), no new frontend. **Depends on:** foundation.
- [epic-notifications-scheduled-reminders](epic-notifications-scheduled-reminders.md) — **User sees:** Shopping items with a `due_at` trigger a morning-of summary push; bulk imports that fully fail get one consolidated "Couldn't import" push. — **Touches:** backend only (Celery beat task + failure-path callsite). **Depends on:** foundation.

## Addendum — 2026-04-22 — Reactive State Permeation (3 epics)

Motivation: dogfood complaint — "a ton of places in the app where the state is not updating whenever we update the underlying objects. I click dismiss on a recipe import, it stays in that view. I recently added a recipe, it doesn't show up until I refresh." Frontend audit confirms ~50% of mutation sites do not invalidate cross-surface state. Fix with a cross-cutting `MutationBus` primitive + convention + systematic migration of every mutation site across features.

User-locked decisions (2026-04-22 batch):
- **Scope split**: Foundation epic (Home + Imports — fixes both named bugs) + two per-domain migration epics.
- **Update style**: Reconcile-only for v1; keep existing optimistic `setState` on mutations that already have it (dismiss/favorite/check-off). Optimistic-everywhere deferred to a polish epic.
- **Failure UX**: Toast + automatic rollback (Snackbar with tap-to-retry).
- **WebSocket expansion**: **Deferred.** Existing WS on shopping lists + recipe-book recipe CRUD stays as-is. No new WS routes for meals/calendars/meal_events this round. Client-side MutationBus is the only new plumbing; WS frames lower into the bus via a thin adapter.

Epics, in dependency order:

- [epic-reactive-foundation-home-imports](epic-reactive-foundation-home-imports.md) — **User sees:** Tapping Dismiss on an import row immediately removes it from every Imports surface (Activity shell, tab, See-all footer) with no manual refresh. Creating a recipe via URL/Photo/Wizard: on pop back to Home, the new recipe is already in the grid — no pull-to-refresh needed. Archive, unarchive, favorite, fork, move, bulk-archive on a recipe: every surface showing that recipe reflects the change immediately. — **Touches:** frontend (new `MutationBus` primitive, HomeScreen migration to `homeContentProvider`, ImportHistoryScreen + `importsSeeAllProvider` + activity shell badge fast-path, all recipe mutation sites emit events), backend (`POST /import-items/{id}/dismiss` returns full updated `ImportItem.Response`; `POST /recipes/{id}/favorite` returns full resource), infrastructure (None). **Blocks:** both migration epics below.

- [epic-reactive-migration-meals-calendar](epic-reactive-migration-meals-calendar.md) — **User sees:** Creating, editing, archiving, or favoriting a meal updates the Home grid, Meal detail, and any book-scoped meal list instantly. Adding or removing a component recipe updates the Meal detail and any "Used in these Meals" recipe-detail surface. Creating, editing, deleting, or marking-cooked a meal event updates the Calendar grid, day sheet, and the meal detail "upcoming plans" row instantly. — **Touches:** frontend (meals service, calendar service, meal-event service all emit events; `mealsByBookProvider`, `calendarsListProvider`, `mealEventsByDayProvider` subscribe; getIt-held meal-list double-source-of-truth collapsed into Riverpod), backend (None), infrastructure (None). **Depends on:** foundation epic.

- [epic-reactive-migration-books-profile-pantry-and-polish](epic-reactive-migration-books-profile-pantry-and-polish.md) — **User sees:** Creating, renaming, archiving, or changing member-role on a recipe book updates the Books list, Home header, and shared-books screens immediately. Updating notification prefs, profile name, or avatar updates Profile and any derived surfaces (push-prefs screen, admin inbox name) instantly. Adding, checking-off, or removing a pantry ingredient updates the Pantry screen (and auto-sync-from-shopping-list surface) instantly. Mutation failures always show a tap-to-retry Snackbar via a centralized copy map — no silent drops. — **Touches:** frontend (books/profile/pantry mutation sites emit; `ShoppingCartService` WS adapter lowers frames into bus to eliminate double-source-of-truth; `mutation_failure_copy.dart` central verb/noun map), backend (None), infrastructure (None). **Depends on:** foundation epic.

## Addendum — 2026-04-22 — Meal Cook Mode (3 epics)

Motivation: user asked for a cooking mode for a whole Meal. A Meal is a curated list of component recipes, but today there is no unified cook flow — the user has to cook each component separately. Pair that with the fact that today's recipe cook mode is entirely ephemeral (app kill = progress lost), which is mildly annoying for one recipe and unacceptable for a 90-minute multi-recipe meal. We also take this opportunity to remove the experimental `CookModeChatSheet`, which the user explicitly wants pulled from both cook modes until the UX is rethought.

User-locked decisions (2026-04-22 batch):
- **Steps sectioned per-recipe with headers** (`Dressing · 3 / 7`); ingredients interlaced into one combined strip. No smart scheduler ("start sauce while pasta boils") — deferred.
- **No ingredient dedup** — reuse `aggregate_meal_ingredients` one-row-per-recipe-ingredient, tag each chip with its source recipe name.
- **FAB entry** on meal detail, bottom-right, mirroring recipe-detail's "Start Cooking" FAB.
- **Shared widgets** — extract cook-mode atoms (`IngredientStrip`, `StepNavigator`, `StepTimersRow`, `ManualTimerSheet`, timer services) for both recipe and meal cook modes to consume; introduce a `CookPlan` abstraction (single recipe = 1-component plan; meal = N-component plan).
- **Per-component post-cook rating** — N star rows, one `cooking_logs` row per rated component. No new `meal_cooking_logs` table.
- **Persistent resume for BOTH recipe and meal cook** — SharedPreferences keyed by `recipe_id` / `meal_id`; Resume/Reset gate when prior state exists; explicit in-cook "Reset" affordance.
- **Remove `CookModeChatSheet`** from both cook modes — explicit deletion, not a deferral.

Epics, in dependency order:

- [epic-cook-mode-remove-chat](epic-cook-mode-remove-chat.md) — **User sees:** The AI chat bubble in the recipe cook-mode header is gone. Recipe cook-mode header is simpler: back, title, manual-timer, cooking-time badge. No regression in ingredient strip, step navigation, timers, or post-cook flow. — **Touches:** frontend (delete `cook_mode_chat_sheet.dart` + chat button in `_buildHeader` + related tests + any route wiring; grep gate in CI), backend (None — route stays for potential future repurposing), infrastructure (None). **No dependencies.** Ships independently.

- [epic-cook-mode-resume](epic-cook-mode-resume.md) — **User sees:** Mid-cook, user backgrounds or kills the app. Re-opening the same recipe from home → FAB "Start Cooking" → a Resume/Reset gate sheet appears: "Started 2h ago, step 3 of 12 · [Resume] [Start Over]". Tapping Resume: state restored — same step, same ingredients checked, same timers rebuilt (with expired ones firing a "While you were away" snackbar). Tapping Start Over: fresh state, persisted key cleared. A new "Reset" affordance in the cook-mode header lets the user blow away state without waiting for a kill. Post-cook sheet submission clears the key automatically. — **Touches:** frontend (new `CookSessionPersister` service over SharedPreferences; Resume/Reset gate sheet; debounced writes from `cook_mode_screen.dart`; in-cook Reset affordance; state schema versioning for forward-compat), backend (None), infrastructure (None). **Dependencies:** none structurally, but meal-cook epic below reuses `CookSessionPersister` keyed by `meal_id` — ship this first.

- [epic-cook-mode-meal](epic-cook-mode-meal.md) — **User sees:** On a meal detail screen, user taps a bottom-right FAB "Start Cooking". A new `MealCookModeScreen` opens. At the top: a combined ingredient strip showing every ingredient from every component recipe, each chip tagged with its source recipe name ("from Dressing"). Below: a step card with a section header `Dressing · 3 / 7` that the user walks through; swiping past the last step of Dressing lands them on step 1 of Salad with a new header. Active timers show in a single meal-level row regardless of which recipe they came from; label disambiguation prepends the component name on collision. On completion: a multi-component post-cook sheet asks for N ratings (one per component); submission writes N `cooking_logs` rows and clears the meal's persisted cook-state key. Backgrounding mid-cook → Resume gate identical to recipe cook. — **Touches:** frontend (new `MealCookModeScreen` + `/meals/:id/cook` GoRoute; shared widget extraction for `IngredientStrip`/`StepNavigator`/`StepTimersRow`/`ManualTimerSheet`; `CookPlan` abstraction; FAB on `meal_detail_screen.dart`; section-header rendering; multi-component `PostCookFeedbackSheet` variant; client-side N parallel recipe fetches; offline per-component fallback), backend (None — reuses existing `GET /v1/meals/{id}`, `GET /v1/recipes/{id}`, `aggregate_meal_ingredients`, `POST /v1/cooking-logs`), infrastructure (None). **Depends on:** `epic-cook-mode-resume` (reuses `CookSessionPersister`); `epic-cook-mode-remove-chat` (soft — if chat ships before this, fine; otherwise meal cook ships without chat too).

## Addendum — 2026-04-22 — Extractor Richer Ingredient Extraction (1 epic)

Motivation: two concrete bugs in ingredient extraction surfaced during dogfood. "1 clove garlic" loses its `clove` unit (LLM folds it into the name under `riip-3`'s strict *"EXACTLY one of these tokens"* rule). "300 gram of vinegar" on URL imports loses BOTH quantity and unit because `json_ld.py` emits `{quantity: null, unit: null, name: null, text: "300 gram of vinegar"}` for every entry in the Schema.org `recipeIngredient` array — it's a plain-string list by spec, no structured data to pull. The review screen then dumps the full raw text into the name field. Both bugs share a root cause: **ingredient-level extraction fidelity is too conservative**.

User-locked decisions (2026-04-22 batch):
- **Soften the canonical-units prompt, don't expand the enum** — keep the 19-token list as the *preferred* set; allow freeform unit words (stalk, bunch, packet, sprig, head, can, sheet) when the source uses them literally; drop the "EXACTLY one of these" strictness.
- **Bias toward convertible units** — when source is ambiguous between a count unit and a measurable one (cup/tbsp/tsp/ml/l/g/kg/oz/lb/fl oz), prefer the convertible one. Future-proofs a later US↔metric conversion feature.
- **JSON-LD ingredient-parse-only AI pass** — when JSON-LD yields text-only ingredients, run a focused gpt-4o-mini call against the string list to structure them. Recipe-level fields (name, times, servings) still come from JSON-LD. ~$0.0001 per URL import.
- **Aggressive qty/unit/notes capture** via explicit prompt instruction + worked examples (clove/gram/stalk/salt/half-cup) — stop dropping what's in the source.
- **Expand `unit_aliases` seeds** (~15 new plural→singular: stalks→stalk, cans→can, etc.) so `normalize_unit_display` covers the words the softened prompt now accepts.
- **Two new feature flags** — `EXTRACTOR_SOFTEN_UNIT_RULE` (default on, rollback to riip-3 prompt via off), `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` (default on, rollback to text-only ingredients via off). Both flippable via ECS task-def.
- **No Flutter changes** — research confirmed Review Import/wizard/edit already render freeform units; `UnitInput` `SessionAliasMap.coerce` handles non-canonical units on blur. Fix backend → frontend becomes correct automatically.
- **No parser-service changes** — user confirmed "Maybe just the extractor honestly."

Epic:

- [epic-extractor-richer-ingredients](epic-extractor-richer-ingredients.md) — **User sees:** A URL import (with Schema.org JSON-LD) that previously dumped "300 gram of vinegar" into the name field now shows `[300] [g] [vinegar]` as three separate fields. "1 clove garlic, minced" from a photo import now shows `[1] [clove] [garlic]` with notes "minced" auto-expanded — the `clove` unit is no longer folded into the name. Recipes with freeform units ("2 stalks celery, chopped") persist the freeform unit literally, surviving the backend's normalize-on-write pass. Review Import, the recipe wizard, and recipe edit all render the richer structured output with zero UI changes (frontend already supported it). — **Touches:** frontend (None — research confirmed the Flutter ingredient row already handles freeform units and all five structured fields), backend (soften `unit_prompt.py` + worked examples in `ai_extractor`/`vision_extractor`/`text_extractor` + new `ingredient_parse.py` module for JSON-LD text-only lists + `extract_recipe_from_html` parse-pass invocation + `unit_aliases` seed expansion migration + two new feature flags), infrastructure (None — one Alembic migration, two env var flags flipped via ECS task-def). **No dependencies.** Independent of in-flight epics; coexists with riip/efi via flag coordination.


## Addendum — 2026-04-22 — Cook mode redesign (toggleable per-recipe flow)

**Context.** Meal cook mode ships and works, but real-kitchen dogfood surfaced that strictly sequential (Dressing → Salad → Chicken) doesn't match how people cook — downtime in one recipe wants to be filled with prep on another. Plus ingredient text is hard to read, the header has a redundant X button, and the Expand/Collapse affordance on the ingredient strip no longer earns its keep. User-locked decisions for this redesign (see PRD addendum dated 2026-04-22):

- **Per-recipe step map + toggle bar** — state shape changes from flat `currentStep` int to `Map<recipeId, stepIndex>` + `activeRecipeId`.
- **Full ingredient list always expanded, grouped by recipe** — no compact strip, no Expand button, no `INGREDIENTS` ALL-CAPS label, no per-chip source tag (group header replaces it).
- **Remove section header above step card** — toggle bar + per-recipe bottom progress replace it.
- **Bottom progress indicator scoped to active recipe** (not meal-flat).
- **Auto-advance on recipe end** — Next on last step of a recipe jumps to first unfinished recipe in plan order.
- **Timer chips prefix recipe name** — `Dressing · 0:17`. When a timer fires on a non-active recipe: snackbar + toggle pill pulse (no auto-switch).
- **Remove the redundant X button** from cook-mode header (both modes).
- **Persister schema v2** — one-shot migration from v1 on read; always writes v2 from the next save.

Two epics, sequential:

- [epic-cook-mode-layout-polish](epic-cook-mode-layout-polish.md) — **User sees:** both cook modes get a shared visual polish — the X close button is gone from the header (back is the sole exit), the `INGREDIENTS` ALL-CAPS label and Expand/Collapse button are gone (ingredients always shown), chip text is enlarged and more readable (14px name + 14px w600 accented quantity, 2-line name support, `IntrinsicWidth` so it doesn't clip at large text scales), meal mode's `--- From Dressing ---` dashed dividers are replaced with clean typographic group headers, and the `Dressing · 1 / 7` section header above the step card is gone. Progress bar margin tightens 48 → 24 to align with step card edges. — **Touches:** frontend (cook_mode_screen + meal_cook_mode_screen + shared ingredient_strip; recipe_section_header render call commented out for later deletion), backend (None — pure Flutter polish pass, no API shape change), infrastructure (None — no env vars, no CI changes). **No dependencies** beyond shipped epics.
- [epic-cook-mode-multi-recipe-flow](epic-cook-mode-multi-recipe-flow.md) — **User sees:** a toggleable recipe bar below the ingredient list in meal cook mode, with pills like `Dressing 5/7` · `Salad 2/4` · `Grilled Chicken 0/9`. Tapping any pill swaps the step card to that recipe at its remembered step. Bottom progress bar + `5 / 7` label scope to the active recipe. On the last step of a recipe, Next auto-advances to the first unfinished recipe. Timer chips at the top always say which recipe they belong to (`Dressing · 0:17`). When a timer fires on a non-active recipe, a completion snackbar appears and that recipe's toggle pill pulses briefly — no auto-switch. Kill/resume restores per-recipe step state exactly. Single-recipe cooks hide the toggle bar entirely (no regression). — **Touches:** frontend (meal_cook_mode_screen state refactor, new RecipeToggleBar widget, active_timers_row recipe-name prefix, cook_plan helpers, recipe_section_header deletion), backend (None — persister schema v2 is client-side only), infrastructure (None). **Depends on** epic-cook-mode-layout-polish.


## Addendum — 2026-04-23 — Frontend Performance Audit & Client-Side Analytics (3 epics)

**Context.** Server-side query tuning (`epic-perf-backend-query-tuning`), infra floor (`epic-perf-infra-and-measurement`), and Flutter client polish (`epic-perf-flutter-client-polish`) shipped 2026-04-21. User sat with Chrome DevTools open on Flutter web and noticed a steady stream of repeated GETs — notably to `/v1/import-items` — and asked three questions: (1) can we audit every page to fetch only the absolute minimum, (2) can we track "time to first paint" on mobile the way Lighthouse does on web, (3) how do people do perf on iOS where Lighthouse doesn't apply.

Phase-2 audit (2026-04-23) enumerated the Flutter fetch surface and surfaced concrete wins: duplicated `getRecipeBooks()` across 7 screens (no shared provider), N+1 `listImportItems(jobId)` per job on Activity Hub, overlap between the 30s activity poll and MutationBus silent reloads, notifications-tab double-fetching on mount (`getActivities` + `refreshUnreadCount`), session-level caches with no TTL, 16 uncached `Image.network` sites in calendar/recipes, and no Dio request-dedup. Separately, the existing `analyze_latency.py` measures server-side latency (`request_latencies` + `task_latencies`) but nothing on the client — no route-paint, no cold-start, no frame-jank, no OS-level hang data.

User-locked decisions (2026-04-23 batch):
- **Three-epic split**: fetch minimization, client analytics, debug tooling. Parallelizable after analytics lands the `client_latencies` table.
- **Storage**: custom `/v1/client-latencies` + Firebase Performance Monitoring as secondary. Custom is primary source of truth; Firebase is free cross-check.
- **OS-level telemetry**: iOS MetricKit + Android JankStats both wired.
- **Platform scope**: all three platforms (iOS + Android + Flutter web) from day one. Web uses browser Navigation Timing API in place of MetricKit.

Three epics:

- [epic-perf-frontend-fetch-minimization](epic-perf-frontend-fetch-minimization.md) — **User sees:** every screen that used to issue a visible stream of duplicate GETs in Chrome DevTools (home → recipe detail → Activity Hub loop) issues measurably fewer — at least 30% fewer by call count on the canonical dogfood flow. Home stops double-fetching recipe books; recipe detail shares the books provider instead of calling `getRecipeBooks()` itself; Activity Hub fetches all visible import items in one round-trip instead of N; notifications tab opens with one network call, not two; book detail stops pre-fetching meals on scroll and lazy-loads when the Meals tab is tapped; images on the calendar and recipes screens arrive from disk cache on the second visit instead of the network. Nothing user-visible breaks — the same data appears in the same places, just with a lighter network footprint. — **Touches:** frontend (new `recipeBooksProvider` usage across home/recipe detail/5 import entry points, Activity-hub poll+MutationBus dedup, notifications-tab single-fetch-on-mount, session-cache TTL for books/profile/home/pantry/prefs, lazy `listMealsInBook`, Dio GET-dedup interceptor, `Image.network → CachedNetworkImage` sweep across calendar + recipes features, CI grep guard for `Image.network(`), backend (additive response-shape trims — `?include=` on `GET /v1/recipes/{id}`, optional `unread_count` field on `GET /v1/activities`, either `GET /v1/import-items?job_ids=<csv>` or `GET /v1/import-jobs?include=items` for N+1 collapse), infrastructure (None — all existing endpoints, no new env vars, no terraform). **No dependencies.** Parallelizable with the other two perf epics.
- [epic-perf-client-analytics](epic-perf-client-analytics.md) — **User sees:** as an admin (Leo), a new Client tab appears on the existing `/admin/metrics` dashboard showing p50/p95/p99 tables for cold-start, route-paint, network-request, and frame-jank metrics, sourced from real user sessions — filterable by platform (ios/android/web), app version, and route. Alongside the existing server-side Endpoints/Tasks tabs, Leo can now answer "is this slow because of the backend or because of the app?" from a single URL. iOS-specific hang rate / launch time / memory warnings arrive daily from MetricKit; Android equivalent from JankStats; web equivalent from the browser's Navigation Timing API. Firebase Performance Monitoring (enabled via `firebase_performance` pub package) provides a zero-config secondary dashboard as a cross-check. — **Touches:** frontend (new `PerfNavigatorObserver` emits `route_paint`, new cold-start timing in `main()`, Dio timing interceptor for `network_request`, `SchedulerBinding.addTimingsCallback` aggregation for `frame_jank_p95`, batched client-side flush service to `POST /v1/client-latencies`, iOS platform channel + Swift `MetricKitReceiver` using `MXMetricManagerSubscriber`, Android platform channel + `JankStats.createAndTrack` on main activity, Flutter-web `dart:html` Navigation Timing bridge, `firebase_performance` wiring on Dio interceptor, new Client tab on the admin dashboard), backend (new `client_latencies` table migration, `POST /v1/client-latencies` batched ingest endpoint with 100-event cap + 413 beyond, `analyze_latency.py --section client` + `--section all` unified view, aggregation endpoints for the dashboard mirroring server-side stats), infrastructure (one Alembic migration for `client_latencies`; Firebase project already exists — enable Performance Monitoring in Firebase console; no new AWS resources). **No hard dependencies**; soft-depends on nothing in-flight.
- [epic-perf-debug-tooling](epic-perf-debug-tooling.md) — **User sees:** two new tools that keep perf honest after the audit ships. (1) In debug builds, long-pressing a corner of the home screen toggles a floating overlay listing the last N HTTP requests with their durations and status codes — a dogfood self-audit tool so Leo can spot regressions without opening Chrome DevTools. (2) A `bin/perf-audit` script that drives each top-level screen through a Patrol-based integration harness, records actual HTTP-call counts per screen, and diffs against a committed per-screen budget YAML — the budget file is the regression gate. The same harness in assert-mode runs on every PR and fails CI if any screen exceeds its budget (e.g., adding a duplicate `getRecipeBooks()` anywhere triggers a failure). Admins reading the `analyze_latency.py --regression-hunt` output now see both server-side and client-side regressions side-by-side. — **Touches:** frontend (new `PerfOverlay` widget wired behind `kDebugMode` long-press, Patrol integration test harness that drives home/books/recipe-detail/activity-hub/meals/calendar/profile/search/cook-mode screens and captures call counts, budget YAML committed at `tools/perf-budgets.yaml`), backend (`analyze_latency.py --regression-hunt --section client` extension to flag client-side p95 shifts > 1.5× baseline), infrastructure (new GitHub Actions workflow step that runs `bin/perf-audit --assert` on PR — Patrol pre-installed in the existing Flutter CI matrix, adds ~3 min to the job). **Soft depends on** epic-perf-client-analytics (the CI guard can run against budgets without live telemetry, but the `analyze_latency.py --section client` extension assumes `client_latencies` exists).

All three epics share a **zero-regression bar**: no user-facing behavior change except latency — if anything looks different or a feature breaks, it's a bug and blocks the epic.

## Addendum — 2026-04-23 — API Async SQLAlchemy Migration

**User-locked decision (2026-04-23):** root cause of client-observed 5s tails on `GET /v1/meals/{meal_id}` (server-side p95 188ms, client-side p95 5192ms) + `POST /v1/users/me/client-errors` (p95 5931ms) is **event-loop starvation** — every router handler is `async def` but calls a synchronous `Endpoint.call(...)` inline, blocking the event loop on every request's DB queries. Migrating to async SQLAlchemy + async handlers + async-native SDKs (asyncpg, AsyncOpenAI, httpx.AsyncClient) across `services/api`. Worker, parser, migrator stay sync.

One monolithic epic, ~27 stories, 6 phases. Rollout: incremental per-domain merges → big-bang cutover → hardening. No canary (no traffic-splitting infra); revert-commit rollback within ~10 min. No Flutter changes. Response shapes byte-identical.

- `epic-api-async-migration` — **user sees:** app feels consistently fast; no random multi-second stalls when a background import or OpenAI call is running. GET /v1/meals/:id client-side p95 returns from 5192ms to < 500ms. touches: backend (all of services/api), no frontend, no infra (dual pip dep + 2 env vars).
