---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain-skipped
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
partyModeInsights:
  - Data sovereignty as product promise — recipes always exportable, never altered
  - Trust is the north star — permanence, reliability, easy import/export
  - Recipe versioning — auto-snapshots on meaningful edits, full history, one-tap restore
  - Recipe forking — copy between books with lineage, fork creates v1, edits are v2+
  - Three-tier recipe book model — personal, shared, public with fork/share/publish ops
  - Household-first design — both partners are full citizens
  - Two UX modes — curation (couch) and action (kitchen), AI bridges both
  - AI as friction remover — version mgmt, notes, imports, hands-free cooking
  - Concentric circle architecture — core (storage+import+cooking) → middle (AI+search+sharing) → outer (cart, calendar, social)
classification:
  projectType: mobile_app_api_backend
  domain: consumer_food_kitchen_management
  complexity: medium
  projectContext: brownfield
  prdScope: full_vision
inputDocuments:
  - REQUIREMENTS.md
  - docs/MVP.md
  - docs/BIG_ROCKS.md
  - docs/business-logic.md
  - docs/ai-tools.md
  - docs/api-reference.md
  - docs/DATABASE.md
  - docs/database-schema.md
  - docs/db-uml-diagram.md
  - docs/INVITATION_SYSTEM.md
  - docs/RECIPE_IMPORT_SYSTEM.md
  - docs/RECIPE_EXPERIENCE_IMPLEMENTATION.md
  - docs/INGREDIENT_SCRAPER_DESIGN.md
  - docs/SHARED_SHOPPING_CART.md
  - docs/calendar-system.md
  - docs/search-design.md
  - docs/ocr-batch-architecture.md
  - docs/AUTH0.md
  - docs/SETUP.md
  - docs/COST.md
  - docs/VERCEL.md
  - docs/OPENAI_AGENT_SETUP.md
  - docs/EVAL_DESIGN.md
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 22
workflowType: 'prd'
---

# Product Requirements Document - Palateful

**Author:** Leo
**Date:** 2026-03-11

## Executive Summary

Palateful is a kitchen management platform that replaces scattered recipe spreadsheets, bookmarked links, and fragmented cooking workflows with a single trusted home base for your entire cooking life. Built as a Flutter mobile app backed by a FastAPI/PostgreSQL API, Palateful serves households who cook regularly and want a permanent, version-controlled recipe database they fully own — paired with an AI assistant that removes friction from every interaction.

The core problem: recipe collections rot. Spreadsheets go stale, bookmarked links break, and no existing app makes it easy enough to add, organize, and actually cook from your recipes. Palateful solves this by making every touchpoint in the cooking lifecycle — import, iterate, plan, shop, cook — so low-friction that users experiment fearlessly, because nothing is ever lost.

Target users are home cooks (initially the founder and partner) who want a shared household recipe system with personal and collaborative spaces. The platform supports the full cooking lifecycle: OCR/URL/manual recipe import, structured recipe storage with versioning, an AI cooking assistant, shared real-time shopping lists, meal planning, and a hands-free cooking mode.

### What Makes This Special

**Git-for-recipes versioning.** Every meaningful edit creates an automatic snapshot. Users can view history, restore previous versions, and annotate changes — all invisible by default, powerful when needed. No recipe app offers this.

**Recipe forking with lineage.** Copy a recipe from a shared book to your personal book and modify freely. The fork tracks its origin; your changes become new versions. A partner's gluten-free scone becomes your meat-filled glutenous version — both coexist with clear lineage.

**Three-tier recipe book model.** Personal books (private experiments), shared books (household collaboration), and public books (future community discovery). Fork, share, and publish operations flow naturally between tiers.

**Household-first design.** Both partners are full citizens — each with their own recipe books, plus shared spaces for collaborative curation. Not "owner + guest" but true co-ownership of the kitchen.

**AI as friction remover.** The assistant handles version management ("go back to the last version"), recipe notes ("add a note to try extra sugar"), imports ("save this recipe from the link I copied"), and hands-free cooking guidance. It bridges curation mode (couch) and action mode (kitchen) seamlessly.

**Data sovereignty.** Recipes are yours permanently. Always exportable, never altered by the platform. The trust promise: your data is permanent and portable.

## Project Classification

- **Project Type:** Mobile App (Flutter cross-platform) + API Backend (FastAPI microservices)
- **Domain:** Consumer Food/Kitchen Management
- **Complexity:** Medium — real-time collaboration, AI/ML integration, OCR pipeline, no regulatory requirements
- **Project Context:** Brownfield — existing codebase with Flutter app, FastAPI backend, PostgreSQL + pgvector database, Auth0 auth, OpenAI integration, and AWS infrastructure (ECS Fargate, Batch, RDS, S3)

## Success Criteria

### User Success

- **Recipe collection reaches 200+ recipes** — migrated from existing spreadsheet/Notion (~100 recipes) plus new additions over time
- **Active cooking usage 2x/week** — you and your partner regularly cook from the app, not just store recipes
- **Import friction eliminated** — bulk import from spreadsheet/Notion completes successfully, OCR snap-to-recipe works reliably, URL import handles major recipe sites
- **Trust established** — you stop maintaining the old spreadsheet/Notion because Palateful is the single source of truth
- **Partner engagement** — your partner independently adds, forks, and cooks from recipes without needing help
- **"Aha!" moment** — the first time you say "hey Palateful, make a note on this recipe" mid-cook and it just works

### Business Success

- **App Store published** — available on iOS (and eventually Android) for friends and family
- **Household adoption** — you and your partner both use it weekly as your primary recipe tool
- **Friends & family sharing** — 5-10 people in your circle try it and find it useful
- **Cost sustainable** — monthly infrastructure costs stay under $50 during personal/friends-and-family phase
- **No user growth pressure** — success is measured by usage quality, not user count. Growth infrastructure exists but isn't a priority metric.

### Technical Success

- **Data permanence** — zero data loss incidents. Recipes are never corrupted, lost, or silently modified
- **Export always works** — full recipe collection exportable at any time (JSON, and ideally PDF/printable)
- **Sub-2s response times** for all core operations (recipe load, search, AI responses begin streaming)
- **OCR accuracy > 90%** for clearly photographed recipes
- **AI assistant reliability** — tool calls succeed consistently, notes/edits actually persist
- **Monthly cost < $50** for personal usage tier (aligns with COST.md Phase 1 analysis)

### Measurable Outcomes

| Metric | Target | Timeframe |
|--------|--------|-----------|
| Recipes imported from existing sources | 100 | First month |
| Total recipe collection | 200+ | 6 months |
| Weekly cooking sessions from app | 2+ | Ongoing after month 2 |
| Partner active usage | Weekly | Month 2+ |
| OCR import success rate | >90% | Launch |
| AI assistant task completion | >95% | Launch |
| Infrastructure cost | <$50/mo | Ongoing |

## User Journeys

### Journey 1: "The Great Migration" — Leo Imports His Recipe Collection

**Opening Scene:** It's a quiet Saturday afternoon. Leo has 100+ recipes scattered across a Google Sheet and a Notion database — some are just URLs to food blogs, others are hand-typed ingredient lists, a few are photos of his grandmother's handwritten cards. He's been meaning to consolidate them for months. He opens Palateful and taps "Bulk Import."

**Rising Action:** Leo pastes his spreadsheet export (CSV) and kicks off the import. Palateful's parser starts chewing through rows — recognizing URLs, extracting structured data from JSON-LD where available, falling back to AI extraction for messy blog pages. For the photo-based recipes, it queues OCR jobs. A progress indicator shows "78 of 103 processed" and Leo goes to make coffee.

His phone buzzes: "3 recipes need your attention." He opens the notification tray. One URL is a dead link — Palateful shows the cached title and asks if he wants to enter it manually or skip. Another is a low-confidence OCR result where "1 tsp" was read as "1 tbsp" — he taps to correct and confirm. The third is a recipe with no clear ingredient/step separation — the AI's best guess is shown side-by-side with the original image for quick editing.

**Climax:** An hour later, Leo's recipe book has 97 imported recipes, each with structured ingredients, steps, and source attribution. He scrolls through them — his partner's aunt's tamale recipe, that one carbonara he perfected last winter, the Thai basil chicken from a blog that's since gone offline. They're all here, organized, searchable. He stars a few favorites.

**Resolution:** Leo shares three recipe books with his partner: "Our Favorites," "Weeknight Dinners," and "Baking Projects." His partner gets a notification: "Leo shared 3 recipe books with you." The spreadsheet tab stays open for another week, then quietly gets closed forever. Palateful is now the source of truth.

### Journey 2: "The TikTok Find" — Leo Discovers and Cooks a Recipe in One Evening

**Opening Scene:** Leo is scrolling TikTok on the couch after work. A video shows someone making a crispy chili oil noodle dish that looks incredible. The comments have a blog link. He taps Share → Palateful.

**Rising Action:** Palateful receives the URL, extracts the recipe in seconds, and presents a clean preview: ingredients, steps, prep time, a photo. Leo glances at it — looks right — and taps "Save to My Recipes." It lands in his personal book. He thinks, "We should make this Thursday." He drags it onto the meal calendar for Thursday and taps "Add ingredients to cart."

Thursday evening arrives. Leo opens Palateful in the kitchen, pulls up the chili oil noodles, and taps "Start Cooking." The screen shifts to cooking mode — large text, ingredient strip at the top, step-by-step navigation. He's got oil heating in the pan. "Hey Palateful, what's step 3 again?" The AI reads it back. His hands are covered in chili flakes. He swipes to the next step with his elbow.

**Climax:** Mid-cook, Leo thinks the sauce needs more sweetness. He says, "Palateful, make a note — try adding a tablespoon of honey next time." The AI confirms and attaches a note to this recipe. He doesn't stop cooking, doesn't wash his hands, doesn't type anything. The note is just there for next time.

**Resolution:** After dinner, Leo opens the recipe and sees: version 1 (original import), plus his note pinned for next attempt. Next time he makes it, he'll add the honey, and Palateful will auto-snapshot version 2. The original stays intact underneath, always restorable.

### Journey 3: "The Fork" — Partner Creates Their Own Version

**Opening Scene:** Leo's partner is browsing their shared "Baking Projects" book. She spots the scone recipe Leo imported — a buttery, classic English scone. She loves the base recipe but wants a gluten-free version with lemon zest. She taps the recipe, then taps "Fork to My Recipes."

**Rising Action:** Palateful creates a copy in her personal book, marked as "Forked from: Classic English Scones (Baking Projects)." It starts as version 1 — identical to Leo's original. She edits the flour to a GF blend, adds lemon zest to the ingredients, and adjusts the baking time down by 5 minutes. Palateful auto-snapshots version 2 with her changes.

Meanwhile, Leo is at the grocery store. His partner added "GF flour blend" and "2 lemons" to the shared shopping cart. Leo sees the items appear in real-time, grabs them alongside his own list items. No texts needed, no double-buying.

**Climax:** That weekend, they're both in the kitchen. Leo pulls up the original scone recipe in cooking mode. His partner has her fork open on her phone. Same base recipe, two versions, two people cooking side by side. She realizes her GF version needs more liquid — she says, "Palateful, update step 3 — add 2 tablespoons of milk to the dough." Version 3.

**Resolution:** Over the next month, her fork evolves through 5 versions while Leo's original stays untouched. When a friend asks for "that scone recipe," the partner shares her personal book link — the friend sees the gluten-free version with full version history, and can fork it themselves into their own book.

### Journey 4: "The Save" — When Things Go Wrong and Versioning Rescues Dinner

**Opening Scene:** Leo's partner has been iterating on a sourdough pizza dough recipe for weeks. Version 6 was perfect — crispy, airy, the best they'd ever made. But last Tuesday, she tried a new hydration ratio and fermentation time (version 7). The result was dense and gummy. Worse, she can't remember the exact proportions from version 6.

**Rising Action:** She opens the recipe and taps "Version History." There they are — seven snapshots, each with a timestamp and a diff showing what changed. Version 6 is right there: 72% hydration, 24-hour cold ferment, 2.5g yeast. She taps "Restore Version 6." Palateful doesn't delete version 7 — it creates version 8, identical to version 6, so the full history is preserved.

**Climax:** The next Saturday, she follows version 8 (née version 6) exactly. Perfect pizza dough. She says, "Palateful, add a note — version 7's higher hydration doesn't work with this flour brand. Stick with 72%." The note attaches to the recipe, visible in the version timeline. A lesson learned, captured permanently.

**Resolution:** Months later, Leo is looking at the pizza dough recipe and wonders "why did we go back to 72%?" He taps the version history, sees the note on version 7 → 8, and understands instantly. Nothing was lost — not the failed experiment, not the reason for reverting, not the winning formula.

### Journey Requirements Summary

| Journey | Key Features Exercised | Priority |
|---------|----------------------|----------|
| The Great Migration | Bulk import (CSV/URL/OCR), notification-driven review, low-confidence flagging, source attribution | MVP |
| The TikTok Find | Share-to-app import, meal calendar, shopping cart, cooking mode, AI voice notes, hands-free interaction | MVP (import + cooking), Growth (calendar) |
| The Fork | Recipe forking with lineage, personal vs shared books, shared shopping cart, real-time sync, version history | MVP |
| The Save | Version history, restore, diff view, version notes, full history preservation | MVP |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Version Control Applied to Recipe Iteration**
Palateful applies software version control concepts to recipe management — a domain where no consumer app has done this. Auto-snapshots on meaningful edits (debounced, not every keystroke), visual diffs between versions, one-tap restore that creates a new version rather than destroying history. This transforms recipes from static documents into living, evolvable artifacts.

**2. Fork-Based Recipe Collaboration**
Borrowing the open-source fork model: copy a recipe between books while preserving lineage, then evolve independently. This enables a collaboration pattern where household members (or eventually community members) can diverge from a shared base recipe without conflict. Fork creates v1; edits become v2+. The original remains untouched.

**3. Exception-Driven Bulk Import**
Rather than requiring users to babysit imports, Palateful treats bulk migration as an async pipeline: start it, walk away, get notified only for exceptions (dead links, low-confidence OCR, ambiguous parsing). This inverts the typical "import one recipe at a time" pattern and makes the migration from spreadsheets/Notion a one-time, low-effort event.

**4. AI as Cooking-Mode Tool Caller (Not Generator)**
While competitors focus on AI recipe generation, Palateful positions AI as a friction-removing assistant that operates through function calling during active cooking: persisting notes, managing versions, answering ingredient questions, and handling imports — all without requiring the user to stop cooking. The innovation is in the interaction model (hands-free, mid-task, tool-calling), not the AI itself.

### Market Context & Competitive Landscape

- **Paprika, Whisk, Mela** — Static recipe storage with basic import. No versioning, no forking, no AI assistant.
- **Recime** — Strong share-to-app import (the inspiration for Palateful's URL import UX), but no version control, no household collaboration model.
- **Notion/spreadsheets** — Flexible but zero cooking-specific UX. No structured ingredients, no cooking mode, no OCR.
- **ChatGPT/AI recipe generators** — Generate recipes from prompts but don't store, version, or help you cook them.
- **No competitor combines** versioning + forking + household collaboration + AI tool-calling in a cooking context.

### Validation Approach

| Innovation | Validation Method | Success Signal |
|-----------|------------------|----------------|
| Recipe versioning | Founder + partner daily use over 2 months | Users restore a previous version at least once; feel safe making changes |
| Recipe forking | Partner forks and diverges at least 3 recipes | Two independent version histories from the same origin |
| Exception-driven import | Migrate 100 recipes from spreadsheet/Notion | <10% require manual intervention; completed in one session |
| AI cooking assistant | Mid-cook voice interactions during real cooking sessions | Notes/edits persist correctly; user doesn't need to stop cooking |

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Versioning adds complexity users don't want | Invisible by default — history exists but never surfaces unless requested. Zero extra taps for normal usage. |
| Fork lineage becomes confusing at scale | Simple UI: "Forked from [X]" badge. Lineage is one level deep (no fork-of-fork tracking needed initially). |
| Bulk import produces too many low-quality recipes | Confidence scoring with tiered review: high-confidence auto-accepts, medium flags for review, low requires manual editing. |
| AI tool calls fail or persist incorrectly | Eval framework (already designed in EVAL_DESIGN.md) validates tool call reliability before shipping. |

## Mobile App + Web Specific Requirements

### Project-Type Overview

Palateful is a Flutter cross-platform mobile app (iOS priority, Android follow) with a planned web companion. The mobile app is the primary experience for both curation (couch) and cooking (kitchen) modes. The web app serves as a full-featured secondary access point — recipe browsing, meal planning, shopping list management, and cooking mode from a desktop or laptop.

### Platform Requirements

| Platform | Priority | Status | Notes |
|----------|----------|--------|-------|
| iOS | Primary | In development | First App Store target |
| Android | Secondary | Planned | Flutter shared codebase, post-iOS launch |
| Web | Tertiary | Planned | Flutter web build, full feature parity including cooking mode |

**Minimum iOS version:** iOS 16+ (covers ~95% of active devices)
**Minimum Android version:** API 26 / Android 8.0+
**Web:** Modern browsers (Chrome, Safari, Firefox — last 2 versions)

### Offline Mode

Recipes must be accessible offline for cooking mode reliability. Strategy:

- **Local recipe cache** — All recipes in the user's books are cached locally with structured data (ingredients, steps, notes, current version)
- **Offline cooking mode** — Full cooking experience works without network. Timers, step navigation, ingredient strip all function offline.
- **Sync on reconnect** — Changes made offline (notes, version edits) queue and sync when connectivity returns. Conflict resolution: last-write-wins with user notification if a conflict is detected.
- **Import requires network** — OCR, URL import, and AI assistant features require connectivity (acceptable tradeoff).
- **Shopping cart requires network** — Real-time sync is the core value; offline cart defeats the purpose.

### Device Features & Permissions

| Feature | Permission | Usage | Priority |
|---------|-----------|-------|----------|
| Camera | Camera access | OCR recipe import (snap photo) | MVP |
| Share sheet | Share extension | Receive URLs from other apps (TikTok, Safari, Instagram) for recipe import | MVP |
| Microphone | Microphone access | Voice input for AI assistant during cooking mode | MVP |
| Haptics | None required | Timer completion feedback, cooking mode step transitions | Growth |
| Notifications | Push notification | Import status, partner actions, meal reminders, shopping updates | MVP |
| Home screen widgets | WidgetKit (iOS) / App Widgets (Android) | Active timer display, next planned meal, quick recipe access | Growth |

### Push Notification Strategy

| Notification Type | Trigger | Priority |
|------------------|---------|----------|
| Import complete | Bulk import or OCR job finishes | MVP |
| Import needs attention | Low-confidence or failed import items | MVP |
| Recipe book shared | Partner/friend shares a book with you | MVP |
| Shopping list updated | Partner adds/checks off items | Growth |
| Recipe added to shared book | New recipe in a shared book | Growth |
| Meal plan reminder | Upcoming meal event (configurable timing) | Growth |
| Cooking timer | Timer completion (critical — must work in background) | MVP |
| Prep reminder | "Start marinating 4 hours before dinner" | Vision |

**Notification principles:** Opt-in per category. Never spammy. Partner actions are batched (not every single item check-off). Timer notifications are critical-priority and must break through Do Not Disturb.

### Widget Strategy (Growth)

| Widget | Size | Content |
|--------|------|---------|
| Active Timer | Small | Countdown timer with recipe name, tap to open cooking mode |
| Next Meal | Medium | Next planned meal from calendar with recipe photo, prep time, tap to start cooking |
| Quick Access | Large | 3-4 recent/favorite recipes with photos, tap to open |

### App Store Compliance

- **Content policy:** User-generated recipes only — no copyrighted cookbook content. Import from URLs respects fair use (ingredient lists are facts, not copyrightable; instructions are paraphrased by AI extraction).
- **AI disclosure:** App Store requires disclosure of AI features. Palateful uses AI for recipe extraction, assistant tool-calling, and search — not for generating misleading content.
- **Subscription model:** Free tier for personal use (TBD). No paywall for core features during friends-and-family phase.
- **Privacy:** No tracking, no ads, no selling user data. Privacy nutrition label will be clean. Auth0 handles authentication; recipe data stays in user's account.
- **Review risks:** Share extension and background notifications are standard Flutter patterns. No known rejection risks.

### Web Platform Considerations

- **Not a full rebuild** — Flutter web build from same codebase. Responsive layout adjustments, not a separate app.
- **Full feature parity for cooking:** Cooking mode, OCR import (webcam or file upload), and voice AI all available on web. Laptop-on-the-counter is a valid cooking setup.
- **Focus areas for web:** Recipe browsing, meal planning calendar (better on larger screen), shopping list management, recipe sharing links, cooking mode.
- **OCR on web:** File upload for recipe photos (drag-and-drop or file picker). Webcam capture as secondary option.
- **Voice AI on web:** Browser microphone API for hands-free assistant interaction during cooking.
- **SEO:** Public recipe books (Vision phase) will benefit from web presence. Server-side rendering considerations for public pages only.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-solving MVP — replace the spreadsheet as Leo's single source of truth, then expand to household use.

**Resource:** Solo developer (Leo) with AI-assisted development. No team scaling needed for MVP.

**Key insight:** This is a brownfield project with working (but incomplete) infrastructure. The MVP isn't about building from scratch — it's about closing gaps in the existing system and making the core loop reliable enough to trust.

### Blocker Chain (Critical Path)

```
Spreadsheet import → Personal adoption → OCR stability → Frictionless new adds
    → Shopping cart → Partner adoption → UI polish → Stickiness → App Store
```

### MVP Feature Set (Phase 1) — "Replace the Spreadsheet"

**Core User Journeys Supported:**
- Journey 1: The Great Migration (bulk import)
- Journey 2: The TikTok Find (URL import → cook)
- Journey 4: The Save (versioning rescues dinner)

**Must-Have Capabilities:**

| Feature | Status | Gap |
|---------|--------|-----|
| Recipe CRUD with structured ingredients/steps | Functional | UI polish needed |
| Recipe books (personal + shared) | Functional | — |
| Bulk import from spreadsheet/Notion (CSV/URL list) | Not built | **Primary blocker** — new feature needed |
| URL recipe import (JSON-LD + AI fallback) | Partially built | Needs reliability hardening |
| OCR recipe import (photo → recipe) | In progress | **HunyuanOCR resource issues on AWS Batch** |
| Recipe versioning (auto-snapshot, history, restore) | Designed | Implementation needed |
| AI assistant with tool calling | Partially built | Needs stability + eval coverage |
| Cooking mode (step nav, ingredient strip, timers) | Functional | UI/UX improvements needed |
| Ingredient search (exact + fuzzy + semantic) | Designed/partial | pgvector + pg_trgm infrastructure exists |
| Auth0 authentication (Google + Apple) | Functional | — |
| Invitation system for sharing books | Designed | Implementation needed |
| Share sheet extension (iOS) | Not built | Critical for "TikTok Find" journey |

**MVP exit criteria:** Leo has migrated 100 recipes from spreadsheet/Notion, can import new recipes via URL/OCR reliably, and cooks from the app 2x/week for 2 consecutive weeks.

### Phase 2 — "Household Mode" (Post-MVP)

**Core Journey Supported:** Journey 3: The Fork

| Feature | Dependency |
|---------|-----------|
| Shared real-time shopping cart (WebSocket sync) | Unblocks partner adoption |
| Recipe forking between books with lineage | Versioning must be stable first |
| Push notifications (import status, partner actions, timers) | — |
| UI/UX overhaul — sticky, polished, delightful | Informed by MVP usage patterns |
| Meal planning calendar | — |
| Cooking log and history | — |

**Phase 2 exit criteria:** Partner independently uses the app weekly. Both use the shared shopping cart for grocery runs.

### Phase 3 — "Share With the World" (Expansion)

| Feature | Notes |
|---------|-------|
| App Store publication (iOS) | After UI polish and stability confidence |
| Android build | Flutter shared codebase, minimal additional work |
| Web build (Flutter web) | Full cooking mode support, laptop-on-counter use case |
| Home screen widgets (timers, next meal, quick access) | Growth engagement feature |
| Export to PDF/printable recipe cards | Data sovereignty promise |
| Ingredient scraper service (USDA/OpenFoodFacts) | 5,000+ ingredient database |
| Haptic feedback in cooking mode | Polish feature |

### Phase 4 — "Community" (Vision)

| Feature | Notes |
|---------|-------|
| Public recipe books and community discovery | Three-tier model completes |
| Social features (friends, profiles, sharing) | — |
| AI suggestion agent (proactive meal ideas) | Based on pantry, calendar, preferences |
| Voice control in cooking mode | "Next step", "set timer 10 minutes" |
| Pantry tracking system | Hard to keep updated — needs low-friction UX |
| Smart substitution suggestions | Mid-cook AI feature |

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Impact | Mitigation |
|------|--------|-----------|
| HunyuanOCR resource issues on AWS Batch | Blocks OCR import pipeline | Profile memory/GPU requirements, right-size Batch compute environment. Fallback: use OpenAI Vision API as interim OCR until Batch is stable. |
| Bulk import quality varies wildly | Low-confidence imports create cleanup burden | Confidence scoring with tiered review. High auto-accepts, medium flags, low requires manual. Set expectations: 90% auto, 10% manual. |
| Recipe versioning complexity | Could add hidden bugs or data corruption | Start simple: full-snapshot versioning (not diffs). Storage is cheap. Optimize later if needed. |
| Offline sync conflicts | Partner edits same recipe simultaneously | Last-write-wins with notification. Rare for recipe data — not a real-time collab doc. |

**Market Risks:**

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Only Leo uses it | No validation of household value prop | Partner adoption is Phase 2 gate. If partner doesn't adopt, reassess shared features before Phase 3. |
| Friends/family don't find it useful | App Store launch is premature | Don't optimize for external users until household adoption is proven. |

**Resource Risks:**

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Solo dev bandwidth | Features take longer than hoped | Strict phase gates. Don't start Phase 2 until Phase 1 exit criteria met. AI-assisted development accelerates velocity. |
| AWS costs creep up | Monthly budget exceeds $50 | Cost monitoring from day one (COST.md already analyzed). Batch jobs are the biggest variable — right-size aggressively. |

## Functional Requirements

### Recipe Management

- **FR1:** Users can create recipes with structured fields (title, description, ingredients with quantities/units, ordered steps, prep time, cook time, servings, source attribution, tags)
- **FR2:** Users can edit any recipe they own, with changes auto-creating a version snapshot when edits modify ingredients, steps, or title (debounced, not every keystroke)
- **FR3:** Users can view the full version history of any recipe they have access to, including timestamps and diffs between versions
- **FR4:** Users can restore any previous version of a recipe, which creates a new version (never destroys history)
- **FR5:** Users can annotate recipes with notes that attach to the current version and persist in the version timeline
- **FR6:** Users can archive recipes they own, removing them from active views while preserving all data, version history, and fork lineage references
- **FR7:** Users can favorite/star recipes for quick access
- **FR8:** Users can attach photos to recipes (hero image, step-by-step photos)
- **FR9:** Users can restore archived recipes back to active status at any time

### Recipe Books & Organization

- **FR10:** Users can create personal recipe books (private, visible only to owner)
- **FR11:** Users can create shared recipe books with role-based access (owner, editor, viewer)
- **FR12:** Users can fork a recipe from any book they have access to into their own personal book, with lineage tracked (source recipe and book recorded)
- **FR13:** The system preserves fork lineage references even when the source recipe is archived or the user loses access to the source book
- **FR14:** Users can move or copy recipes between their own books
- **FR15:** Users can invite other users to shared recipe books with configurable permissions
- **FR16:** Users can browse and search within a specific recipe book
- **FR17:** Users can perform bulk operations on recipes (bulk tag, bulk move between books, bulk archive)
- **FR18:** Users can archive recipe books, removing them from active views while preserving all contained recipes and their data

### Recipe Import

- **FR19:** Users can import recipes by providing a URL, with the system extracting structured recipe data automatically
- **FR20:** Users can import recipes by photographing physical recipes (OCR pipeline extracts structured data)
- **FR21:** Users can bulk import recipes from a CSV or URL list, with the process running asynchronously and notifying the user only when intervention is needed
- **FR22:** Users can review and correct low-confidence imports before they are finalized
- **FR23:** Users can import recipes via the iOS/Android share sheet from any app (TikTok, Safari, Instagram, etc.)
- **FR24:** The system preserves source attribution for all imported recipes (original URL, photo, or source reference)

### Cooking Mode

- **FR25:** Users can enter a hands-free cooking mode for any recipe, with large text, step-by-step navigation, and an ingredient reference strip
- **FR26:** Users can set and manage multiple concurrent timers during cooking, with background notifications on completion
- **FR27:** Users can navigate between steps using touch gestures suitable for messy hands (swipe, large tap targets)
- **FR28:** Users can access cooking mode offline with locally cached recipe data
- **FR29:** Users are prompted with a post-cook feedback flow after completing cooking mode (rate how it went, add notes, log the cook)

### AI Assistant

- **FR30:** Users can interact with an AI assistant via text or voice that performs actions through tool calling (not just chat)
- **FR31:** The AI assistant can search the user's recipe collection and return relevant results
- **FR32:** The AI assistant can add notes to recipes on the user's behalf ("make a note to try extra sugar")
- **FR33:** The AI assistant can provide recipe suggestions based on user queries
- **FR34:** The AI assistant can answer questions about a recipe's ingredients, steps, or history during cooking mode
- **FR35:** The AI assistant is available hands-free in cooking mode via voice input

### Search & Discovery

- **FR36:** Users can search their recipe collection by recipe name, ingredient, tag, or free text
- **FR37:** The system supports exact match, fuzzy match, and semantic search across recipe content
- **FR38:** Users can filter search results by recipe book, tags, prep time, and other structured fields
- **FR39:** Users see a home screen with contextual recipe suggestions (recent, favorites, planned meals) without needing to search
- **FR40:** Archived recipes are excluded from default search and browsing but can be found via an explicit archive view

### Household Collaboration

- **FR41:** Users can share recipe books with household members where both parties have full citizen access (not owner + guest)
- **FR42:** Users can see real-time updates when a shared book member adds, edits, or forks recipes
- **FR43:** Users can manage a shared real-time shopping list with household members, with items syncing in real-time
- **FR44:** Users can add recipe ingredients to the shared shopping list with one action
- **FR45:** Users can check off shopping list items, with changes visible to all members in real-time

### Meal Planning

- **FR46:** Users can schedule recipes to a shared meal planning calendar
- **FR47:** Users can view upcoming planned meals and navigate to the recipe from the calendar
- **FR48:** Users can add all ingredients from a planned meal to the shopping list
- **FR49:** Users can generate an aggregate shopping list from multiple planned meals across a date range

### Authentication & Identity

- **FR50:** Users can sign in via Google or Apple accounts
- **FR51:** Users can manage their profile (display name, preferences)
- **FR52:** Users can accept or decline invitations to shared recipe books

### Notifications

- **FR53:** Users receive push notifications for async events (import complete, import needs attention, book shared, timer complete)
- **FR54:** Users can configure notification preferences per category (opt-in/opt-out)

### Data Ownership & Export

- **FR55:** Users can export their entire recipe collection at any time (JSON format minimum, PDF/printable as growth feature)
- **FR56:** The system never alters, removes, or restricts access to a user's recipe data

### Onboarding

- **FR57:** First-time users experience an onboarding flow that introduces recipe import, recipe books, and cooking mode, and prompts them to complete their first action (import recipes, create a recipe, or explore)
- **FR58:** The system handles empty states gracefully with contextual prompts (empty book → "Add your first recipe", empty cart → "Plan a meal to get started")

### Sharing & External Access

- **FR59:** Users can share a recipe or recipe book via a public link accessible to people without a Palateful account
- **FR60:** Users can share recipe content via native platform sharing (text, email, messaging apps)

### Cross-Platform

- **FR61:** Users can access all core features (including cooking mode, OCR via file upload, and voice AI) through a web browser with responsive layout

## Non-Functional Requirements

### Performance

- **NFR1:** Core user actions (recipe load, book browsing, search results) complete within 2 seconds at P95 under normal load
- **NFR2:** AI assistant responses begin streaming within 2 seconds of user input at P95
- **NFR3:** Shopping list updates propagate to all connected household members within 1 second
- **NFR4:** Cooking mode transitions (step navigation, timer actions) respond within 200ms at P95, including offline
- **NFR5:** OCR import jobs complete within 60 seconds from image upload to structured recipe output, per recipe image
- **NFR6:** Bulk import processes at minimum 10 recipes per minute for URL-based imports

### Security

- **NFR7:** All data encrypted in transit (TLS 1.2+) and at rest (AES-256 for database, S3)
- **NFR8:** Authentication handled via identity provider with token-based sessions; no plaintext credentials stored
- **NFR9:** Users can only access recipes and books they own or have been explicitly invited to
- **NFR10:** API endpoints enforce authorization checks on every request — no data leakage between users
- **NFR11:** AI assistant tool calls execute with the same permission model as direct user actions (no privilege escalation)

### Reliability & Data Integrity

- **NFR12:** Zero recipe data corruption — the system never silently alters, truncates, or loses recipe content
- **NFR13:** Data recoverable within 4 hours from automated backups in a disaster scenario
- **NFR14:** Database backups run daily with 30-day retention minimum
- **NFR15:** Archive operations are soft deletes — no user data is ever physically removed from the database
- **NFR16:** Version history is append-only — past versions cannot be modified or deleted, only new versions created
- **NFR17:** System gracefully degrades when external services are unavailable (AI features degrade to offline mode, OCR queues for retry, core recipe CRUD continues working)

### Scalability

- **NFR18:** System supports up to 50 concurrent users without performance degradation (friends-and-family scale)
- **NFR19:** Architecture does not preclude scaling to 10,000+ users without fundamental redesign
- **NFR20:** Individual recipe collections support up to 5,000 recipes per user without search or browsing performance degradation
- **NFR21:** Shopping list real-time sync supports up to 5 concurrent editors per list

### Accessibility

- **NFR22:** Cooking mode uses minimum 18pt font with high-contrast colors, readable in bright kitchen lighting
- **NFR23:** All interactive elements in cooking mode have minimum 48x48dp touch targets (messy hands / elbow navigation)
- **NFR24:** Voice input provides audio or haptic confirmation so users know their command was received without looking at the screen

### Integration

- **NFR25:** AI capabilities are provider-agnostic — the system supports swapping between AI providers (Claude, OpenAI, etc.) without changes to user-facing features or data models
- **NFR26:** Identity provider integration supports adding new sign-in methods without application changes
- **NFR27:** OCR pipeline supports swapping processing backends (HunyuanOCR, cloud vision APIs) without changing the import user experience
- **NFR28:** Recipe import supports extensible scraper architecture — adding support for new recipe sites requires only a new scraper module, not system changes

### Cost

- **NFR29:** Monthly infrastructure costs remain under $50 for personal/friends-and-family usage tier (≤50 users)
- **NFR30:** AI API costs are monitored and capped per user to prevent runaway spending
- **NFR31:** OCR batch jobs use spot/on-demand Batch compute sized to minimize idle cost

---

## Addendum — 2026-04-16 — Dogfood Bug Punch List (BUGS.md NEW section)

Source: `BUGS.md` lines 1–20 ("NEW" section, OLD section explicitly skipped). These are items Leo hit while using the dogfood build. Already-landed items (ErrorLog table, admin dashboard, basic activity feed read endpoints, meal_event recurrence columns) are audited and excluded from this addendum — only gaps between shipped-code and dogfood-feel are specified below.

### Scope

Three focused epics:
1. **Calendar Meal UX** — make the calendar an action surface, not a read-only grid.
2. **Activity Hub Polish** — finish what Epic 13 started; the feed is wired but the user experience is still broken.
3. **Home & Foundations** — declutter the home header, close the default-shopping-list onboarding gap, and ship the admin-promotion script that's been blocking Leo from using his own admin dashboard.

### New Functional Requirements

- **FR62:** Tapping a meal on the calendar opens a meal detail view that exposes all meal actions (view recipe, reschedule, unschedule, mark as cooked) without forcing a navigation to the recipe page.
- **FR63:** When a user taps a calendar day (not a specific meal), they see a day-level view listing all meals planned for that day with the same actions.
- **FR64:** Planning a meal surfaces a recipe autocomplete that searches the user's recipes as they type; selecting a recipe attaches it to the meal event. Free-text entry remains supported as a fallback but is de-emphasized.
- **FR65:** The plan-meal sheet exposes a recurrence control with at minimum: None / Daily / Weekly / Monthly options and an end-date picker. The backend columns (`is_recurring`, `recurrence_rule`, `recurrence_end_date`) already exist; this is UI surfacing plus write-through.
- **FR66:** Every user has a default shopping list from the moment their account exists. On account creation / onboarding completion the system auto-creates a shopping list named "Shopping List" and sets it as the default. For existing users who are missing a default (or any shopping list), a backfill runs idempotently on next sign-in.
- **FR67:** The home screen no longer displays the AI assistant chat entry point. The AI assistant remains reachable from a secondary surface (Profile tab or overflow menu) but is not advertised from the main scrolling surface.
- **FR68:** Sort options and Filter options on the home screen are consolidated into a single top-row icon (filter funnel) that opens a bottom sheet containing both sections. The separate row of sort chips is removed.
- **FR69:** Activity items (both background-job activities and import activities) that the user has seen stay marked as read across navigations, app backgrounds, and app restarts. The current persistent-unread behavior is a bug.
- **FR70:** The import activity detail view exposes all fields the backend already returns — currently only a subset renders. At minimum: error message, stage, last retry timestamp, and source link are visible when present.
- **FR71:** The "In Progress" / import history list inside the Add Recipe screen is removed; its responsibilities move into the Activity Hub. The Add Recipe screen links to the Activity Hub for pipeline state.
- **FR72:** An operator script exists to promote a user to admin by email address, runnable against the prod database via the deploy toolchain. The script is idempotent and logs the before/after `is_admin` state.

### New Non-Functional Requirements

- **NFR32:** Onboarding default-creation (recipe book + shopping list) completes in a single transaction — either both land or neither does. Partial state is not acceptable.
- **NFR33:** Recipe autocomplete in the plan-meal sheet returns results within 300ms at P95 for collections up to 5,000 recipes (reusing existing search infrastructure from Epic 5).
- **NFR34:** Activity read-state writes are fire-and-forget from the client's perspective — the UI optimistically marks items read and reconciles with the server async. A failed server write does not re-surface a notification as unread.
- **NFR35:** The admin-promote script is defensive: it refuses to run without a target email, prints a dry-run of the change, and requires confirmation (or an explicit `--yes` flag for automation).

### Explicitly Out of Scope for This Addendum

- The "Maybe we should make our own error tracing in the database" item (BUGS.md line 13): the `ErrorLog` table and admin errors view already ship. The item is considered satisfied.
- BUGS.md OLD section (lines 22–31): superseded or obsolete per the user's `skip the old` directive.
- Rebuilding the AI assistant as anything new — the MCP server path is the strategic direction and this addendum only hides the in-app chat, it does not expand or redesign it.
- Calendar recurrence series management (editing "this and future", split-series semantics). Initial recurrence creation only; power-user edits defer to a later epic.


---

## Addendum — 2026-04-17 — Recurring Meal Plans (slot-based)

### Context

Leo replans the same meals weekly (Pizza Friday, Meatless Monday, weekday-breakfast smoothies, Sunday family dinner). The calendar today forces him to retype every occurrence. The deferred `bugs-cal-3` story proposed iCalendar RRULE at a `meal_event` timestamp — that path is explicitly replaced by this addendum. Recurrence here is **slot-based** ("Every Monday lunch"), not time-based. A new `meal_recurrence_rules` table owns the rule; `meal_events` rows are materialized from it and can be individually overridden, consistent with the GCal-style "This / This and following / All" edit semantics users expect.

Locked decisions from the 2026-04-17 planning intake (confirmed with user):

- **Rule grammar**: weekly-by-weekday-chips + biweekly + monthly-nth-weekday (e.g., "first Saturday dinner"). No count-based ends.
- **Edit scope**: Google-Calendar-style prompt — **This occurrence / This and following / All occurrences**.
- **Slot collision**: manual meals and rule occurrences **stack**. No prompt, no hide. Mirrors current multi-meal-per-slot permissiveness.
- **Rules surface**: both inline (create/edit in `plan_meal_sheet`, edit from meal detail sheet) **and** a dedicated "Recurring plans" screen under Profile/Settings.

### New Functional Requirements

- **FR73:** A recurring meal plan is defined by a **rule**, not a timestamp. The rule captures: meal slot (breakfast/lunch/dinner/snack), day-of-week selection (one or more weekdays), interval (every 1 or 2 weeks), optional "nth weekday of month" mode (e.g., "first Saturday"), and an optional end-date. Each rule has an `owner_id` (the original creator) and an `is_shared` flag. **Shared rules are co-editable by any household member of the owner** — any household partner can read, update, split, and delete a shared rule, and `owner_id` is preserved across co-edits (edits do not transfer ownership). Private rules (`is_shared == false`) are owner-only for every mutation. Shared-rule occurrences remain visible and schedulable per existing `meal_event.is_shared` semantics.
- **FR74:** A rule may be attached to one recipe (preferred) or captured as free-text (e.g., "Leftovers"). Recipe attachment reuses the same autocomplete UX as one-off planning (FR64).
- **FR75:** Rule occurrences are **materialized as concrete `meal_events` rows** linked back to the rule via a `recurrence_rule_id` FK. Materialization covers a rolling window (default: the current week plus 8 weeks forward). Materialization is re-run (a) on rule create/edit, (b) on list reads that cross the current window boundary, and (c) by a nightly job that extends the window and archives stale unused occurrences. Users always see concrete `meal_event` rows on the calendar — there is no virtual / rule-only display path.
- **FR76:** The plan-meal sheet (both quick-add and edit-from-recipe) exposes a **"Repeats"** control. Default: **Never**. Selecting a repeat option reveals a day-of-week chip row (Mon–Sun, multi-select) and an interval toggle (Weekly / Every other week / Monthly on nth weekday). An end-date picker is optional; omission means "forever." Presets **Weekdays** (Mon–Fri) and **Weekends** (Sat–Sun) are one-tap chips.
- **FR77:** Tapping a recurring occurrence on the calendar shows the existing meal detail sheet with an additional **"Recurring"** badge and a summary row ("Every Monday dinner · Pizza"). The sheet's edit/unschedule/reschedule actions prompt "**This occurrence / This and following / All occurrences**" before committing any destructive or series-affecting change. Non-destructive reads (Open Recipe, Mark as Cooked on one occurrence) do not prompt.
- **FR78:** Single-occurrence overrides (from "This occurrence only") are stored on the concrete `meal_event` row as a detached copy — the row loses its `recurrence_rule_id` link and behaves as a one-off thereafter. The rule continues to materialize the next scheduled occurrence as normal.
- **FR79:** "This and following" splits the rule: the original rule receives an end-date set to the day before the chosen occurrence; a new rule is created starting from the chosen occurrence with the new values. Future occurrences past the split point are materialized from the new rule.
- **FR80:** "All occurrences" edits the rule in place. Already-materialized future occurrences are regenerated (replaced) to reflect the new rule. Past occurrences are never touched, regardless of edit scope.
- **FR81:** A new **Recurring Plans** screen under Profile/Settings lists all the current user's rules (one row per rule: summary line, next-occurrence date, active/ended badge). Tapping a rule opens the same edit flow as tapping a recurring occurrence (with the "All occurrences" branch pre-selected — the per-occurrence branches are irrelevant from this surface). The screen exposes one-tap **End Series Today** (same as deleting the rule's future materializations while keeping the past).
- **FR82:** Deleting a rule via **End Series Today** from any entry point (manage screen or "All occurrences" in the meal detail sheet) archives the rule and deletes all future materialized occurrences. Past occurrences remain for history/analytics. "This occurrence only" deletion leaves the rule intact and deletes only the chosen `meal_event` row (existing `DeleteMealEvent` path, with the rule's next materialization filling the slot as normal).
- **FR83:** Weekly shopping-list aggregation (`PopulateFromCalendarRange`) continues to operate on concrete `meal_event` rows and therefore picks up rule-materialized occurrences automatically without endpoint changes. The existing integration remains correct as long as materialization covers the requested week.
- **FR84:** Manual meal plans and rule-generated occurrences on the same slot/day **coexist** — no prompt, no hide, no dedupe. Users who want exclusivity must delete the manual or override the rule occurrence themselves. This matches the current calendar's existing multi-meal-per-slot permissiveness.

### New Non-Functional Requirements

- **NFR36:** Materialization of a new rule completes within 500ms at P95 for a 9-week window on a typical weekday-selection rule (up to ~45 occurrences). Rules are validated and materialization runs in a single transaction; partial state is not acceptable.
- **NFR37:** `ListMealEvents` P95 latency stays within 20% of its current baseline after the rolling-window materialization check is added. The check is a bounded `SELECT` over `meal_recurrence_rules WHERE max_materialized_through < requested_end_date`; expansion is deferred to a job path if hot-path latency is threatened.
- **NFR38:** The rule-edit flow's "All occurrences" regeneration path is idempotent and safe to retry — concurrent edits from different devices converge on the server-state rule, with the most recent `updated_at` winning.
- **NFR39:** The Recurring Plans list loads within 200ms at P95 for a user with up to 50 rules, reusing the same caching layer as the recipes/books lists.

### Explicitly Out of Scope for This Addendum

- Arbitrary RRULE recurrence shapes (e.g., "every 3rd Thursday of odd months") — not worth modeling.
- Count-based end conditions ("for 10 occurrences"). "Until date" and "forever" cover the vast majority of real usage.
- Cross-slot rules ("rotating breakfast / lunch"). A user who wants both creates two rules.
- Per-occurrence participant invites that differ from the rule's default participant set. Invites on a rule-materialized occurrence follow the rule's default; the user may re-invite individually on the concrete occurrence via the existing `InviteParticipant` path.
- Yearly recurrence ("Thanksgiving turkey"). Manual entry covers this.
- Back-filling past occurrences — materialization is forward-only from rule creation.
- Removing legacy `is_recurring` / `recurrence_rule` / `recurrence_end_date` columns on `meal_events`. They remain as dead fields for backward compatibility with any legacy clients (to be cleaned up after this epic ships and stabilizes).


---

## Addendum — 2026-04-17 — Import Bug Punch List (BUGS.md NEW lines 5–7)

### Context

Three import-flow bugs surfaced during dogfood. Source: `BUGS.md` lines 5–7. The user batched questions confirmed scope (locked decisions in the parenthetical of each FR below):

1. **Review Import lost ingredient detail.** Commit `4f0de4c fix(extractor): stop duplicating quantity+unit in ingredient text` correctly stripped duplicated tokens from the `text` field and split them into separate `quantity` / `unit` / `name` / `notes` fields, but the Flutter Import Review screen still binds only `text`. Quantity, unit, and notes are silently invisible. The recipe-create wizard has the same gap: a single text field for ingredient input, no structured editing anywhere in the app.
2. **No source-image preservation.** When a photo import finalizes into a Recipe, the original parser-input photo is forgotten. The recipe ends up with `image_url` set only if the AI extractor happened to provide one (rare for photo imports). URL imports work today (the extractor populates `image_url` from JSON-LD or AI). The user's chosen approach: when no other hero is set, promote the user-uploaded source photo to the recipe's hero image.
3. **One photo, one recipe.** HunyuanOCR receives a generic OCR prompt and `parser_batch_completion` always creates one ImportItem per `group_index`, baking in a "1 photo → 1 recipe" assumption. A common cookbook page has two recipes (or facing pages cover one recipe each in a single photo). The user's chosen approach: auto-detect server-side, fan out to N ImportItems, and the existing exception-review queue handles N cards naturally.

### Locked Decisions (from 2026-04-17 user batch)

- **Bug 1 scope:** structured ingredient editor (qty + unit dropdown + name + notes) lands in **both** the Review Import screen **and** the recipe create/edit wizard. One shared widget, two consumers.
- **Bug 2 strategy:** auto-promote the user-uploaded photo-import source to the recipe's hero image when no other hero is set. URL imports already work and are out of scope. No "Snap Picture" prompt, no per-ingredient OCR-bbox crops, no og:image scraping.
- **Bug 3 strategy:** auto-detect via extractor prompt update, fan out N ImportItems server-side. User sees N cards in the existing exception-review queue. No manual split UI in v1; if the model under- or over-splits, the user edits the cards individually (and a follow-up may add merge/split affordances if it becomes painful).
- **Unit catalog (sensible default, not asked):** curated short list of common units (cup, tbsp, tsp, oz, fl oz, ml, l, g, kg, lb, each, pinch, dash, clove, slice) with free-text fallback. No US/metric profile toggle in v1.

### New Functional Requirements

- **FR85:** The Import Review screen renders each parsed ingredient as a structured row exposing four editable fields: **quantity** (numeric input, accepts decimals and common fractions like `1/2`), **unit** (dropdown of common units with free-text fallback), **name** (text), **notes** (text, prep/state qualifiers like "melted", "diced"). The `is_optional` flag is exposed as a checkbox/toggle. The single-text-field rendering is removed. Saving an item from the review screen sends the structured shape to `user_edits.ingredients`; the API and `create_recipe_task` already understand it.
- **FR86:** The recipe create/edit wizard uses the same structured-ingredient row component as Review Import. Existing recipes whose ingredients lack `quantity` / `unit` / `notes` (legacy or AI-pre-`4f0de4c`) render with empty structured fields — the user can fill them in or leave them blank; nothing is lost. The recipe detail screen continues to render display-formatted ingredient lines (this story does not redesign read-only display, only the edit experience).
- **FR87:** When a photo-source import finalizes into a Recipe and the resulting recipe has no `image_url` set by the extractor, the system copies the user-uploaded source image from the parser-inputs S3 prefix to a permanent recipe-images S3 location and writes that URL to `recipe.image_url`. The promotion happens once, in `create_recipe_task` (or its wrapper), inside the same transaction that creates the recipe. URL imports are unaffected — the extractor-supplied `image_url` (typically scraped JSON-LD or AI-extracted) wins. If the user later attaches their own hero photo via the existing photo-attachment flow, that overrides the auto-promoted one.
- **FR88:** A single photo containing two or more recipes is detected by the extractor and produces N `ImportItem` rows from one `ParserJob` group. Detection is the extractor's responsibility: the prompt is updated to instruct the model to emit a JSON array of recipes when distinct recipes are present in the OCR text, and `parser_batch_completion._handle_success` fans out one ImportItem per array element (preserving the source-photo S3 key on every item so FR87 still works for each child). The exception-review queue surfaces the N cards independently — no new screen, no batch-of-batch UX. Single-recipe images continue to produce exactly one ImportItem (array of length one is normalized to today's behavior).

### New Non-Functional Requirements

- **NFR40:** The structured ingredient row UI renders without layout jank for recipes with up to 50 ingredients on the smallest supported screen size (iPhone SE 1st-gen width). Unit dropdown opens within 100ms.
- **NFR41:** Source-photo promotion (FR87) adds no more than 500ms to `create_recipe_task` P95 latency for a typical 1–4MB cookbook photo. Failure to copy (S3 error, missing source key) does not fail recipe creation — it logs a warning and leaves `image_url` null. The recipe is the user's data; the hero is a nice-to-have.
- **NFR42:** Multi-recipe extraction (FR88) does not regress single-recipe extraction quality on the existing eval suite (Story 13.5 fixtures). A new eval fixture set covering ≥3 multi-recipe cookbook pages is added; the extractor must hit ≥80% recipe-count accuracy on that set before this story is marked done.
- **NFR43:** The unit dropdown's curated list is defined in a single Flutter constant (single source of truth) and is not re-translated or re-ordered per screen. New units are added by editing the constant; this is not a backend-driven catalog in v1.

### Explicitly Out of Scope for This Addendum

- **"Snap Picture" prompt at end of import.** Considered, deferred. Auto-promotion of the source photo (FR87) covers the common case; an explicit "take a photo of the finished dish now" prompt is a separate UX decision not made in this round.
- **Per-ingredient OCR bounding-box crops.** Substantial uplift (HunyuanOCR prompt + bbox model output + per-ingredient image storage + new UX). Not a current pain point; revisit only if the user asks again.
- **og:image scraping for URL imports.** URL imports already populate `image_url` via the extractor in practice. If a regression is observed, file separately.
- **Manual "split here" / "merge these" controls in Review Import.** Auto-detect (FR88) is v1; manual rescue for model errors is the user editing the N cards individually. Add merge/split affordances only if dogfood proves auto-detect is unreliable.
- **Backend-served unit catalog with locale/i18n.** The Flutter constant (NFR43) is the v1 source of truth.
- **Replacing the recipe-detail read-only ingredient renderer.** FR86 is edit-side only. The cooking-mode and recipe-detail display pipelines stay as they are.


---

## Addendum — 2026-04-17 — Home/Notification Bug Punch List (BUGS.md lines 2–5)

### Context

Three more dogfood bugs. Source: `BUGS.md` lines 2–5.

1. **Add-image icon still cluttering the home header.** The prior `epic-bugs-home-and-foundations` removed the AI chat button and consolidated sort+filter, but left the multi-photo batch-import shortcut (`Icons.add_photo_alternate_outlined`) at `home_screen.dart:556`. The Photo import flow has a primary, discoverable entry via the Add Recipe sheet → "From Photo". The header shortcut is redundant and not useful.
2. **Notifications have never worked.** Flutter has `firebase_messaging` initialized, FCM token registration hits the backend, and the backend has a full `PushNotificationService` (libraries/utils) with 15 event types and 9+ callsites already wired. Terraform pipes `FIREBASE_CREDENTIALS_JSON` from AWS Secrets Manager into ECS. **What's broken:** iOS `AppDelegate.swift` never calls `registerForRemoteNotifications()`, `Info.plist` has no `UIBackgroundModes=remote-notification`, no APNs auth key has been uploaded to Firebase Console, `.env.example` doesn't mention `FIREBASE_CREDENTIALS_JSON`, send callsites swallow failures silently, and there's zero documentation. The user has never seen a notification fire on their device.
3. **Post-add-recipe nav bounces to home.** After completing an add-recipe flow from anywhere except Photo, the user ends up on the home screen — jarring when they were browsing a book or came in via share-sheet and want to add another. The Photo flow uses `context.pop(true)` (correct). The share-sheet flow does three `context.go('/')` calls (`share_import_screen.dart:216,237,250`). The text/PDF/spreadsheet/audio paths `pushReplacement` to `/recipes/import/review-list/$jobId` — a real mid-funnel review step — and when the user finishes there, they also land on home instead of the originating page.

### Locked Decisions (from 2026-04-17 user batch)

- **Bug 1 scope:** straight deletion. Match the pattern from `bugs-home-1` (AI chat button removal). No analytics, no flags, no replacement.
- **Bug 2 scope: iOS-first, admin test-push only.** Ship the plumbing fixes that let a push arrive on the user's iPhone, verify via an admin-only "Send test push to myself" button in the admin dashboard, and leave real event triggers (import-complete, partner activity) for a follow-up story once the round-trip is proven. Android polish (explicit FCM channel definition, Android UI for permission prompt) is deferred.
- **Bug 2 permission UX:** prompt during onboarding, immediately after sign-in, before the existing "Choose vibes" step. This adds a new onboarding step.
- **Bug 2 dev/local:** `PushNotificationService` is a no-op (log-only) when no `FIREBASE_CREDENTIALS_JSON` is present. Real pushes only fire on deployed ECS tasks. `.env.example` documents the variable as *optional, prod-only*.
- **Bug 2 credentials path:** APNs auth key (`.p8` file pulled from developer.apple.com → Keys), uploaded to Firebase Console → Cloud Messaging. Documented as a one-time ops step.
- **Bug 3 scope:** fix share-sheet `context.go('/')` to pop-with-cold-launch-fallback, AND make the review-list hub's terminal actions (Approve / Dismiss / Close) pop all the way back to the original caller, not to home. Keep the review-list as an intermediate surface — text/PDF/spreadsheet/audio still go through it, since they have a real pending-review action; only the terminal nav is fixed.
- **Audit-log admin actions (carries forward from prior epic):** the admin test-push button writes an audit row via the existing ErrorLog/audit path, same pattern as `promote_admin.py`.

### New Functional Requirements

- **FR89:** The home screen header has no image/photo-batch shortcut icon. The `Icons.add_photo_alternate_outlined` button, the `_pickMultiplePhotos()` handler, the `_showBatchConfirmDialog()` handler, and the `image_picker` import are removed from `home_screen.dart`. The `BatchImportStatusWidget` on the home grid remains — it continues to surface in-flight batch progress for batches started from any entry point. The Add Recipe sheet's "From Photo" entry is the sole discoverable path into the photo-import flow.
- **FR90:** iOS devices receive APNs registration on first app launch after sign-in. `AppDelegate.swift` calls `UIApplication.shared.registerForRemoteNotifications()` and `Messaging.messaging().delegate = self` after Firebase initializes. `Info.plist` declares `UIBackgroundModes` with `remote-notification`. The APNs auth key is uploaded to Firebase Console as a one-time ops procedure documented in `docs/PUSH_NOTIFICATIONS.md`. Once registered, the app obtains an FCM token and registers it with the backend via the existing `RegisterPushToken` endpoint.
- **FR91:** The onboarding flow adds a notification-permission step. After sign-in and before the "Choose vibes" step, the user sees a single-screen prompt that explains why Palateful wants to send notifications (one-line value prop per event type, e.g., "when an import finishes, when a partner edits a shared book"), with two buttons: **Turn On** (invokes `FirebaseMessaging.requestPermission`) and **Not Now** (proceeds without requesting). The user's choice is recorded as `notification_permission_status` on the user model for later analytics/resurfacing. The prompt is never shown again automatically; users who say "Not Now" must enable notifications from Profile → Settings.
- **FR92:** The admin dashboard gains a "Send test push to myself" button under a "Notifications" section. Tapping it calls a new admin-only backend endpoint `POST /api/v1/admin/notifications/test-push` that invokes `PushNotificationService.send_to_user(current_user.id, type=TEST, title="Palateful test push", body="If you see this, pushes work 🍽️")`. The endpoint is gated on `is_admin` and writes an audit row (actor=`admin:test_push`, target=user_id). Response body returns the FCM message-id so the dashboard can display "Sent (msg-id: ...)" on success, or a surfaced error on failure.
- **NFR44:** `PushNotificationService` logs every send attempt — success or failure — at INFO level with the message type, target user_id, and FCM response. Failures (invalid token, FCM 4xx/5xx, quiet-hours suppression, missing credentials) are logged at WARNING or ERROR level with enough context to diagnose without a repro. No silent swallow. Send failures never raise out of the callsite — they're caught, logged, and audit-tagged; the triggering event still succeeds.
- **NFR45:** `PushNotificationService.__init__` detects the absence of `FIREBASE_CREDENTIALS_JSON` / `FIREBASE_CREDENTIALS_PATH` and enters a "log-only" mode that records every would-be send at INFO level without invoking the FCM SDK. The service never raises on missing creds — local dev and CI run unmodified. The mode is logged once at startup so it's discoverable.
- **FR93:** Every "add a new recipe" flow lands the user back on the screen they launched from after the add (or its first pending user action) completes. Specifically:
  - `share_import_screen.dart` replaces `context.go('/')` at lines 216, 237, 250 with `Navigator.canPop(context) ? context.pop() : context.go('/')` — the home fallback only fires on cold-launch (no nav stack).
  - The review-list screen's terminal actions (Approve-all, Dismiss-all, Close) use a `popUntil` variant so the user is returned to the originating screen (home, recipe book detail, etc.) rather than to `/`. The originating route is captured at push time and matched in `popUntil`.
  - The Photo flow (`context.pop(true)` at `photo_capture_screen.dart:381`) and the recipe-book-detail flow (push → pop → reload) are kept as-is — they're the exemplar.
- **NFR46:** The post-create nav fix is verified via integration tests for each entry point: home → add-recipe → assert still on home; recipe-book-detail → add-recipe → assert still on book detail and book reloaded; share-sheet (warm launch) → approve → assert still on origin; share-sheet (cold launch) → approve → assert on home (fallback path).

### Explicitly Out of Scope for This Addendum

- **Android push polish.** No explicit FCM channel definition in Flutter, no Android-specific permission-prompt copy variations. Android gets whatever the default `firebase_messaging` plugin provides. Follow-up story if/when Android dogfooding starts.
- **Real event push triggers.** Turning on import-complete / partner-activity / shopping-list-added pushes is deliberately NOT part of this epic. Those callsites already exist in code; they are gated by the service running for real. Once FR90+FR92 prove the round-trip works on device, a later story flips on the event firehose and does per-event copy/deep-link tuning. The goal of this epic is "a push arrives on the user's phone," not "the full notification experience."
- **Notification center / inbox inside the app.** System push only. An in-app notification feed is a separate product decision.
- **Quiet-hours UI and per-event preferences UI.** The backend supports quiet hours and per-event preferences already. Surfacing them to the user as a settings screen is out of scope here.
- **Rich / actionable notifications.** Plain title + body + deep-link payload only. The existing tap-to-route handler in `push_notification_service.dart:178-244` is sufficient. Interactive actions (e.g., "Mark cooked" from the notification) belong in the `ios-1-notification-actions` epic.
- **A centralized `RecipeCreationNavigator` helper.** Considered, deferred. The current plan touches two concrete callsites — share-sheet (3 lines) and review-list terminal (1 helper). A shared navigator abstraction isn't justified for that surface area. Revisit if a future entry point introduces a fourth post-create behavior.

---

## Addendum — 2026-04-17 — Calendar Management & Sharing (multiple switchable calendars, full co-edit)

### Context

Today the meal calendar is implicit: every `meal_event` is owner-scoped, and sharing happens one meal at a time via `meal_event_participants` (host/cohost/guest). There is no container that groups events, no way to keep a personal calendar and a shared-with-partner calendar side by side, and no way to give a partner blanket edit rights across an entire calendar without inviting them to each meal.

This addendum introduces **Calendar** as a first-class, shareable container — the missing symmetric concept to `recipe_book`. Every meal_event (and every recurrence rule) belongs to exactly one calendar. Users can own multiple calendars, switch between them on the Calendar tab, and invite others with full edit/add permissions that apply to every meal inside.

Locked decisions from the 2026-04-17 planning intake (confirmed with user):

- **Roles**: `owner` and `editor` only. No viewer tier. Editors get full create/edit/delete on every meal and recurrence rule in the calendar. Symmetric co-ownership is the point; role asymmetry isn't the user's ask.
- **View shape**: **Switcher**, not overlay. The Calendar tab shows one active calendar at a time with a header picker to swap. No Google-Calendar-style color-coded stacking.
- **Default per-user calendar**: every existing user gets one auto-created calendar named "My Calendar" at migration time, and every existing `meal_event` + `meal_recurrence_rule` is backfilled into it. New sign-ups get the same default calendar as part of the user-provisioning flow.
- **Shopping-list auto-populate source**: `shopping_lists.auto_populate_from_calendar` continues to pull from every calendar the user has access to (union across owned + editor-access calendars). No new picker, no per-list calendar scoping.
- **Invitation substrate**: extend the existing invitation system (`docs/INVITATION_SYSTEM.md`) with a new `resource_type = "calendar"`. Reuse direct-invite + invite-link flows verbatim. No new notification category beyond what the existing invitation plumbing already emits.
- **Meal-event-level participants (`host/cohost/guest` on `meal_event_participants`) stay as-is.** Calendar-level membership is a separate, coarser sharing dimension; the two coexist. An editor on the calendar can create meals without being individually invited to each.

### New Functional Requirements

- **FR101:** A **Calendar** is a first-class resource with: `id`, `name`, `description` (optional), `owner_id`, `is_shared` (bool), `is_default` (bool), `color` (optional hex, reserved for future use — no UI in this epic), plus standard timestamps. Every `meal_event` and every `meal_recurrence_rule` belongs to exactly one calendar via a mandatory `calendar_id` FK.
- **FR102:** On first deploy, a migration creates exactly one calendar per existing user named **"My Calendar"** with `is_default = true`, and backfills every existing `meal_event` and `meal_recurrence_rule` with that user's default calendar id. No user action required.
- **FR103:** New sign-ups automatically receive a default calendar named "My Calendar" as part of user provisioning. The default calendar cannot be deleted while it is the user's only remaining calendar; attempting to do so returns `CALENDAR_CANNOT_DELETE_LAST` (error code reserved in the 26x range).
- **FR104:** Users can create additional calendars via a **New Calendar** action from the Calendar tab's switcher. Creation takes a name (required) and an optional description. The creator is the owner. The newly created calendar becomes the active calendar in the switcher.
- **FR105:** Users can rename, describe, and delete any calendar they own via a **Calendar Settings** sheet reachable from the switcher. Deletion is a hard archive: the calendar is soft-deleted (`archived_at` set) and all contained meal_events and recurrence rules are soft-archived with it. Past events remain queryable via direct id lookup; the calendar disappears from the switcher. Deletion requires confirmation; no undo snackbar (destructive bulk, matches recurring-meals "End series today" policy).
- **FR106:** Users can share a calendar with another user by inviting them as an **editor** via the existing invitation system (direct invite by email/username, or shareable invite-link). Accepted invitations add the invitee to `calendar_users` with `role = editor`. The invitee gets full create/edit/delete/reschedule permissions on every meal_event and recurrence rule in the calendar.
- **FR107:** Users can view, change, and remove members of any calendar they own via a **Calendar Members** screen reachable from Calendar Settings. Owner cannot change their own role or remove themselves without transferring ownership to another member (ownership transfer is a distinct action, not a side effect of leave). Editors see the member list but cannot modify membership.
- **FR108:** An editor on a calendar can **leave** the calendar at any time via Calendar Settings (removes their `calendar_users` row). The owner sees a "left calendar" activity entry. The leaver no longer sees the calendar in their switcher.
- **FR109:** The Calendar tab header shows the **currently-active calendar's name** and a **switcher** affordance (chevron / tap area). Tapping opens a bottom sheet listing every calendar the user has access to (owned + editor), grouped into "My Calendars" and "Shared with Me", each with member count and a chevron to a per-calendar settings screen. The active calendar is persisted across app launches (last-active-calendar stored locally).
- **FR110:** All calendar reads and writes enforce authorization: a user can only read/write a meal_event or recurrence rule if they are owner or editor on its `calendar_id`. Existing permission checks on `meal_events` (owner + participants) and `meal_recurrence_rules` (owner + household) are **replaced** by the calendar-level check. Meal-event-level `host/cohost/guest` participants are preserved as a separate dimension (they still drive per-meal invites and status display), but they no longer grant edit rights to users who aren't calendar members.
- **FR111:** The plan-meal sheet, quick-add flow, recipe → "Plan for…" flow, and recurrence-rule create flow all target the **currently-active calendar** by default. Users can change the destination calendar via a "Calendar: [name]" picker row inside the plan-meal sheet (below the Date row, above Meal Type). Picker options are restricted to calendars the user can write to (owned + editor).
- **FR112:** Moving an existing meal or recurrence rule between calendars is supported via the meal detail sheet / recurrence rule edit flow: a "Move to calendar" action presents the same calendar picker. Move is atomic (single update to `calendar_id`). Participants and status on the moved meal are preserved.
- **FR113:** `shopping_lists.auto_populate_from_calendar` continues to pull meal_events from every calendar the user has access to (owned + editor-member) across the requested date range. No change to the existing endpoint shape. The `PopulateFromCalendarRange` handler's `meal_events` query replaces its current owner-scoped WHERE with a calendar-membership-scoped WHERE.
- **FR114:** Users receive a push notification (via the existing invitation system) when they are invited to a calendar. Accepting the invitation adds the calendar to their switcher immediately. No new notification category is introduced — the existing `INVITATION_RECEIVED` and `INVITATION_ACCEPTED` types cover it.
- **FR115:** The Profile/Settings screen gains a **Shared Calendars** row that deep-links to a list of every calendar the user is an editor on. Tapping a row opens that calendar's members screen (parallel to recipe-book-members). This is the low-prominence surface for managing calendars the user doesn't own.
- **FR116:** The invite-link flow for calendars matches the shopping-list/recipe-book precedent: `POST /v1/invite-links` with `resource_type = "calendar"` creates a shareable token, `GET /v1/invite-links/{token}` returns preview metadata (calendar name, member count, owner display name), `POST /v1/invite-links/{token}/join` adds the current user as an editor. Deep-link scheme: `palateful://invite/{token}` (unchanged).

### New Non-Functional Requirements

- **NFR44:** The calendar switcher sheet loads within 200ms at P95 for a user with up to 50 calendars (owned + shared). Reuses the same caching pattern as the recipe-books list.
- **NFR45:** The backfill migration (every existing user → one default calendar + every meal_event/recurrence_rule backfilled) completes within 30 seconds on a prod-sized DB (current user count ≤ 50). The migration is re-runnable: re-running is a no-op if the default-calendar rows already exist.
- **NFR46:** Authorization check on every `meal_events` or `meal_recurrence_rules` read/write is a single indexed lookup on `calendar_users (calendar_id, user_id)`. No N+1 for list endpoints — list handlers preload calendar-membership once per request.
- **NFR47:** Moving a meal or recurrence rule between calendars is transactional; partial state (e.g., meal_event moved but participants lost) is not acceptable.
- **NFR48:** Zero data loss during the backfill migration — the migration is reversible (down-migration drops `calendar_id` FKs and restores implicit owner-scoping). A full DB snapshot is taken before running per NFR14 cadence.

### Explicitly Out of Scope for This Addendum

- **Viewer role** on calendars. Users who want read-only access to a partner's calendar still have to be invited as editor. Revisit if we see real demand.
- **Overlay view / color-coded multi-calendar display**. Users switch one at a time. Color field is reserved on the model but not surfaced.
- **Per-shopping-list calendar scoping** (FR113 alternative). All lists union across all accessible calendars. Revisit when a user explicitly asks to scope.
- **Copying a calendar** (duplicate template). Users who want a second similar calendar create it empty and add meals manually, or move/copy meals individually.
- **Calendar-level notification preferences** (mute a specific shared calendar). Existing notification categories are calendar-agnostic; if a partner's calendar is too noisy, the mitigation is leaving the calendar or muting the existing category.
- **Removing the existing `meal_event_participants` host/cohost/guest model.** The per-meal invite surface stays. Calendar membership is a separate, coarser dimension.
- **Transferring ownership as a separate UX primitive.** Owners invite another user as editor, promote them, and then leave; this is a low-frequency flow. If we see demand, add a bespoke transfer button later.
- **Public calendars (unauthenticated read).** Not in scope. Public recipe links (FR59) don't extend to calendars.

---

## Addendum — 2026-04-18 — Operator Observability: Latency Metrics & User Feedback Inbox

### Context

Two operator-facing gaps are holding back the product.

1. **No latency visibility.** The API has 80+ endpoints and a Celery worker with ~25 task types, and today there is nothing measuring how long any of them take. The existing `error_logs` table captures failures but not durations. Datadog is off the table (NFR29 — $50/mo cap for <50 users), and there is no Prometheus, CloudWatch EMF pipeline, or even a custom stats middleware. When a user reports "the app felt slow today," Leo has no way to confirm or localize it. The admin dashboard already shipped under Epic 12 — the natural home for this is a new `/admin/metrics` surface inside it.
2. **No user-feedback channel.** The post-cook feedback flow (Story 6-5) attaches *recipe* notes; it is not a place for "the app crashed in the share sheet", "add a dark-mode toggle in cook mode", or "I love the wizard". Users who want to talk to the developer have no in-app affordance, and Leo has no inbox to read from. In a friends-and-family product this is the highest-signal source of roadmap input, and it is wholly missing.

These two gaps are the operator side of the product: what an admin (currently just Leo) needs to run the service well. Epic 12 shipped admin role, error logs, admin API, admin dashboard, and production console. This addendum continues in that lineage.

### Locked decisions (from 2026-04-18 user batch)

- **Latency storage: Postgres-backed tables.** Two new tables (`request_latencies` for FastAPI, `task_latencies` for Celery) with batched async writes from middleware / Celery signal handlers. Zero new AWS infra. Aligns with NFR29. CloudWatch EMF and self-hosted Prometheus explicitly rejected as premature for <50 users; can revisit if scale changes.
- **Latency view shape: dedicated `/admin/metrics` page.** Mirrors the existing `admin_errors_screen.dart` pattern. Two sections (Endpoints, Tasks), each a sortable table with `p50 / p95 / p99 / count` per `(method, normalized_path)` or `task_name`, a selectable time window (1h / 24h / 7d), and a sparkline per row. Admin dashboard gains an "Overall p95 (24h)" + "Slowest endpoint" card that links to the full page. Drill-down to per-request sample lists is explicitly deferred.
- **Feedback alerts: push + unread badge.** On new feedback, push notification to every `is_admin=true` user via the existing `PushNotificationService.send_to_user(..., force=True)` (admin-critical → bypass quiet hours). Additionally, admin dashboard `/admin/stats` gains an `unread_feedback` count rendered as a badge on the Feedback card. Email-via-SES deferred.
- **Feedback flow: read-only inbox with mark-read / archive.** Admin sees feedback list with body, user, timestamp, app version, platform, optional category. Mark Read and Archive actions only — no reply UI. Reply / threaded conversations are a future epic when real demand appears.
- **Prod fetch-feedback script mirrors `promote_admin.py`:** direct `DATABASE_URL`, argparse CLI, audit row to `error_logs` with `service="audit"`, mirrored exit codes. Read-only export (no `--yes` required for list/export; `--yes` reserved for any future mutation like bulk-archive).

### New Functional Requirements

- **FR117:** FastAPI middleware records `method + normalized_path + status_code + duration_ms + user_id + request_id + created_at` into a new `request_latencies` table for every request except `/health` and `/ready`. Writes are batched via an in-process async queue flushed every 2 seconds or 100 samples (whichever first) so the hot-path cost is bounded. Path normalization strips UUID segments to keep cardinality bounded (e.g. `/v1/recipes/{recipe_id}` rather than `/v1/recipes/7f3c...`).
- **FR118:** Celery task signal handlers (`task_prerun` / `task_postrun` / `task_failure`) record `task_name + task_id + duration_ms + status (success|failure|retry) + queue_name + created_at` into a new `task_latencies` table. Writes are unbatched — task volume is low relative to HTTP requests.
- **FR119:** Admin-only `GET /v1/admin/metrics/endpoints?window={1h|24h|7d}` returns one row per `(method, normalized_path)` with `p50_ms`, `p95_ms`, `p99_ms`, `sample_count`, `error_rate` (fraction with `status_code >= 500`), and a 24-bucket sparkline (mean latency per equal-width time bucket) over the window. Default sort: `p95_ms` descending.
- **FR120:** Admin-only `GET /v1/admin/metrics/tasks?window={1h|24h|7d}` returns one row per `task_name` with the same percentile fields plus `failure_rate` and the same 24-bucket sparkline. Default sort: `p95_ms` descending.
- **FR121:** Admin dashboard `/v1/admin/stats` adds `overall_p95_ms` (24h window across all endpoints) and `slowest_endpoint` (`{method, normalized_path, p95_ms}`). Null on cold-start before any samples exist.
- **FR122:** A new Flutter admin screen `AdminMetricsScreen` (route `/admin/metrics`) renders two sections (Endpoints / Tasks), a window selector (1h / 24h / 7d), sortable tables with percentile columns and sparklines, and pull-to-refresh. Reachable from a new "Metrics" card on the admin dashboard.
- **FR123:** Samples in `request_latencies` and `task_latencies` older than 30 days are pruned by a new nightly Celery beat task (`cleanup_latency_samples`). Matches the existing `cleanup_error_logs` cadence.
- **FR124:** A new user-facing endpoint `POST /v1/user/feedback` accepts `body` (required, 1–4000 chars), `category` (optional enum: `bug`, `idea`, `praise`, `other`), and a `context` JSON blob (optional: `app_version`, `platform`, `route`, `recipe_id`) from the authenticated user. Stores into a new `user_feedbacks` table (`id`, `user_id`, `body`, `category`, `context`, `status` — `unread` default, can be `read` or `archived`, `created_at`, `updated_at`). On insert, a Celery task is enqueued that fans out a push notification to every `is_admin=true` user.
- **FR125:** Profile → Settings section gains a new "Send Feedback" row (icon `Icons.feedback_outlined`). Tapping opens a `FeedbackSheet` widget (modeled on `PostCookFeedbackSheet`) with a category dropdown, a multiline body field (with live character count), and a Send button. Submission calls `POST /v1/user/feedback` and closes the sheet with a snackbar ("Thanks — feedback sent"). Offline submissions are queued via the existing `RecipeCacheService`-style pattern and retried on next app resume.
- **FR126:** Admin-only `GET /v1/admin/feedback?status={unread|read|archived|all}&offset=&limit=` returns a paginated list of feedback items joined with user display name + email, body, category, context, status, created_at. Admin-only `PUT /v1/admin/feedback/{feedback_id}/status` sets status with a `{unread|read|archived}` payload. Audit row written to `error_logs` on status change.
- **FR127:** Admin dashboard `/v1/admin/stats` gains an `unread_feedback` count. A new "Feedback" card on the admin dashboard shows the count as a badge and links to `AdminFeedbackScreen` (route `/admin/feedback`). The screen mirrors `AdminErrorsScreen` — filter chip row (Unread / Read / Archived / All), paginated list, each item tappable to reveal a read-only detail drawer with full body + context + Mark Read / Archive actions.
- **FR128:** A new prod ops script `services/api/scripts/fetch_feedback.py` reads directly from `DATABASE_URL`, accepts `--since 7d|30d|all`, `--status unread|read|archived|all`, `--format csv|json|tsv`, and streams to stdout. Writes a single audit row per run to `error_logs` (service=`audit`, error_type=`FetchFeedbackExport`) capturing filter + row count. Mirrors `promote_admin.py` in CLI shape and exit codes.

### New Non-Functional Requirements

- **NFR49:** Latency-sample write overhead on the hot path adds ≤1ms at P95 to any request. The batched in-process queue writes asynchronously; a queue-full condition drops the oldest samples rather than blocking the request. The drop count is itself logged every minute so we can observe sample loss.
- **NFR50:** Aggregation queries on `request_latencies` and `task_latencies` for a 7d window return within 300ms at P95 on a dataset of up to 10M rows. `(created_at DESC, normalized_path)` and `(created_at DESC, task_name)` B-tree indexes are mandatory; query plans are captured in the story AC.
- **NFR51:** `request_latencies` and `task_latencies` combined stay under 2 GB at steady state on a <50-user deployment given the 30-day pruning window. If storage grows faster, retention tightens to 14 days before any new indexes or partitioning are introduced. Monitored by the existing RDS storage CloudWatch metric.
- **NFR52:** Feedback submission is rate-limited per authenticated user to 10 submissions per hour, returning 429 otherwise. Guards against both accidental form-resubmits and an abusive caller spamming the admin inbox.
- **NFR53:** New-feedback admin push dispatch never blocks the `POST /v1/user/feedback` response. The fan-out to admins runs as a Celery task (`worker.notification.notify_admins_new_feedback`); the user gets a <500ms acknowledgment regardless of FCM latency or admin count.
- **NFR54:** `fetch_feedback.py` streams output row-by-row (CSV / TSV / JSON-lines) rather than buffering the full result set in memory, so even a 100k-row export completes without OOM risk on the operator's local machine.

### Explicitly Out of Scope for This Addendum

- **Per-user latency drill-down / slow-request sample log.** Percentile tables + sparklines cover the 80/20. Revisit when a real debugging session is blocked by missing raw samples.
- **Alerting on latency thresholds.** No CloudWatch alarms, no Slack webhooks, no email on p95 spikes. Admin checks the dashboard when they care.
- **Tracing / per-request spans.** No OpenTelemetry, no Jaeger. Single `duration_ms` per request is the abstraction; span trees belong in a Prometheus/OTel world that is explicitly rejected for this scale.
- **Emailing feedback to admins (SES channel).** Push + badge proven sufficient. Email can be a later bolt-on.
- **Feedback reply from admin → user.** Read-only inbox only. Reply (one-way or threaded) deferred.
- **User-facing "your feedback was seen" acknowledgment beyond the submission snackbar.** No read receipt, no status surfaced to the user.
- **Auto-classification / sentiment / free-form tags.** Four-option enum (`bug`, `idea`, `praise`, `other`) is the full taxonomy.
- **Web / Android feedback parity surface work.** First shipment is the shared Flutter widget tree (iOS-primary). Android + Flutter-Web pick it up by construction; extra platform polish is out of scope here.
- **Migrating the existing post-cook feedback (Story 6-5) into the new inbox.** Recipe notes stay recipe-scoped — different signal.
- **Bypassing the auth gate for feedback.** Unauthenticated users cannot submit. Anyone in the app is already signed in via Auth0; the scope change isn't worth the spam surface.

---

## Addendum — 2026-04-18 — Activity Hub Redesign & Import Experience Overhaul

### Context

Despite heavy iteration (Epic 13 unified-import-pipeline, Epic MVP Finalization swipe-to-dismiss / retry / dismiss endpoints, the 2026-04-16 epic-bugs-activity-hub polish), Leo's daily use still reports the Activity Hub feels muddled. Three root causes are now understood:

1. **Imports and general notifications share one feed with filter chips.** The "Imports" chip on `/activity` is a redirect to a separate `/activity/import-history` screen — users learn this by accident. The two concerns aren't visually siblings; they feel like one mixed pile.
2. **The rich per-import debug view was deleted, not relocated.** The previous Add Recipe "In Progress" list exposed type + stage + raw parser text. Moving it to the Activity Hub (bugs-act-3) landed a slim ambient strip but erased the debug depth. Leo explicitly wants that depth back — in the new Imports surface.
3. **Review Import ingredient rows are two-row (qty/unit/name on row 1, notes on row 2)** and the extractor emits full-word units ("tablespoon", "teaspoon") that can't collapse into a compact single-line layout. The UI bug and the extractor behavior are one problem.

This addendum commits to a three-epic redesign that treats Activity Hub IA, rich import telemetry, and Review Import ingredient polish as one joined effort.

### Locked decisions (from 2026-04-18 user batch)

- **Top-of-screen tabs, not sub-routes.** `/activity` becomes a single route with two tabs: **Notifications** (invitations / partner_action / meal_reminder) and **Imports** (all import-sourced activity). The existing `/activity?filter=imports` redirect to `/activity/import-history` is replaced. The `Import History` route is retired — history becomes an expandable "See all" section inside the Imports tab.
- **Color-coded import sections.** Imports tab is sectioned by state with fixed color semantics: **BLUE = In Progress** (currently running), **YELLOW = Needs Review** (awaiting user decision), **RED = Failed** (terminal error), **GREEN = Auto-Imported** (completed successfully, no action required). These become semantic tokens in the Flutter theme (not raw `colorScheme` lookups) so every screen that references them stays in lockstep.
- **Per-row caret expansion.** Every import row (all four states) gets a caret toggle. Collapsed shows: source icon + recipe name + contextual one-liner + color-chip. Expanded reveals: stage timeline (parsed → extracted → matched → created, each ✓/⏳/✗), confidence score (when applicable), raw parser text preview (collapsible), retry history, error detail. This is the "information-heavy but readable" view the redesign promises.
- **Swipe semantics locked.** Swipe-to-archive works on all import rows **except** In Progress (blue). Blue rows have no swipe action — cancelling an in-progress import stays a detail-screen flow. All other states: swipe archives with 3s snackbar-undo per inherited locked-decision #3.
- **"See all" archived section.** Imports tab has a collapsed-by-default "See all" footer that, on expand, reveals archived + older-than-30d completed/failed imports. Default imports-tab view stays attention-first (YNAB-inspired, per `feedback_import_jobs_ux.md`).
- **Confidence score end-to-end, this release.** Extractors produce it, backend persists + exposes it, UI renders it on yellow rows + inside caret expansion. No coarse placeholder intermediate.
- **Unit normalization end-to-end, this release.** Extractor prompts enumerate the canonical abbreviated enum (tsp, tbsp, cup, …). Backend runs every parsed-recipe write through a `normalize_unit_display` step backed by a new unit-alias table (alias → canonical, e.g. tablespoon → tbsp). Flutter `UnitInput` coerces typed text to canonical on blur using the same alias map. Three layers, one source of truth.
- **One-line ingredient row.** `StructuredIngredientRow` redesigned to `[qty][unit▾][name-flex][caret][delete]` on one line. Name truncates with ellipsis. Notes + `is_optional` toggle move behind the caret. Caret auto-expands on render if notes or optional are non-empty so data isn't silently hidden.
- **No new bottom-nav tab.** Imports stays inside the Activity Hub. Single Activity tab in bottom nav, as today.
- **Ambient `LiveImportStrip` on Add Recipe stays one-liner.** The "N imports in progress" strip with deep-link to `/activity` (imports tab) is preserved. It is a link, not a duplicate — the rich view lives in the Imports tab, as decided.
- **No widening of notification-type coverage.** General Notifications tab renders the existing three activity types (invitation, partner_action, meal_reminder). Covering the other 14 `NotificationType` enum values (shopping, recipe-book, friend-request, etc.) is out of scope here — they are push-only today and not wired into the activity-feed pipeline.

### New Functional Requirements

**Activity Hub IA**

- **FR129:** `/activity` becomes a single route with two top tabs: **Notifications** and **Imports**. Tab selection is remembered per-session (not persisted across cold starts); cold-start default is **Notifications**. Deep-link `/activity?tab=imports` selects the Imports tab on open. The old `?filter=<enum>` param is accepted and mapped forward (`filter=imports` → `tab=imports`, `filter=partner|reminders` → `tab=notifications`) for one release cycle, then removed.
- **FR130:** Notifications tab renders activity-types `invitation`, `partner_action`, `meal_reminder` in a single chronological feed (no internal sub-sections). Swipe-to-archive on each row writes through to a new `POST /v1/user-activities/{id}/archive` endpoint. Tab-open marks every loaded item read per the existing bugs-act-1 rule.
- **FR131:** Imports tab renders per-import rows grouped into four fixed sections, top-to-bottom: **In Progress** (blue), **Needs Review** (yellow), **Failed** (red), **Auto-Imported** (green). Empty sections are hidden (no "0 items" placeholder). Within each section, sort by most-recent-first. Sections have a header chip showing the section name + count.
- **FR132:** In Progress rows have no swipe action (cancel stays a detail-screen flow). All other rows support swipe-to-archive with 3s snackbar-undo (inherited locked decision). Archived rows disappear from their color section and reappear in the "See all" footer.
- **FR133:** Imports tab has a collapsed-by-default **See all** footer. On expand it reveals: archived imports (any state), completed/failed imports older than 30 days, and items explicitly dismissed. This section uses muted typography to visually deprioritize it (per `feedback_import_jobs_ux.md` YNAB pattern).
- **FR134:** Color tokens BLUE / YELLOW / RED / GREEN are added to the Flutter theme as `importStateInProgress`, `importStateNeedsReview`, `importStateFailed`, `importStateAutoImported` semantic tokens. Every screen that references import state (Imports tab, detail screens, `ImportActivityDetail` card, `LiveImportStrip`) reads from these tokens. No direct `colorScheme.error`/`colorScheme.tertiary` references for import state after this epic.

**Rich Per-Row Detail + Stage Telemetry**

- **FR135:** Every import row in the Imports tab (all four states) exposes a caret toggle. Collapsed shows: source-type icon + recipe name + 1-line status label + color chip + relative timestamp. Expanded reveals: stage timeline, confidence score (if applicable), raw parser text preview (collapsible inside the expansion), retry history (count + last-retry-at), error detail (if present), source reference (URL / photo thumbnail / text preview). Expansion state is remembered per-row for the session.
- **FR136:** Backend `GetImportItem` response adds `last_successful_stage` (string, nullable — was already on the DB model, never serialized), `last_retry_at` (datetime, nullable — new column, added in this epic's migration), and `awaiting_review_reason` (enum `low_confidence | unmatched_ingredients | missing_title | manual`, nullable — derived server-side from the routing logic that flipped the item into `awaiting_review`). The reason field drives the 1-word chip on collapsed yellow rows so users can skip expansion on obviously-action items.
- **FR137:** New endpoint `GET /v1/import-items/{id}/telemetry` returns a stage log: array of `{ stage: str, status: "pending|ok|failed|skipped", started_at: datetime?, completed_at: datetime?, duration_ms: int?, raw_output_preview: str? }`. `raw_output_preview` is truncated to 2KB and only included for stages that produced text output (parser, extractor). Stage log is derived from `error_logs` filtered by `import_item_id` (not a new table) to avoid migration bloat for telemetry that already exists as log events.
- **FR138:** Parser batch responses (`GET /v1/parser/batches`) continue to return per-job `extracted_text`. Imports tab rows belonging to a parser-batched import source surface the parser batch's `extracted_text` inside their caret expansion, alongside their own telemetry — so Leo sees OCR output and extractor output in one place without cross-screen navigation.

**Confidence Score — End-to-End**

- **FR139:** Recipe extractors (`text_extractor.py`, `vision_extractor.py`, `ai_extractor.py`) produce a top-level `confidence_score: float` in their output JSON, range 0.0–1.0, representing the extractor's self-reported confidence in the overall extraction. The extractor prompt instructs the model to emit the score; on malformed output, a heuristic fallback (ingredient-match-rate × step-count-presence × title-presence) computes the score server-side and the result is annotated `confidence_source: "heuristic" | "model"` so UI can badge heuristic-derived scores if we want to later.
- **FR140:** `ImportItem.parsed_recipe.confidence_score` is persisted as part of the parsed_recipe JSONB payload (no new column). `GetImportItem` surfaces it at the response root as a convenience. `GET /v1/import-jobs` / `GET /v1/import-items/{job_id}` item summaries include it so the Imports tab can render without a second fetch.
- **FR141:** Needs-Review (yellow) rows render the confidence score inline as a small badge next to the recipe name — low (<0.5) shows a warning glyph, medium (0.5–0.8) shows the numeric percentage, high (>0.8) shows a check glyph (but still flagged needs-review because some other rule routed it here). Tapping the row's caret reveals per-ingredient confidence (when the extractor provides per-item scores) inside the expansion.

**Review Import — One-Line Ingredient Row**

- **FR142:** `StructuredIngredientRow` widget is redesigned to a single-line layout: `[qty][unit▾][name-flex][caret][delete]`. `qty` is a compact 56–64px-wide field, `unit` is a dropdown chip ~80–96px wide, `name` is flex with ellipsis truncation on overflow, `caret` toggles notes + optional, `delete` is a trailing icon. Row height is a single tap target (WCAG ≥44pt).
- **FR143:** The `notes` field and `is_optional` toggle move behind the caret's expanded area. The caret is **auto-expanded** on initial row render if either `notes` is non-empty or `is_optional` is true, so pre-existing data is not silently hidden. Collapsed caret state renders a subtle indicator dot on the caret if hidden fields have values (so user scanning the list sees "this row has more").
- **FR144:** A new `IngredientRowStateBadge` (optional) renders inline on the row when an ingredient has `matched_ingredient_id` null (auto-created via find-or-create) or `pending_review=true` on the linked ingredient. This closes the loop with Story 13.3 (pipeline auto-creates) by surfacing the state to the user at review time. Badge is a single icon with a tooltip; no extra row space.

**Unit Normalization — End-to-End**

- **FR145:** Extractor prompts (AI, vision, text) explicitly enumerate the canonical abbreviated unit tokens: `tsp, tbsp, cup, fl oz, ml, l, g, kg, oz, lb, each, pinch, dash, clove, slice`. Prompts instruct the model to use those exact tokens — no "teaspoon", no "Tbsp.", no "grams". The extractor's post-processing validates that emitted `unit` is one of the canonical tokens; unknown units fall through with a warning log.
- **FR146:** Backend adds a `unit_aliases` table (columns: `alias` PK, `canonical_unit` FK → `units.name`, `created_at`) seeded with common full-name and variant spellings (tablespoon → tbsp, teaspoon → tsp, gram → g, kilogram → kg, pound → lb, ounce → oz, liter → l, milliliter → ml, fluid ounce → fl oz, …). A new helper `normalize_unit_display(raw: str) -> str` does an alias-table lookup; hits return the canonical, misses return the raw input unchanged and emit `error_logs` row `service="audit"`, `error_type="UnitAliasMiss"` so the miss set can be harvested into the alias table over time.
- **FR147:** `normalize_unit_display` runs on every write path that persists a parsed or user-entered unit: `extract_recipe_task`, `approve_import_item`, recipe create/update, wizard draft save. No write path bypasses normalization. A unit test per path asserts that input "tablespoon" produces stored `tbsp`.
- **FR148:** Flutter `UnitInput` widget coerces typed text to the canonical enum on field-blur and on typing a trailing space. Coercion uses a client-side mirror of the backend alias map, fetched once per session from a new `GET /v1/units/aliases` endpoint and cached. On cache miss (first app run), the widget ships with a small hardcoded default alias set covering the top ~20 aliases so behavior works offline before the fetch lands.

### New Non-Functional Requirements

- **NFR55:** `GET /v1/import-items/{id}/telemetry` returns within 300ms at P95 for any single import item. The stage log is a derived view over `error_logs` filtered by `import_item_id` — an index on `error_logs (import_item_id, created_at)` is added in this epic's migration to support the lookup.
- **NFR56:** Confidence-score generation adds ≤10% to extractor latency. If the LLM output is missing or malformed, the heuristic fallback executes locally (no retry, no second LLM call) and returns within 50ms.
- **NFR57:** Activity tab switching (Notifications ↔ Imports) does not re-hit the network — both tabs' data loads once on screen open, each polls on its own existing 30s cadence. Switching is instant.
- **NFR58:** `normalize_unit_display` is O(1) per lookup (hash-backed alias cache, loaded once per worker process on startup). Bulk ingredient writes (e.g., a 40-ingredient recipe) incur no measurable normalization cost.
- **NFR59:** `GET /v1/units/aliases` returns within 100ms at P95 and is safe to call on every cold app launch. Response is cacheable (`Cache-Control: max-age=86400`) since the alias table changes rarely.

### Explicitly Out of Scope for This Addendum

- **Cancel-in-progress from the row.** Blue (In Progress) rows remain read-only. Cancel stays the existing detail-screen flow. Adding a "cancel" swipe action on blue is a future consideration.
- **Confidence score on green (auto-imported) rows.** Score is surfaced only on yellow (Needs Review) where it drives user decision. Green imports already succeeded — showing the score there is noise.
- **Bulk unit normalization of historical recipes already in the DB.** `normalize_unit_display` runs on new writes only. A backfill of historical rows is a future ops script if needed — the Add Recipe / Review Import surface where the user sees units most is fed by new writes.
- **Per-ingredient confidence breakdown.** Extractors produce only the top-level score. Per-ingredient confidence (e.g., "we're 92% sure this says flour, 40% sure on butter") would require prompt + schema changes and is deferred to a follow-up epic.
- **Typography of fractions (superscript, Unicode vulgar fractions).** Quantity rendering stays with the existing `Fraction.limit_denominator(8)` convention (text like `1/2`). Deferred pending a dedicated typography pass.
- **Real-time push for every import state transition.** Push still fires only on `import_needs_review` (existing). Other state transitions (in-progress → extracting → matching → completed) remain visible via the 30s polling cadence, as today.
- **Multi-select archive / bulk actions in either tab.** Swipe-per-row archive is the only bulk-ish primitive. "Archive all failed" already exists at the job-section level and is preserved; no new bulk actions are added here.
- **Widening Notifications tab to cover the other 14 NotificationType enum values.** Shopping / recipe-book / friend-request / calendar events stay push-only and do not appear in the Notifications feed. Wiring them up is a future cross-cutting epic.
- **Retiring `ImportHistoryScreen` code without a deprecation lap.** The route is removed from the router immediately; the widget file stays in the tree for one release so any deep link in push-notification payloads (historical) doesn't 404. Remove in the release after this epic ships.
- **Promoting the Imports tab to its own bottom-nav tab.** Single Activity tab stays. Top tabs are the scope for IA split; no bottom-nav change.
- **Refactoring `ImportActivityDetail` (the hierarchical card).** It is reused as the caret-expansion content scaffold. Its internal render order (error → stage → source → timestamps → retry) is preserved; only the chrome around it (embedding inside a per-row caret vs. a full detail screen) changes.

## Addendum — 2026-04-18 — Universal Share-to-Palateful (Ingest from OS Share Sheet)

### Context

Today FR23 ("Users can import recipes via the iOS/Android share sheet from any app") is marked complete in the FR coverage map (Epic 3), but the end-to-end flow is broken on iOS and narrow on Android:

- **iOS:** No Share Extension target exists in `app/ios/Runner.xcodeproj`. `receive_sharing_intent ^1.8.0` is installed on the Flutter side but has no native bridge, so Palateful does not appear in the iOS share sheet for URLs or files.
- **Android:** Manifest declares `text/plain` and `text/*` MIME filters only. Photos, PDFs, audio, video, and spreadsheets never route to Palateful.
- **Flutter:** `_handleSharedFiles` in `app/lib/main.dart` already routes by file extension to `/recipes/add/{photo,pdf,audio,spreadsheet,share}`, but the destination screens open their own file pickers and don't accept a pre-selected file path — the handoff is dead code past step one.
- **Backend:** Handles URL (incl. social media via `video_extractor.py` + yt-dlp), photo (client-side OCR), text, audio (Whisper), PDF (PyMuPDF + multi-recipe boundary), spreadsheet. **Missing:** local video file source_type and ffmpeg in the worker container; presigned S3 upload endpoint for import files (currently base64-in-body only).

This addendum documents the requirements and locked decisions to close FR23 end-to-end and extend ingest to cover any of today's supported media types — whatever the OS share sheet hands us, we handle it or degrade gracefully.

### New functional requirements

- **FR-SHR-1** — Palateful appears as a share target in the iOS share sheet for URLs, images, PDFs, audio files, video files, and plain text. Selecting Palateful opens a minimal confirmation sheet (icon + detected content summary + optional recipe-book picker + Save).
- **FR-SHR-2** — Palateful appears as a share target in the Android share sheet for the same MIME surface: `text/*`, `image/*`, `video/*`, `audio/*`, `application/pdf`, `text/csv`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, plus a `*/*` wildcard fallback.
- **FR-SHR-3** — Local video files shared from Photos (iOS) or Files (Android) run through a new `video_file` import path: ffmpeg extracts audio, Whisper transcribes, existing text extraction path structures the recipe. Hard cap: 100 MB uploaded.
- **FR-SHR-4** — iOS Share Extension uploads file content directly to S3 via a presigned URL and calls the import API from inside the extension — no dependency on the main app being running. A push notification fires when processing completes and the recipe is ready for review (or when extraction fails).
- **FR-SHR-5** — When shared content is not in a supported source type, Palateful shows a single graceful error state ("We couldn't extract a recipe from this") with a retry/edit-by-hand affordance — never a silent drop.
- **FR-SHR-6** — When the main app receives a share (iOS: App Group handoff if extension upload is deferred; Android: intent), it routes to a universal "Import Received" landing screen that performs content-type detection (MIME + extension + content prefix), shows ≤2s of progress context, and then routes to the appropriate typed import screen or directly to the import activity feed.
- **FR-SHR-7** — All typed import screens (`photo_capture_screen.dart`, `pdf_import_screen.dart`, `audio_import_screen.dart`, `spreadsheet_import_screen.dart`, plus the new video file screen) accept an optional pre-selected file path via constructor/route param and skip the file picker when provided.
- **FR-SHR-8** — Social media URL detection (TikTok / Instagram / YouTube / Pinterest / Facebook) runs in the import endpoint, not the extract task, so `ImportItem.source_type` is persisted correctly at creation time (`video` for social URLs, `url` for standard web).

### New non-functional requirements

- **NFR-SHR-1** — The iOS Share Extension completes its visible work (upload + API enqueue + confirmation dismissal) within 5 seconds at P95 for files ≤10 MB; files up to 100 MB may take longer but must show progress.
- **NFR-SHR-2** — iOS Share Extension memory stays under the 120 MB iOS-imposed ceiling; file data is streamed to S3 (presigned PUT), never fully buffered.
- **NFR-SHR-3** — Files >100 MB are rejected in the extension UI with a clear "open Palateful and import from Files" fallback message. No silent failures.
- **NFR-SHR-4** — The existing `group.com.palateful.app` App Group is reused for iOS extension ↔ main app state handoff (e.g., "pending imports" count for a badge). No new App Group is introduced.
- **NFR-SHR-5** — ffmpeg is added to `services/worker/Dockerfile` with LGPL-compatible build flags; worker image size increase is capped at ≤150 MB.

### Locked decisions (from this planning loop)

1. **iOS cold-start handling:** Extension uploads + confirms. The Share Extension calls the import API directly (no dependency on main app running). Main app receives push notification when processing finishes.
2. **Extension UI depth:** Minimal confirmation sheet — icon, one-line detected-content summary, optional recipe-book picker, Save button. No full preview, no editing. 2–3 days of native work vs. a rich preview's 4–5.
3. **Scope of "anything":** URL, photo, text, audio, PDF, spreadsheet, social media video URL, local video file. Out of scope for this planning loop: `.docx`, `.rtf`, `.pages`, zip archives, arbitrary unknown files — these hit the FR-SHR-5 graceful error state.
4. **Large-file strategy:** Presigned S3 upload directly from the extension, hard cap at 100 MB. Larger files show a "too large, open in Palateful" fallback.

### What's explicitly out of scope

- iOS Share Extension rich preview / in-extension recipe editing (minimal sheet only).
- Office-document ingest (Word, Pages, RTF) — reserved for a follow-up epic if user demand emerges.
- Deferred import / offline queue when the extension has no network — v1 requires network at share time; extension shows an error and suggests retrying.
- Multi-file share (user selects 3 photos → 3 recipes): v1 processes only the first file and shows "Only the first item was imported" banner. Batch-aware share is a follow-up.
- Apple Watch share support, macOS share extension, Shortcuts.app integration.
- Renaming / re-plumbing existing source_types. The schema stays; `video_file` is additive.

### Dependencies and collision risk

- `epic-activity-hub-redesign` (in-progress) is reshelling the import activity feed where the "your shared recipe is ready" push notification deep-link lands. Share epics must wait for `ahr-3` (two-tab shell + routing) to consume the new deep-link target, **or** ship the deep link against the existing feed and migrate on activity-hub completion.
- `epic-review-import-ingredient-polish` (riip, backlog) and `epic-bugs-import-photo-pipeline` (backlog) both touch extractors and ingredient rows; share epics stay away from those files. No extractor prompt changes in this surface.
- `epic-media-import.md` is retired by this addendum — Story 5 (Add Recipe Sheet redesign) already shipped as Media.5; Stories 1–4 (social router, audio fallback, PDF, audio files) were absorbed into the current backend before this planning loop. Remaining work is what this addendum covers.

## Addendum — 2026-04-18 — Android Play Store launch + CI hardening

### Problem

The Android app builds. It runs in an emulator. `epic-share-android-entrypoint` expanded share-sheet coverage. But nothing today actually *ships* Android to a real user — Palateful is iOS-first and Android has lagged. To close the gap we need three things in parallel:

1. **App-layer readiness** — the release AAB must satisfy Google Play policy (permissions, icon, notification channels) and a user on Android 13+ must actually receive FCM push notifications.
2. **CI stitched end-to-end** — a `v*.*.*` tag push must reliably land a signed AAB on Play Store internal track, with Crashlytics symbols uploaded, without human intervention.
3. **Manual runbook for the human-only Play Console steps** — developer account signup, keystore generation, first AAB upload, Data Safety form, privacy policy URL, content rating, tester recruitment. Produced as `ANDROID.md` at repo root.

The operator does **not** have access to an Android device during initial rollout. Production-readiness therefore leans on Play Console's Pre-Launch Report (auto-runs on every AAB), Firebase Test Lab soft-smoke in CI, and an internal-track tester group of friends/family with Android devices. Production promotion is a manual, later step — Play's new-personal-account rules require a 14-day × 12-tester closed test anyway.

### Functional requirements

- **FR-AND-1** — On Android 13+, when the user grants notification permission via onboarding, FCM push notifications show up in the system shade. (Today's manifest has no `POST_NOTIFICATIONS` → silent failure.)
- **FR-AND-2** — The app's launcher icon is an adaptive icon (foreground + background + monochrome). Old raster icon preserved as fallback.
- **FR-AND-3** — `https://palateful.app/...` deep links open the app directly (no browser chooser). Android App Links verified via `.well-known/assetlinks.json` served from palateful.app. Existing Auth0 `com.palateful.app://` custom scheme preserved for backward-compat.
- **FR-AND-4** — `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO` removed from AndroidManifest. Share-received files continue to open via intent-grant flag (`FLAG_GRANT_READ_URI_PERMISSION`), which is what the existing Jan 2025 Play policy requires. `sae-1`'s permission additions are reverted.
- **FR-AND-5** — `SCHEDULE_EXACT_ALARM` remains declared (cook timer UX requires exact firing). Justification copy for Play Console sensitive-permission review lives in ANDROID.md and is provided verbatim to the reviewer.
- **FR-AND-6** — Android Crashlytics symbol upload happens in CI after AAB build, so Android-native stack traces are symbolicated in the Firebase Crashlytics dashboard.
- **FR-AND-7** — `https://palateful.app/privacy` returns a publicly readable HTML page listing: Firebase Crashlytics + Messaging, Auth0 (email/name/user ID), S3 user-uploaded media (photos, audio, video), Google/Apple sign-in, OpenAI/Anthropic chat subprocessors, Play Billing (when applicable), retention policy, contact email, GDPR/CCPA/COPPA notes, deletion request process.
- **FR-AND-8** — Pushing a `v*.*.*` git tag runs `mobile-builds.yml android-build` end-to-end: analyze + test + build AAB + upload Crashlytics symbols + Firebase Test Lab soft-smoke (non-blocking) + upload to Play Store internal track. Single-operator flow.
- **FR-AND-9** — `mobile-builds.yml` and `ci.yml` agree on Flutter channel + version (`stable`, pinned). Gradle cache persists across runs.
- **FR-AND-10** — A new workflow `promote-android.yml` (manual dispatch only, gated by GitHub `production` environment approval) promotes a build already on one track to another via Fastlane `upload_to_play_store(track_promote_to:)`, with no rebuild.
- **FR-AND-11** — `ANDROID.md` at repo root is the single source of truth for the manual steps required *outside* of the repo: keytool keystore generation, `base64` → GitHub Secret, Google Play Developer account signup (Personal, display name "Palateful", $25), GCP service account for Fastlane, Play Console app creation, Play App Signing enrollment, Data Safety form filling (paste-ready text blocks), Content Rating IARC answers, Target Audience (Teen 13+), Sensitive Permissions Declaration (SCHEDULE_EXACT_ALARM justification), tester recruitment via Google Group, first AAB upload.
- **FR-AND-12** — `app/android/play-store-assets/` holds the 512×512 app icon, 1024×500 feature graphic, and 2–4 phone screenshots, version-controlled so the user can re-upload idempotently.

### Out of scope

- **Automated production promotion** — stays manual. User promotes via Play Console UI after observing internal-track stability.
- **Staged rollout automation** — user manages rollout % from Play Console UI. `promote-android.yml` sets target track; user sets user_fraction later.
- **Dynamic feature delivery** / app bundles with split APKs — monolithic AAB only.
- **Google Play Billing integration** — will be its own epic when subscriptions ship.
- **Organization developer account migration** — personal account stays. D-U-N-S upgrade is a later decision.
- **Android-specific UI/UX polish** — Material You theming, edge-to-edge, navigation-bar color, per-device testing — deferred to a post-device-access epic.
- **Play Console API for store listing updates** — listing stays hand-edited in Play Console UI. Automating it is low-value while the app is pre-launch.
- **Android integration test suite** — CI runs Firebase Test Lab Robo crawl as a soft-smoke. Full instrumented tests are deferred.
- **Secondary tracks beyond `internal` / `production`** — Closed test (12-tester × 14-day gate) is documented in ANDROID.md but not wired into CI. Open test (public beta) deferred.

### Locked decisions (resolve cross-epic ambiguity)

1. **Personal developer account**, display name "Palateful", $25 one-time fee.
2. **SCHEDULE_EXACT_ALARM kept** — justification: "Palateful is a cooking timer app; cook timers must fire at the scheduled instant during active cooking to avoid ruining food. Inexact alarms (±15 min drift under Doze) are unacceptable."
3. **READ_MEDIA_* removed** — shared-file intent flag `FLAG_GRANT_READ_URI_PERMISSION` grants transient read access; declaring these permissions now triggers Jan 2025 Play policy review friction with no benefit.
4. **Privacy policy at `https://palateful.app/privacy`**, served by the existing Flutter-web Cloudflare Pages deploy (static HTML in `app/web/privacy.html`).
5. **HTTPS App Links wired now** — `assetlinks.json` under `app/web/.well-known/` deploys with Flutter web; manifest gets `<data android:scheme="https" android:host="palateful.app" />` + `android:autoVerify="true"`.
6. **pubspec.yaml stays the single version source**. Flutter's Gradle plugin reads `version: x.y.z+N` and wires versionCode/versionName. User bumps pubspec + creates a matching `vX.Y.Z` tag. No CI-side tag-to-pubspec mutation.
7. **Target audience Teen 13+** — alcohol-containing recipes are expected; Play's "depicting alcohol" policy forces ≥13.
8. **Firebase Test Lab is soft-fail** — a single Robo crawl on one emulator runs after AAB build, never blocks Play Store upload.
9. **YOLO acceptance** — "signed AAB lands on internal track reliably on every tag push; real-device issues are fixed later when the operator has hardware access."
10. **First AAB upload is manual** — Fastlane cannot create a new Play Console app. Subsequent uploads are CI-driven.

### Dependencies and collision risk

- Touches `app/android/app/src/main/AndroidManifest.xml` — `sae-1` landed that file recently. Permission cleanup (FR-AND-4) is a small revert. No conflict with in-flight share work.
- Touches `app/web/` — adds `privacy.html` and `.well-known/assetlinks.json`. The `deploy-web` job in `ci.yml` already ships everything under `app/web/` via Cloudflare Pages, no workflow change required for those files.
- Touches `.github/workflows/mobile-builds.yml` — shared with iOS beta lane. Changes isolated to `android-build` job; Flutter-version pinning affects both platforms (single source of truth is a win).
- Touches `app/fastlane/Fastfile` — Android lane extended with Crashlytics symbol upload and new `promote` lane.
- Touches `firebase.json` — flip Android `uploadDebugSymbols` handling.


---

## Addendum — 2026-04-18 — Push Notifications Diagnostics & Hardening

### Scope

The iOS proof-of-life epic (`epic-notifications-ios-proofoflife`, all four stories marked `done`) shipped the plumbing — AppDelegate APNs forwarding, log-only backend mode, admin test-push endpoint, onboarding permission step. The primary admin / dogfood user reports the prompt has never fired on his existing-account TestFlight launches and that logging out / in or toggling iOS Settings produces nothing.

Root-cause trace identified three failure modes:

1. **Onboarding-only permission gate.** The `notification_permission_step` runs solely for `has_completed_onboarding=false` users. Router gates at `onboarding_welcome_screen.dart:39-48` and `app_router.dart:103-106` auto-skip onboarding for past-completion users. Any account that finished onboarding before notif-4 landed (or tapped Not Now) is permanently locked out of the prompt path.
2. **Silent failure everywhere.** `push_notification_service.dart` + `AppDelegate.swift` use `debugPrint` / `print` for every catch block. TestFlight release builds strip `debugPrint`. Zero observability.
3. **No bounded retry.** `ensureRegistered()` already auto-prompts on `notDetermined` at boot (`main.dart:135`) and on foreground resume, but has no retry discipline if Firebase racing / transient errors block the first attempt, and no breadcrumbs on its state transitions.

### Functional Requirements (addition)

- **FR-PDH-1** — On app boot (post-auth, post-Firebase-init), if OS notification permission status is `notDetermined`, the app MUST auto-trigger the OS permission prompt without requiring onboarding reruns. Applies to all authenticated users regardless of `has_completed_onboarding` state.
- **FR-PDH-2** — The auto-prompt is retried up to 3 times per app-launch if `notDetermined` persists post-`requestPermission`. Counter is in-memory, resets on cold start. No retry after 3 attempts this launch.
- **FR-PDH-3** — Every failure in the push-notification pipeline (permission query exceptions, `getToken` null-after-granted, `getToken` exception, backend token registration failure, APNs `didFailToRegister`, APNs registration timeout 10s, foreground banner show failure, topic subscribe/unsubscribe failure, `openOsSettings` failure, notification-preferences save failure) MUST call `ErrorReporter.report(...)` with `area: 'push'` and a specific `operation:` tag. Existing `debugPrint` calls in these paths are replaced.
- **FR-PDH-4** — iOS native failures (`didFailToRegisterForRemoteNotificationsWithError` and a new 10s registration-timeout safety net) MUST forward via a `palateful/push` MethodChannel to Flutter, which reports them through `ErrorReporter`.
- **FR-PDH-5** — Breadcrumbs via `ErrorReporter.log(...)` fire at every state transition in `ensureRegistered`: entry, initial-status, pre-prompt, post-prompt, granted/denied branch, completion.
- **FR-PDH-6** — Admin dashboard gains a `GET /api/v1/admin/notifications/health/{user_id_or_email}` endpoint returning: `notification_permission_status`, `push_tokens` (count + per-token metadata with FCM token prefix only), `recent_errors` (last 10 `error_logs` where `service="push_notifications"`, filterable via `?error_limit=`), `last_successful_send_at` (explicitly `null` in this epic; schema placeholder for future), `crashlytics_query_url` pre-filtered to the user's Auth0 ID.
- **FR-PDH-7** — The admin Notifications panel accepts a UUID or email input, renders the health JSON in a readable layout, and surfaces a "Send test push to this user" button that reuses the existing notif-3 endpoint with `target_user_id`.
- **FR-PDH-8** — Every health-check call writes ONE `error_logs` audit row with `service="audit"` and `error_type="AdminPushHealthCheck"`, matching `promote_admin.py` shape exactly.
- **FR-PDH-9** — `docs/PUSH_NOTIFICATIONS.md` gains a "Diagnosing a user who reports no pushes" runbook that chains: health lookup → interpret permission state → interpret token count → interpret recent errors → test-push as last resort.

### Non-Goals (this epic)

- **No new user-facing UI.** Existing Profile → Notifications warning for `denied` state is the ONLY user-visible surface. No home-screen banner, no modal, no re-onboarding.
- **No Android parity.** iOS-first, mirroring parent epic. Android-side failures would be caught by the same `ErrorReporter` integration (already platform-agnostic in Flutter code), but no Android-specific hardening in this epic.
- **No `push_send_log` table.** `last_successful_send_*` ships as `null`. Adding a dedicated send-log table is deferred to a follow-up if diagnosis calls actually need it.
- **No user-facing toasts for registration failures.** The requirement is admin visibility, not user feedback.
- **No changes to the Firebase project / APNs key / Terraform.** Infrastructure is already correct.

### Locked decisions

1. **Loud auto-prompt on `notDetermined`** via `ensureRegistered()` at boot — no banner, no ceremony. Already the current code path; this epic makes it robust.
2. **`denied` state surfaces in Profile only** via the existing `_buildOsPermissionWarning` card. No new surfaces.
3. **Admin-only diagnostic.** No user-facing health screen.
4. **Errors to `ErrorReporter` (Crashlytics), not toasts.** Existing fallback to `debugPrint` in local/test modes preserves dev ergonomics.
5. **Bounded retry: 3 attempts per app-launch.** Prevents prompt-spam if Firebase is misbehaving.
6. **No new DB tables.** All diagnostic data from existing `users.notification_permission_status`, `push_tokens`, `error_logs`.
7. **MethodChannel name: `palateful/push`** (pending collision check at dev time).

---

## Addendum — 2026-04-18 — Meals: Higher-Order Recipe Grouping

### Context

Today the app is strictly recipe-centric: every `meal_event` (calendar slot) points to a single optional `recipe_id`, and there is no first-class way to bundle two or more recipes into one served-together meal. The user hit this when recipe imports produced pairs like **Lemon Dressing** and **Kale and Collards Salad** — mechanically they are two recipes, conceptually they are one meal. A dozen other pairings already exist in the dogfood library (entrée + side, base + sauce, main + dessert).

This addendum introduces **Meal** as a first-class, reusable container that bundles two or more recipes under one name. A Meal has its own detail screen, lives inside a `recipe_book` (inheriting that book's sharing), can be scheduled onto the calendar as a single `meal_event`, and drives shopping-list population across all of its component recipes.

The word "meal" in the UI is user-facing; the existing `meal_event` and `meal_recurrence_rule` tables (calendar slots / recurrence rules) are internal and never visible to the end user, so the naming collision is tolerable. Internally: **Meal = the reusable bundle of recipes; MealEvent = one scheduled occurrence**.

### Locked decisions (from 2026-04-18 user batch)

- **Model shape**: reusable template, first-class entity. Not a one-shot assembly. Users create and name Meals once, schedule them many times, share them with household members.
- **Container**: Meals live **inside a `recipe_book`**, with a mandatory `recipe_book_id` FK — exactly mirroring `Recipe`. Sharing, archiving, and member roles inherit from the book via the existing `recipe_book_user` substrate. No new sharing substrate is introduced.
- **Component recipes can come from any book the user can READ**, not only the Meal's own book. A Meal in Leo's personal book may reference a recipe in a book shared with him. If a component recipe later becomes unreadable (book unshared / recipe archived), the component is gracefully hidden in read surfaces and flagged in edit surfaces — the Meal is never deleted as a side-effect of a component becoming unavailable.
- **User-facing name**: **Meal**. DB table: `meals`. DB join: `meal_recipes`. The existing `meal_events` / `meal_recurrence_rules` tables are not renamed and are not visible in user copy. MCP tool names: `create_meal`, `get_meal`, `list_meals`, `add_recipe_to_meal`, `remove_recipe_from_meal` — distinct from the existing `create_meal_event` etc. AI chat disambiguation is straightforward because a Meal is "what you cook" and a MealEvent is "when you cook it."
- **Combining UX in v1**: polished manual multi-select picker (search + recent + favorites chips, reuses `RecipeAutocompleteField` pattern). AI-suggested pairings (e.g., "you added a Lemon Dressing — want to pair with one of these 3 salads?") are explicitly deferred to a follow-up epic.
- **Schema strategy (design decision, party-mode to cross-check)**: **Option (a) — dual nullable FK on `meal_events` and `meal_recurrence_rules`.** A new `meal_id` column is added alongside the existing `recipe_id`; a DB check constraint enforces `num_nonnulls(recipe_id, meal_id) <= 1`. This preserves the existing single-recipe scheduling path verbatim (no data migration needed), keeps the recurrence/shopping-list/notification code paths largely unchanged, and adds the group-scheduling path cleanly. Rejected alternatives: (b) template-expansion into N meal_events (confuses the calendar UX — "one meal" becomes N cards) and (c) M:M join replacing the single `recipe_id` (larger migration, regressions on all existing callers).
- **Shopping-list aggregation**: within a single Meal, duplicate ingredients across component recipes are **summed** (1 tbsp olive oil in the dressing + 1 tbsp olive oil in the salad = 2 tbsp line item). Across different meal_events on different days, the existing per-event separation is preserved (Monday's 2 tbsp and Wednesday's 2 tbsp remain separate line items). This mirrors the user's cooking intuition: "what do I need for tonight's meal" vs. "what do I need for the week."
- **Cooking mode**: a Meal does **not** have a combined cooking mode in v1. The Meal detail screen exposes a clear "Open recipe" action per component; the user chooses which recipe to cook and the existing single-recipe cooking mode takes over. Combined cooking mode is deferred.
- **Ordering**: Meals are stored with an `order_index` on `meal_recipes` rows to preserve user-chosen order (so the dressing can be listed before or after the salad per the user's preference), but there is **no "courses" UX** in v1 (no starter/main/dessert labels, no sequence enforcement). The list is a simple reorderable roll of component recipes.
- **Versioning**: Meals do **not** auto-version in v1 (Epic 4's `recipe_versions` pattern is not mirrored). If a user edits which recipes are in a Meal, the change is in-place. Revisit only if users ask.
- **Share tokens**: Meals get a `share_token` column mirroring Recipe, with a matching public-link page at `/share/meal/{token}`. Public viewers see the Meal's name, description, and component recipe names; tapping a component follows existing public-recipe rules (opens only if that component is individually public-shared).
- **Recurrence**: `meal_recurrence_rules` gets the same dual `meal_id` / `recipe_id` treatment. Users can schedule "Kale Salad Meal every Monday dinner" using the existing repeats UI.
- **Archive / restore**: Meals follow the `archived_at` soft-delete convention. Archiving a book archives its Meals. Archiving a component recipe does **not** archive Meals that reference it — the component is hidden in read surfaces instead.
- **Bulk create**: on the recipe-book screen, the existing multi-select mode (today: bulk archive / move / copy) gains a new **"Create Meal from selected"** action when ≥2 recipes are selected. This is the primary fast-path for existing libraries. The standalone "New Meal" create flow is the secondary path for fresh meals.

### New Functional Requirements

- **FR-MEAL-1** — A Meal is a first-class resource with: `id`, `name` (required), `description` (optional), `recipe_book_id` (required FK to `recipe_books`), `share_token` (optional), `archived_at`, plus the standard `created_at`/`updated_at`. A Meal has **two or more component recipes** attached via a `meal_recipes` join table (`meal_id`, `recipe_id`, `order_index`, `created_at`). A Meal with fewer than 2 components is a degenerate state the backend rejects at create/update; the UI enforces the 2+ rule before enabling Save.
- **FR-MEAL-2** — Component recipes on a Meal can reference any recipe the user can **read** at the time of attachment (owned recipe or recipe in a book they have `recipe_book_user` access to), not just recipes in the Meal's own book. If a component recipe later becomes unreadable (its book is unshared from the Meal's owner), the component is hidden from read surfaces with a muted "Unavailable" placeholder and flagged in the edit surface with "Remove or wait until re-shared." Meals themselves are never deleted as a side-effect.
- **FR-MEAL-3** — Users can create a Meal via two paths: (a) from the recipe-book detail screen's existing multi-select mode — select ≥2 recipes, tap a new **"Create Meal"** action bar button, name the Meal, save; (b) from a new **"New Meal"** button on the book detail screen header — opens a flow that takes a name and a multi-select recipe picker (defaulting to the book's own recipes at top, showing all accessible recipes via search).
- **FR-MEAL-4** — The Meal detail screen reuses the recipe-detail scroll shell (hero-image area, title, description, action bar) and replaces the ingredients/steps sections with a **component-recipes list** — one row per component recipe (thumbnail + name + book-of-origin + cook/prep time), each with tap-to-open-recipe and an overflow menu exposing "Remove from Meal." The hero-image area shows a grid/collage of up to 4 component thumbnails; no separate Meal hero image in v1 (Meals don't carry their own `image_url`). The action bar exposes: Favorite, Plan for Date (opens the existing PlanMealSheet in Meal mode), Add to Shopping List (Sum-within-meal dedupe), Share (public link), Archive, Edit.
- **FR-MEAL-5** — The Meal edit screen supports: rename, edit description, add/remove component recipes (same picker as FR-MEAL-3 path b), reorder component recipes via drag handle. All mutations are atomic on Save; cancel discards.
- **FR-MEAL-6** — The recipe-book detail screen's recipe grid gains a **Meal tile variant**: shown alongside recipes in the same grid, distinguished by a small "N recipes" badge (bottom-right corner of the card) and a subtly different bottom border / background treatment (design polish — does not make the Meal tile feel like a different UI primitive). Tapping a Meal tile opens the Meal detail screen; tapping a Recipe tile opens the recipe detail screen (as today).
- **FR-MEAL-7** — Home screen, search results, favorites, and archive view all surface Meals alongside recipes with the same visual differentiation from FR-MEAL-6 (N-recipes badge). The existing `RecipeCard` widget is extended — not forked — to carry an optional `mealComponentCount` that controls the badge. Meal search matches on the Meal's name/description **and** on any component recipe's name (searching "dressing" finds the "Kale Salad Meal" if its component is "Lemon Dressing").
- **FR-MEAL-8** — The `meal_events` table gains a `meal_id` nullable FK to `meals`, with a check constraint `num_nonnulls(recipe_id, meal_id) <= 1`. The `meal_recurrence_rules` table gains the same `meal_id` nullable FK with the same constraint. Existing rows (with only `recipe_id` set) are untouched by the migration.
- **FR-MEAL-9** — The plan-meal sheet (`plan_meal_sheet.dart`) gains a segmented control at the top of the recipe-picker row: **Recipe** (today's behavior) / **Meal**. When "Meal" is selected, the autocomplete searches the user's accessible Meals (owned + via shared books) instead of recipes. All other fields (date, meal_type, calendar, recurrence) behave identically. The resulting meal_event has `meal_id` set and `recipe_id` null. Free-text entry is only available in the Recipe mode.
- **FR-MEAL-10** — The calendar grid renders a meal_event with `meal_id` set as **"MealName (N recipes)"** with a small stack icon (e.g., `Icons.layers`), distinguishing it from single-recipe cards. Tapping opens the meal detail sheet (not the Meal detail screen directly — the existing meal detail sheet is the editorial surface for a scheduled meal). The meal detail sheet exposes an "Open Meal" deep-link to the Meal detail screen, alongside the existing "Open Recipe" path (which now shows a chooser when there are 2+ components: "Which recipe?").
- **FR-MEAL-11** — The day-detail sheet (`day_detail_sheet.dart`) renders meal_events with meals inline the same way the grid does — "MealName (N recipes)." Recurrence visuals (the existing "Recurring" badge from FR77) continue to apply whether the attached thing is a recipe or a meal.
- **FR-MEAL-12** — "Add ingredients to shopping list" from a meal_event with `meal_id` set expands to all component recipes' ingredients, with **sum-within-meal dedupe**: if two components both specify 1 tbsp olive oil, the shopping list gets one line item for 2 tbsp olive oil, not two line items. The existing per-meal_event separation across different events is preserved (Monday and Wednesday remain separate line items). The existing `PopulateFromCalendarRange` endpoint is extended to handle the meal expansion; its shape is unchanged.
- **FR-MEAL-13** — A Meal can be scheduled recurring via the existing repeats UI. `meal_recurrence_rules.meal_id` is set in place of `recipe_id`; materialization produces meal_events with `meal_id` set. The recurrence-rule manage screen (Profile → Recurring Plans) renders rule rows for Meals as "Every Monday dinner · Kale Salad Meal (2 recipes)".
- **FR-MEAL-14** — Meals can be made publicly shareable via a `share_token` column mirroring `recipes.share_token`. A new public-link page at `/share/meal/{token}` renders the Meal's name, description, and component recipe names. Tapping a component follows the existing public-recipe rules: opens only if that component has its own `share_token`; otherwise shows a "Sign in to view" prompt. The share sheet on the Meal detail screen exposes **Copy Link** and **Native Share** actions, paralleling the Recipe share sheet.
- **FR-MEAL-15** — New MCP tools for the AI assistant: `create_meal(name, description, recipe_ids, book_id)`, `get_meal(meal_id)`, `list_meals(book_id?)`, `add_recipe_to_meal(meal_id, recipe_id, order_index?)`, `remove_recipe_from_meal(meal_id, recipe_id)`, `update_meal(meal_id, name?, description?)`, `archive_meal(meal_id)`. The existing `create_meal_event` tool is extended to accept `meal_id` as an alternative to `recipe_id` (exactly one must be provided). MCP auth inherits the existing recipe-book member check for all mutations.
- **FR-MEAL-16** — The admin dashboard's existing Recipes panel gains a **Meals** sub-panel showing total Meal count, active vs. archived count, top books by Meal count, and most-scheduled Meals (by `meal_events.meal_id` count) over the last 30 days. No new endpoints beyond an extension of the existing admin stats endpoint.

### New Non-Functional Requirements

- **NFR-MEAL-1** — Meal list endpoints (`GET /v1/recipe-books/{book_id}/meals`, `GET /v1/meals`) load within 300ms at P95 for a book with up to 100 Meals, with eager-loaded component-recipe summaries (not full recipe payloads — just `id`, `name`, `image_url`, `prep_time`, `cook_time`). No N+1 on the component recipes.
- **NFR-MEAL-2** — Creating a Meal and attaching 10 component recipes is a single transaction. The API response returns the full Meal with embedded component summaries, enabling the Flutter client to render the detail screen without a follow-up fetch.
- **NFR-MEAL-3** — The recipe search path (FR-MEAL-7) supporting component-recipe-name matching adds no more than 15% P95 latency to the existing search endpoint. Implementation uses the same trigram/semantic search infra already covering `recipes.name`; Meals are joined to their components and the search predicate ORs across Meal name and component names.
- **NFR-MEAL-4** — Shopping-list population (FR-MEAL-12) on a meal_event with a Meal containing up to 6 component recipes each with up to 20 ingredients completes within 250ms at P95 — bounded by the same query patterns as the existing recipe expansion. Sum-within-meal dedupe is a single pass over component ingredients in Python; no SQL-level dedupe.
- **NFR-MEAL-5** — API coverage for the new Meal resource hits 100% on the existing `services/api` coverage bar (CLAUDE.md principle). New endpoints have happy-path, auth-failure, not-found, component-unavailable, and transaction-rollback branches covered.
- **NFR-MEAL-6** — The migration adding `meals`, `meal_recipes`, `meal_events.meal_id`, and `meal_recurrence_rules.meal_id` runs in under 10 seconds on a prod-sized DB (user count ≤ 50). It is idempotent: re-running after a successful run is a no-op. The check constraints on meal_events and meal_recurrence_rules are validated without rewriting existing rows (`NOT VALID` + `VALIDATE CONSTRAINT` pattern if needed).
- **NFR-MEAL-7** — No new AWS resources are introduced (confirmed by infra research). The feature is CRUD + joins + endpoint additions only; deploy is the standard `npx nx run api:docker-build` + `npx nx run migrator:docker-build` path.
- **NFR-MEAL-8** — Zero regression on the existing calendar, shopping-list, and recurring-meals features. Existing meal_events with `recipe_id` set and `meal_id` null behave identically to today. Existing `PopulateFromCalendarRange` and `ListMealEvents` endpoints return the same shape for recipe-only callers; new `meal_id` / `meal_summary` fields are additive on the response only.

### Explicitly Out of Scope for This Addendum

- **AI-suggested pairings** ("you added a Lemon Dressing, want to pair with …") — deferred to a follow-up epic. v1 combining is manual only.
- **Combined cooking mode for a Meal** — deferred. v1 user opens component recipes individually from the Meal detail screen.
- **Meal versioning** — no parallel to `recipe_versions`. Meal edits are in-place.
- **Courses / ordering UX** (starter → main → dessert). `meal_recipes.order_index` persists user-chosen order but no course labels or sequence enforcement in v1.
- **Meal hero image / dedicated Meal photo**. Collage of up to 4 component thumbnails is the v1 visual. Revisit if users ask.
- **Nested Meals** (a Meal containing another Meal). Explicitly rejected in the domain research — users don't ask for it and it's a modeling trap.
- **Per-component servings reconciliation / cross-component scaling**. Each component recipe retains its own `servings` and scales independently via the existing recipe-detail scale control. A single Meal-level scale control is a nice-to-have for later.
- **Meal-level notifications** (e.g., "prep-start" on a Meal with 3-hour marinade). Existing meal_event prep/cook notifications apply at the meal_event level, not per component. Revisit if users ask.
- **Meal fork lineage / "forked from this Meal"** parallel to `recipes.forked_from_recipe_id`. Not needed for v1.
- **Public Meal explore surface / algorithmic Meal feed**. Share-link access only; no public browse.
- **Backend-enforced component limit beyond 2+**. No upper bound in v1; NFR-MEAL-1 / NFR-MEAL-4 implicitly bound by typical use.



---

## Addendum — 2026-04-18 — Calendar Shopping: Per-Meal Add Pivot

### Context

The calendar AppBar today exposes **"Add week to shopping list"** — a single tap that calls `POST /v1/shopping-lists/{list_id}/populate-from-calendar` with the visible week's date range and dumps every ingredient from every planned meal in that range into one list. In dogfood use this surface produced 12 garbage line-items with raw-string names like *"1 recipe pasta dough, rolled out into wide ribbons, about 1/4-inch thick"* because `ingredients.canonical_name` is sometimes populated with a raw recipe line instead of a canonical ingredient. The underlying `canonical_name` data bug is **out of scope** here and tracked separately; this addendum pivots the UX so that the bulk amplifier is gone and users opt in to individual meals.

### Pivot

- **Remove** the bulk "Add week to shopping list" AppBar action, its handler, the Flutter client method (`populateFromCalendarRange` on `ShoppingCartService`), the `api_client.dart` wrapper (`populateShoppingListFromCalendar`), the backend endpoint `POST /v1/shopping-lists/{list_id}/populate-from-calendar`, its impl module `services/api/src/api/v1/shopping_list/populate_from_calendar.py`, its `__init__.py` export, the dedicated test file, and the `TestPopulateFromCalendarExtended` class from `test_coverage_gaps.py`. Update `docs/SHARED_SHOPPING_CART.md` accordingly.
- **Add** a visible per-meal `Icons.add_shopping_cart_outlined` icon button on every calendar-grid meal card **when `event.recipe != null`** (hidden otherwise, matching how the row's existing chevron is gated). The button reuses the existing `_addIngredientsFromEvent` handler (default-list resolution + optional chooser sheet + `populateFromRecipe` call + snackbar with "Added N ingredients to \<list\>") — no logic duplication.
- **Post-add indicator** (session-persistent until reschedule): after a successful add, the card's icon replaces with `Icons.check` in a muted tone; persists in client-side state keyed by `event.id` until the grid reloads (`_loadEvents()` is already called on reschedule, on week navigation, on tab re-entry, on active-calendar change). No backend flag; no new migration. Accessibility: the card's `Semantics` label flips to "Already added to shopping list" when in the added state.
- **Unchanged**: `POST /v1/shopping-lists/{list_id}/populate-from-recipe`, the default-list selection + chooser flow, and the long-press action sheet's existing "Add to shopping list" entry (which stays as a secondary path).

### Functional Requirements (addition)

- **FR-CPMS-1** — The calendar AppBar exposes no shopping-list action. Only per-meal adds are possible from the grid. The backend endpoint `POST /v1/shopping-lists/{list_id}/populate-from-calendar` is removed and returns `404` after deploy.
- **FR-CPMS-2** — Every meal-event card in the week grid renders a tap-target `Icons.add_shopping_cart_outlined` icon button when the event has a linked recipe (`event.recipe != null`). The icon sits inside the card row adjacent to the existing chevron; tapping it does NOT propagate the row's existing `onTap` (which opens the meal detail sheet) or `onLongPress` (which opens the action sheet). Icon is hidden (not disabled-grey) when `event.recipe == null` to match the chevron's existing visibility rule.
- **FR-CPMS-3** — Tapping the icon invokes the existing `_addIngredientsFromEvent(event)` flow verbatim: resolves the user's default shopping list, opens a chooser sheet only when there is no default and >1 list, calls `populateFromRecipe(listId, event.recipe!.id)`, and shows the existing snackbar with item count + list name. No duplicated logic path.
- **FR-CPMS-4** — After a successful add, the card's icon swaps to `Icons.check` (muted tone) and stays that way for the remainder of the session until the grid reloads via `_loadEvents()`. Reloads fire on: reschedule, unschedule, week navigation, tab re-entry, active-calendar switch, pull-to-refresh. An "added" card that the user then reschedules returns to the un-added state when the grid repopulates.
- **FR-CPMS-5** — The card's `Semantics` node updates in the added state: label reads "Already added to shopping list" and the icon button's `tooltip` updates to the same. Tapping an already-added card re-runs the add flow (no guard); the icon re-renders as checked after the second snackbar — the user explicitly overrides their own "done" state by tapping again.
- **FR-CPMS-6** — The long-press action sheet's existing "Add to shopping list" entry at `calendar_screen.dart:518–526` is unchanged. It also invokes `_addIngredientsFromEvent`. If a user uses the long-press path, the card's session-persistent "added" indicator still flips — both entry points share the same success-state update (the `_addedEventIds` Set is updated inside `_addIngredientsFromEvent`, not at the tap site).
- **FR-CPMS-7** — Meals-calendar epic reconciliation (cross-epic): story **`mcal-4-backend-populate-from-calendar-meal-expansion-load-bearing`** in `epic-meals-calendar` is marked `deleted` in `sprint-status.yaml`. That epic's shopping-list expansion for Meals (FR-MEAL-12) will route through a per-Meal add path instead — either an extension of `populate-from-recipe` to accept a `meal_id`, or a new `populate-from-meal` endpoint with sum-within-meal dedupe. `epic-meals-calendar.md` is updated with a dated note pointing here. FR-MEAL-12 is **not retracted** (Meals still dedupe sum-within-meal on add to shopping list), only its transport path changes.

### Non-Functional Requirements (addition)

- **NFR-CPMS-1** — `services/api` coverage stays at 100% after the deletion (memory: coverage pinned at 100%). Coverage verification: deleting the source file and its tests together is neutral; CI coverage run after the change must pass with the `pyproject.toml` fail-under threshold intact.
- **NFR-CPMS-2** — No new AWS resources, no new migrations, no new env vars. Deploy is the standard `npx nx run api:docker-build` + Flutter release path. Existing shopping-list data and existing meal-event data are untouched.
- **NFR-CPMS-3** — The per-card icon adds zero new network calls on grid render (the added-state check is a pure client lookup on an in-memory Set). Adding a meal is one existing network round-trip (`populateFromRecipe`) — identical to today's long-press path.
- **NFR-CPMS-4** — No WebSocket changes. The existing `broadcast_event_to_list` event for `item_added` (in the `populateFromRecipe` router handler) continues to fire once per add; removing the bulk endpoint also removes its per-item broadcast loop, which is net-positive (less socket traffic).

### Non-Goals (this epic)

- **Not fixing the `canonical_name` data bug.** Raw-string line items will still appear in per-meal adds when the underlying ingredient row has a raw-string `canonical_name`. That bug is tracked separately. This epic reduces the blast radius (12 → 1 meal's worth) and gives the user intentional control over which meals to shop for, which is enough for dogfood.
- **No server-persistent "added to shopping list" flag.** The indicator is client-only, session-scoped, cleared on grid reload. A server-side `last_added_to_list_at` column was considered (Q1 option D) and explicitly rejected as out-of-proportion.
- **No bulk-select re-introduction in any other form.** If the user wants to shop for three meals, they tap three icons. No "select all" / "select range" UX in v1.
- **No change to the shopping-list side** of the UX — the list screen, the "Add item" flow, the websocket sync all continue to work as today.
- **No backend migration.** The endpoint and its tests are deleted cleanly; `meal_events` schema is unchanged.

### Locked decisions

1. **Per-card icon is always visible** (not hover-only / not tap-to-reveal) when `event.recipe != null`. Discoverability is the point.
2. **Hidden, not disabled-grey**, when no recipe is linked. Matches the existing chevron's conditional visibility.
3. **Session-persistent "added" check** (Q1 option C, confirmed 2026-04-18). Client-only `Set<String> _addedEventIds`; cleared on `_loadEvents()`. No new column, no new endpoint, no cross-device sync.
4. **Long-press action sheet path stays** and shares the same success-state update with the icon tap.
5. **Endpoint deletion is load-bearing on the meals-calendar epic's mcal-4** being replanned. Updated in the same addendum (Q2 option α, confirmed 2026-04-18).
6. **No backwards-compat shim / no deprecation period** on the endpoint. It goes from the codebase in one deploy — consistent with project rules on "don't leave dead code."

## Addendum — 2026-04-20 — Cook Mode Polish & Timer Autodetection

### Context

Dogfood pass of **Cook Mode** (Epic 6, shipped 2026-Q1) surfaced three distinct UX regressions and one dormant feature:

1. **Color scheme is jarring.** `cook_mode_screen.dart:446` force-applies `AppTheme.dark()` regardless of the app's ambient theme, and the scaffold/header/chat-input row all use `colorScheme.primary` (terracotta) as a **full-surface background** (`cook_mode_screen.dart:454, 503, 574`, `cook_mode_chat_sheet.dart:269`). Material 3 reserves `primary` for accents; using it as a fill colour creates the "everything is orange" effect and a hard theme seam when entering cook mode from a light-themed home screen. Compounded by mixed-register token usage (`colorScheme.*` interleaved with a custom `appColors.*` extension) with no clear role contract.
2. **Completed-step visual bleeds backward.** `_nextStep()` adds `_currentStep` to `_completedSteps` before advancing (`cook_mode_screen.dart:229`); `_goToStep()` never removes it (`:219`). Result: navigating back to a prior step renders it with line-through text, 0.6-alpha dimming, and a green checkmark border (`:810–823`) — directly contradicting the user's mental model ("I went back because I forgot something").
3. **Timer autodetect is one regex on the client, and it misses most cases.** `cook_mode_screen.dart:742` — pattern `(\d+)\s*(min|sec|hour)…` with `.firstMatch()`. No ranges (`3–5 min`), no decimals (`0.5 hour`), no multi-timer steps. Users have no escape hatch when it doesn't fire.
4. **Dormant backend timer column.** `recipe_step.timers` (JSONB) exists (`libraries/utils/utils/models/recipe_step.py:30`) and is wired all the way through the API response (`services/api/src/api/v1/recipe/get_recipe.py:66–79`), but **no extractor populates it**. `ExtractedStep` has only `order` + `instruction` (`libraries/utils/utils/services/recipe_extractors/base.py:20–31`); the LLM prompt doesn't request per-step durations (`ai_extractor.py:35–95`). Infrastructure built 2026-01-29 (commit `4f52574`), never filled in.

Kept in scope (explicit keep-as-is): **ingredient toggle strip** (`ingredient_strip.dart`) — the user called it out as "pretty sweet, very helpful." The compact/expanded cross-fade, check-animation, and `appColors.success` highlight are the reference pattern for "completed" visuals in the polished cook mode.

### Pivot

- **Cook mode becomes theme-aware.** Remove the forced `AppTheme.dark()` wrap in `cook_mode_screen.dart:445–568`. Cook mode inherits the ambient app theme (light, dark, or system) and applies a **single cohesive palette** derived from that theme via a new `CookModeTheme` `ThemeExtension` ("cookSurface", "cookOnSurface", "cookAccent", "cookProgress", "cookCompleted", "cookTimer"). No more `colorScheme.primary`-as-background anywhere.
- **Step completion is explicit, not incidental.** Navigating back via `_goToStep()` (swipe-right, tap-left-zone, or StepNavigator pill tap) **removes the target step from `_completedSteps`**. Forward navigation (`_nextStep()`) continues to mark the departing step complete. `_markAllUpToHere()` is unchanged. `_finishCooking()` still adds the last step. Net result: the "completed" pill/visual only shows for steps the user has walked past.
- **Timer autodetection is hybrid, with a manual escape hatch.**
  - **Backend primary.** LLM extractor (`services/worker/` + `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`) emits `timers: [{duration_minutes: int, label: str}]` per step as part of the extraction schema. `ExtractedStep` gets a `timers` field; `create_recipe_task` persists it; eval fixtures + the `RecipeExtractionEvaluator` are extended.
  - **Frontend fallback.** When `step.timers` is empty/null, `cook_mode_screen.dart` runs an **upgraded** regex that supports: multiple matches per step (one button per timer), ranges (`3-5 min` → use lower bound by default, surface upper as label context), decimals (`0.5 hour` → 30 min), and a small alias table (`h/hr/hrs`, `m/mins`). Still strictly fallback — backend wins when it has data.
  - **Manual escape hatch (always available).** A `Icons.timer_outlined` icon in the cook-mode header (between the AI-chat button and the cooking-time pill) is always tappable, regardless of whether extraction or regex fires. Tap opens a small bottom sheet — numeric duration + optional label — that calls the existing `_startTimer(Duration, String)` path verbatim. Same active-timers row, same notifications, same `CookTimerNotificationService`.

### Functional Requirements (addition)

#### Visual polish (cook-mode-polish epic)

- **FR-CMP-1 — Cook mode inherits app theme.** The forced `Theme(data: AppTheme.dark(), …)` wrap is removed. Cook mode reads `Theme.of(context)` and renders correctly in light, dark, and system-dark modes. There is no user toggle "force dark in cook mode" in v1.
- **FR-CMP-2 — `CookModeTheme` ThemeExtension defines the palette contract.** Lives in `app/lib/core/theme/cook_mode_theme.dart`. Exposes at minimum `cookSurface`, `cookOnSurface`, `cookAccent`, `cookProgress`, `cookCompleted`, `cookTimer`. Registered on both `AppTheme.light()` and `AppTheme.dark()` in `app_theme.dart`. Every `colorScheme.primary` / `colorScheme.tertiary` / `appColors.success` reference inside `cook_mode/**` is replaced with the appropriate `CookModeTheme` token. No direct Material role usage for backgrounds in cook mode after this epic.
- **FR-CMP-3 — Scaffold, header, step-content card, and active-timers pill use `cookSurface` (not `primary`).** The previous `colorScheme.primary` background at `cook_mode_screen.dart:454, 503, 574` is gone. Accents (progress bar fill, timer ring/border/text, inline "Set timer" button) use `cookAccent` / `cookTimer`. Completed step indicators use `cookCompleted` instead of `appColors.success`.
- **FR-CMP-4 — Chat sheet input row aligns with sheet background.** `cook_mode_chat_sheet.dart:269` stops using `colorScheme.primary` as the input-row background; uses `cookSurface` (matching the sheet) with a thin `cookAccent` focus outline on the text field instead. Send button keeps the filled-accent affordance.
- **FR-CMP-5 — Completed step untoggles on back-navigation.** `_goToStep(step)` removes `step` from `_completedSteps` **when `step < _currentStep`** (i.e., navigating back). Forward nav still adds the departing step via `_nextStep()`. Swipe-right, left-zone tap, and StepNavigator pill-tap all route through `_goToStep` so all three paths get the untoggle. `_markAllUpToHere()` semantics unchanged.
- **FR-CMP-6 — StepNavigator pill reflects the set, not the index.** A pill renders as "completed" (`cookCompleted` fill + check icon) iff its index is in `_completedSteps`. A pill renders as "current" iff its index `== _currentStep`. The current pill never renders as completed even if the set still contains it (belt-and-braces for FR-CMP-5).
- **FR-CMP-7 — Ingredient toggle strip is untouched, except for token migration.** `ingredient_strip.dart` behaviour (compact/expanded cross-fade, haptic on toggle, `appColors.success` highlight on checked ingredients) is preserved. Only colour tokens swap to `CookModeTheme` (`cookCompleted` for checked, `cookAccent` for counter). No layout, no animation, no interaction changes.

#### Timer extraction + manual entry (cook-mode-timers epic)

- **FR-CMT-1 — Extractor schema emits per-step timers.** The LLM extraction schema (`libraries/utils/utils/schemas/recipe_extraction_schema.py`) gains a `timers` field on each step: `list[{duration_minutes: int, label: str}]`. Default `[]`. Prompt (`ai_extractor.py`) explicitly instructs the model to extract **actively tended** durations (simmer 10 min, bake 25 min) and label them; `label` falls back to the salient verb from the instruction. Passive "rest overnight" / "marinate 4+ hours" are **excluded** (they become recipe-level wait time, not in-cook timers).
- **FR-CMT-2 — `ExtractedStep` + `create_recipe_task` persist timers.** `ExtractedStep` dataclass (`libraries/utils/utils/services/recipe_extractors/base.py`) gains `timers: list[dict]` with a default factory. `create_recipe_task.py:137–142` writes `timers=step.timers` when constructing `RecipeStep`. Validation rejects negative or >360-minute durations (out-of-band; clamp + log a `service="api"` error row rather than fail the whole import).
- **FR-CMT-3 — Eval fixtures + RecipeExtractionEvaluator cover timers.** At least 3 existing `services/eval/fixtures/expected/*.json` fixtures are extended with ground-truth `timers` per step, chosen to exercise: single timer, multiple timers in one step, and no-timer steps. A new `timer_extraction_f1` metric joins the evaluator with a soft gate at ≥0.7 (soft — not a hard merge block in v1; measured and surfaced on the eval dashboard).
- **FR-CMT-4 — Frontend prefers `step.timers` over regex.** In `cook_mode_screen.dart`, `_buildStepContent` replaces its current single-regex path with: if `step.timers` is non-empty, render one `OutlinedButton.icon` per entry using `duration_minutes` + `label`; else run the upgraded regex and render one button per regex match.
- **FR-CMT-5 — Upgraded frontend regex.** Replaces the current `firstMatch`-only regex. Supports: (a) multiple matches per step (returns all via `allMatches`, up to 4 rendered — more collapsed behind a "+N more" chip); (b) ranges `\d+\s*(?:-|–|—|to)\s*\d+\s*(min|hour|sec)` → lower bound as timer, upper bound in the label (e.g. "Set 3 min timer (up to 5)"); (c) decimals (`0.5 hour` → 30 min; `1.5 hr` → 90 min); (d) alias tokens (`h/hr/hrs/hour/hours`, `m/min/mins/minute/minutes`, `s/sec/secs/second/seconds`). Returns empty list (not first-match) when nothing recognised.
- **FR-CMT-6 — Always-visible manual timer button.** A `Icons.timer_outlined` IconButton lives in the cook-mode header row (`cook_mode_screen.dart` `_buildHeader`), positioned between the AI chat button and the cooking-time pill. Visible in online and offline modes; visible regardless of whether the current step has extracted/regex timers. Tap opens a new `ManualTimerSheet` bottom sheet: numeric keypad for minutes (1–360), optional short label (default "Timer"), "Start" button. Starts the timer via the existing `_startTimer(duration, label)` path. Accessibility: min 48×48 tap target, `Semantics` label "Add a timer".
- **FR-CMT-7 — Active timers row is the same regardless of source.** Timers started from extracted metadata, from regex, or from manual entry all land in the same `_activeTimers` list, share one `_ActiveTimer` type, one notification path (`CookTimerNotificationService`), one detail sheet (`_TimerDetailSheet`), and the same haptic/snackbar on completion. There is no visible "source" badge — the user can't tell whether a timer came from extraction or manual entry, and that's intentional.
- **FR-CMT-8 — No backfill of existing recipes.** Recipes imported before FR-CMT-1 ships keep `step.timers = []`. The frontend regex fallback handles them; users can always use the manual button. A backfill pass is explicitly deferred — not a v1 scope item.

### Non-Functional Requirements (addition)

- **NFR-CMP-1 — Zero visual regression on Epic 6 acceptance criteria.** Offline cooking mode (FR28), gesture navigation (FR27, Story 6.2), concurrent timers with background notifications (FR26, Story 6.3), post-cook feedback (FR29, Story 6.5) all continue to work — Story-6.* widget-test suite must pass unmodified. A new `CookModeTheme` golden test covers both light and dark palettes side-by-side.
- **NFR-CMP-2 — Theme switching is seamless.** Entering cook mode from a light-themed home screen produces a light cook mode; entering from dark produces dark. No flash, no double-paint. `dispose()` does not need to restore a parent theme since there is no wrapping `Theme(…)` after FR-CMP-1.
- **NFR-CMT-1 — Extractor cost envelope.** Per-recipe LLM cost delta from the `timers` schema addition is under $0.0005 in the current eval corpus. Measured on one full eval run before/after prompt change; surfaced in the addendum's epic retrospective.
- **NFR-CMT-2 — Latency envelope.** Import pipeline end-to-end latency is unchanged within noise (no new LLM calls; single-pass schema change). `obs-latency` dashboards before/after the change remain in the same p95 bucket for `task=extract_recipe`.
- **NFR-CMT-3 — Coverage stays at 100% on `services/api`.** Schema + `create_recipe_task` changes come with tests; the new `timer_extraction_f1` metric has a unit test with a stub evaluator.
- **NFR-CMT-4 — Manual timer entry is offline-safe.** The manual timer button works with no network. Starts a client-side timer via `_startTimer`, schedules the OS notification via `CookTimerNotificationService`, and does not call the API.

### Non-Goals (this epic bundle)

- **No user preference for cook-mode theme.** Cook mode follows the app theme. A "force dark in cook mode" toggle is deferred.
- **No ML model for "is this a timer" disambiguation.** Extraction relies on the LLM's prompt compliance; fallback is regex. We do not ship a classifier.
- **No backfill job for existing recipes.** See FR-CMT-8. Frontend regex + manual button cover the gap.
- **No passive-wait-time UI.** Recipe-level "marinate 4 hours" does not become a timer chip or a recipe-level warning in v1. The extraction prompt excludes these explicitly, but we do not invent new UI around them.
- **No timer editing** (reschedule, rename, change duration of an already-running timer). Only cancel + restart, as today.
- **No cross-device timer sync.** Timers are single-device, as today.
- **No audit on `_markAllUpToHere`.** That path remains a deliberate bulk-complete. It is not touched by FR-CMP-5.

### Locked decisions

1. **Q1 = Hybrid + manual escape hatch** (2026-04-20). Backend extraction primary, upgraded frontend regex fallback, and an always-visible manual timer button regardless of either. Users never get "stuck" with no timer option.
2. **Q2 = Full theme-awareness** (2026-04-20). Cook mode honours the app theme; no forced dark, no forced anything. Palette contract lives in a dedicated `CookModeTheme` `ThemeExtension`, not scattered across `colorScheme.*` / `appColors.*` usage.
3. **Q3 = Untoggle on back** (2026-04-20). `_goToStep(step)` with `step < _currentStep` clears `step` from `_completedSteps`. Forward nav is unchanged. StepNavigator pills render from the set, so they update automatically.
4. **Q4 = No backfill** (2026-04-20). Regex + manual button cover legacy recipes. A one-shot backfill script remains possible later but is not in this scope.
5. **Ingredient toggle strip is locked behaviour.** Only token migration; no interaction or layout change. Flagged explicitly because it's the one thing the user called out as working well.
6. **Two independent epics, parallelisable.** `epic-cook-mode-polish` (Flutter-only) and `epic-cook-mode-timers` (full-stack). No ordering dependency between them — polish doesn't read `step.timers`, timers work doesn't require the new theme extension. Both can ship in any order.

---

## Addendum — 2026-04-20 — Activity Hub: badge integrity + full history

### Context

Epic `activity-hub-redesign` (2026-04-18) shipped the two-tab Activity shell (Notifications / Imports), four-color-section Imports tab, swipe-to-archive, and See-all footer for archived + >30d completed imports. Epic `import-row-rich-detail` (2026-04-18) shipped caret expansion with stage timeline, confidence, raw parse preview, and retry history. Both are now done.

In dogfood use, Leo reported two concrete defects:

1. **Bell-count drift.** The bottom-nav Activity badge shows a number that the Notifications tab body doesn't account for. Root cause (verified): the unread-count endpoint at `services/api/src/api/v1/user_activity/unread_count.py:15-23` has no type filter and no 30-day window, so it counts `import_started / import_complete / import_needs_review / import_failed / partner_action` rows; the Notifications tab client-side filters to `{invitation, partner_action, meal_reminder}` (two of which are never actually created today). Result: badge says N, Notifications list shows ≪N. Additionally, `importsActionableBadgeProvider` (in `app/lib/features/activity/providers/`) computes the imports-side count but is never consumed — the "ahr-7 wires the bottom-nav end" comment in-code acknowledges this was not finished.
2. **History gap.** "All Set" is a friendly empty state but a dead end — there is no path from the Notifications tab to previously-read or archived items. The Notifications tab fetches `?limit=50` once, filters client-side, and that's all. Imports tab has a See-all footer but is capped at `limit=100` and has no pagination.

User ask (verbatim): "I want to figure out what's going on with activities. We see a number in the activity bell that is not shown in the actual UI. Also I want the ability to see ALL activity. I see 'All Set' which is great, but then I want to see historical information. Both in imports and notifications. Second, I want to see all imports in the import hub. If I just started one, I want to see it and its status, what stage it's at … if it auto completed successfully (and then give me a dismiss to remove it there as well), and if it failed with a dismiss and a retry flow. The biggest thing here is that I want to always be able to see my imports at some point."

### Pivot

- **One combined bell number, formula-locked.** Bell badge = `unread_notifications_count + actionable_imports_count` where actionable = in-progress + needs-review + failed (green / auto-imported excluded, matching the Imports tab badge formula already in ahr-2 AC5). The two summands are independent server calls; the badge sums them client-side so the bell never disagrees with the tab badges' sum.
- **Notifications tab gets a See-all footer** symmetric with the Imports tab. Archived + read + >30d rows land behind `See all (N)`. Pagination lazy-loads older pages on scroll, unbounded in depth.
- **Imports tab See-all becomes unbounded.** The current hardcoded `limit=100` is replaced with lazy pagination on the See-all list. Default 4-section behavior unchanged.
- **Bell tap destination is context-aware.** Tapping the bottom-nav Activity tab opens whichever tab has more unread/actionable items; ties go to Notifications (current cold-start default). Push-payload deep-links continue to force the referenced tab.

### Functional Requirements (addition)

#### Badge integrity (activity-badge-integrity epic)

- **FR-ABI-1 — `unread-count` endpoint returns a structured payload.** `GET /v1/activities/unread-count` response changes from `{count: int}` to `{notifications: int, imports_actionable: int}`. `notifications` counts user_activity rows where `user_id = me AND read = false AND archived_at IS NULL AND type IN (<visible-in-Notifications-tab types>)` AND `created_at >= NOW() - INTERVAL '30 days'` (matches list endpoint window). `imports_actionable` counts distinct import_items where `user_id = me AND archived_at IS NULL AND dismissed_at IS NULL AND status IN ('pending','processing','extracting','matching','awaiting_parser','awaiting_review','failed')`.
- **FR-ABI-2 — Backward-compat wrapper ships in same release.** The old `{count: int}` shape is preserved for one release as `count = notifications + imports_actionable` so any out-of-date clients don't break. Deprecated marker in the endpoint docstring; removal scheduled one release after the Flutter client is on the new shape.
- **FR-ABI-3 — `user_activity.type` column has a documented allow-list.** The set of types the Notifications tab shows is codified in one place (`libraries/utils/utils/models/user_activity.py` — new `NOTIFICATION_TAB_TYPES` module constant) and both `unread-count` and `list_activities` read from it. Today's membership: `partner_action`. Future additions (e.g. `invitation`, `meal_reminder` if those ever get wired up) require updating the constant only; no endpoint changes.
- **FR-ABI-4 — Bottom-nav badge formula is the sum.** Flutter `scaffold_with_bottom_nav.dart` reads BOTH `notifications` and `imports_actionable` from the new payload and renders the sum. `ActivityReadProvider` is extended to expose both, or split into two providers; either is fine. The orphan `importsActionableBadgeProvider` is either wired in or deleted (no dead code left behind).
- **FR-ABI-5 — Tap on bottom-nav Activity opens the tab with more items.** If `imports_actionable > notifications`, initial tab is `imports`; otherwise `notifications`. Tie → `notifications`. Only applies to taps *without* an explicit `?tab=` query param; push-payload deep-links that already encode `?tab=imports` continue to win.
- **FR-ABI-6 — `import_*` activity rows are no longer created for items that are already visible in the Imports tab.** Auditing `start_import.py:431`, `create_recipe_task.py:342`, `match_ingredients_task.py:149`, `extract_recipe_task.py`, `sweep_stuck_imports.py`: these insert `user_activities` rows only to drive push notifications. Under FR-ABI-3 those types are no longer surfaced in the Notifications tab (they're out of the allow-list) and no longer bump the notifications count. They still drive push dispatch. Remove the dead DB writes for types that the push-dispatch layer doesn't read — single source of truth for "is this import unseen?" is the import_item itself, not a parallel user_activity row.
- **FR-ABI-7 — Badge cannot go negative, cannot desync.** Regression coverage: seed N actionable imports + M unread notifications; open Activity; badge reads N+M; open Imports tab; actionable imports badge reads N; open Notifications tab; notifications badge reads M; N + M still equals the bottom-nav number throughout. Archive-an-import reduces the bottom-nav number by 1 within the next poll window (30s) OR immediately via optimistic local update, whichever is faster.

#### Full history (activity-full-history epic)

- **FR-AFH-1 — `GET /v1/activities` supports `include_read=<bool>` + `include_archived=<bool>` + `since_days=<int|null>` + cursor pagination.** Defaults stay backward-compatible (`include_read=false` effectively — via `since_days=30` window and current client behavior). Pagination uses an opaque `cursor` param (the epoch-ms of the oldest row on the previous page, URL-safe-base64 encoded, with a `|id` tiebreaker for same-timestamp collisions — `{created_at_ms}|{id}` base64'd). `limit` clamped at 100. `since_days=null` removes the window entirely. `Link` header with `rel="next"` on responses when more pages exist.
- **FR-AFH-2 — `GET /v1/import-items` and `GET /v1/import-jobs` support the same cursor pagination.** The existing `limit`/`offset` are kept for backward compat, but new callers use `cursor` instead. Flutter's See-all footer migrates to cursor on both tabs.
- **FR-AFH-3 — Notifications tab See-all footer.** A new `NotificationsSeeAllFooter` widget mirrors the shape of `SeeAllFooter` (Imports). Collapsed: single row `See all (N) ›` where N is the count of archived + read-and-older-than-30d notifications (new endpoint: `GET /v1/activities/see-all-count`). Expanded: lazy-paginated list of those items rendered with `colorScheme.onSurface.withOpacity(0.65)`, oldest-by-archive-date-then-created-date at the top of each page, more-recent above that. Swipe-right on a See-all row unarchives (symmetric with Imports See-all).
- **FR-AFH-4 — Imports See-all footer becomes paginated.** `SeeAllFooter` in `app/lib/features/activity/widgets/see_all_footer.dart` drops the hardcoded `limit=100`, uses the new cursor pagination, lazy-loads on scroll-to-bottom with a trailing progress indicator. Reaching end-of-list shows a muted "That's everything. (N total)" footer row.
- **FR-AFH-5 — "All Set" becomes a gateway, not a wall.** Notifications tab empty state (`"You're all caught up"`) renders an inline `Text.rich` with `See past notifications` as a tap target that opens See-all directly, if history exists. If the user has zero lifetime notifications (count = 0), the tap target is absent — pure empty state. Same pattern on the Imports tab "All clear — no imports yet" — inline link `See past imports` if lifetime imports > 0.
- **FR-AFH-6 — See-all counts are first-class, not derived.** `GET /v1/activities/see-all-count` returns `{archived: int, older_than_30d: int, total: int}`. `GET /v1/import-items/see-all-count` returns the same triple (completed+archived+older). These are used by the footer "See all (N)" labels so we don't fetch a full list just to compute a count.
- **FR-AFH-7 — Session-persistent "unarchive-then-back-out" works.** Unarchiving a row from See-all (either tab) optimistically moves it into the main list (Notifications tab body or color section), and a 3s "Undo" snackbar rolls back on tap. This behavior already exists for Imports (ahr-5 AC5); FR-AFH-7 generalizes to Notifications too.
- **FR-AFH-8 — Full-history view honors ordering.** See-all Notifications: `ORDER BY archived_at DESC NULLS LAST, created_at DESC` so archived-most-recent comes first, then read-and-old items by age. See-all Imports (already): `archived_at DESC NULLS LAST, created_at DESC` — unchanged.

### Non-Functional Requirements (addition)

- **NFR-ABI-1 — No endpoint regression beyond the v0 shape.** `unread-count`'s old `{count: int}` wrapper must continue to return a non-breaking value for one release. Old clients show a number that is no longer accurate but also is never zero-when-should-be-nonzero (sum still bumps when either summand does). Proved by a Flutter-free API test pinned to the old response contract.
- **NFR-ABI-2 — Partial indexes on the count hot paths.** `user_activities` already has `(user_id, created_at DESC) WHERE archived_at IS NULL` (ahr-1). Add a partial index `(user_id) WHERE read = false AND archived_at IS NULL AND created_at >= NOW() - INTERVAL '30 days'` — not allowed in Postgres (NOW() isn't immutable). Use the existing index and rely on the planner using the `read = false` predicate; assert with `EXPLAIN`. For imports: existing indexes on `(user_id, status)` are sufficient; verify plan with `EXPLAIN` in test.
- **NFR-ABI-3 — Bottom-nav badge update is bounded.** Two HTTP requests per 30s poll at most (one for notifications count, one for imports-actionable count, OR one combined call — combined is preferred). Under 150ms p95 total round-trip on warm cache. Bell number never flickers on refresh (Riverpod debounce 100ms).
- **NFR-AFH-1 — See-all pagination p95 under 200ms.** Cursor-paginated queries against both `user_activities` and `import_items` under 200ms p95 for page sizes ≤100. Index plan verified with `EXPLAIN` in test.
- **NFR-AFH-2 — Client memory bounded.** See-all scroll list windowed via `ListView.builder` with `itemExtent` hinted where possible; memory consumption for a user with 10k archived activities is under 20MB of list state.
- **NFR-AFH-3 — Coverage stays at 100% on `services/api`.** All new endpoints + migrations + removed-dead-code paths ship with tests.
- **NFR-AFH-4 — Accessibility preserved on all new rows.** See-all rows keep 48dp touch targets and carry `Semantics` labels "Archived notification, <title>, dated <relative time>". Tap gesture on `See past notifications` / `See past imports` inline links has min 48dp target via `InkWell` + padding.

### Non-Goals (this epic bundle)

- **No new bottom-nav slot.** Activity remains one tab. No separate "Imports" bottom-nav slot.
- **No redesign of color sections, swipe rules, or import-row collapsed layout.** This bundle is additive to the shipped Activity Hub Redesign, not a rewrite.
- **No cross-device push inbox.** The bell number is per-device from the user's server-side state; multi-device read-state sync is out of scope.
- **No UI for deleting activities or imports.** Archive is the hide mechanism; deletion is not exposed.
- **No per-type notification filter within Notifications tab.** Today the tab shows all non-import types in a single feed; no user-visible filter chips.
- **No audit rows for archive/unarchive.** Matches ahr-1 AC12 — these are user-space mutations, not admin mutations.

### Locked decisions

1. **Q1 = Combined bell number** (2026-04-20). One number in the bottom-nav, sum of unread notifications + actionable imports. Green excluded. Tap opens the tab with more.
2. **Q2 = Unbounded pagination** (2026-04-20). No soft cap on history depth. Cursor-paginated server-side, lazy-loaded client-side.
3. **Q3 = Notifications See-all footer mirrors Imports** (2026-04-20). Same widget shape, same position, same muted typography, same swipe-right-to-unarchive. No separate "History" sub-tab.
4. **Two epics, ordered** (2026-04-20). `epic-activity-badge-integrity` ships first (fixes the user-visible bug in minimal scope). `epic-activity-full-history` builds on it with the See-all footer + pagination + "All Set" gateway UX. No parallelism within this bundle — the second epic reads the new payload shape from the first.
5. **`import_*` user_activity rows are dead weight after FR-ABI-6.** The push-dispatch layer reads the import_item directly today; removing the parallel user_activity inserts simplifies the schema and kills the primary drift vector. Any type currently only used for push and never surfaced in UI is a candidate for deletion.

## Addendum — 2026-04-20 — Ingredient canonicalization retired (`epic-ingredients-string-simplification`)

### Context

After a design re-evaluation, the user decided to retire every piece of ingredient canonicalization / matching / substitution / pantry-check infrastructure that was either (a) not shipping a user-visible feature, or (b) delivering value less valuable than its complexity. The grand plan of "write-time ingredient knowledge graph powering easy replacements" was never wired past a seed script; future similarity, if ever needed, comes from read-time LLM or vector calls, not from a persistent graph.

Three distinct bodies of work are affected:

1. **Scraper service + substitution table** — dead weight. ~2,500 LOC scraper (untouched — user parked for possible future reuse), empty substitution table, unused HNSW index + embedding column. Deleted.
2. **Runtime matcher (pg_trgm 4-tier + find-or-create) + MCP parallel matcher** — delivering cross-recipe identity that supports one real feature (shopping-list sum-within-meal dedup) and one opinion-level feature (pantry check). Deleted; replaced with "every ingredient name becomes a fresh `ingredients` row" at every write path (Flutter import, recipe CRUD, MCP `create_recipe` / `fork_recipe`).
3. **Pending-review admin affordance** — UI placeholder never driven by a real admin workflow; reviewed zero ingredients in prod. Deleted.

### Retracted / modified functional requirements

- **FR37 — Exact + fuzzy + semantic search.** Scope narrowed: recipe-level fuzzy + semantic search is unchanged (pgvector recipe embeddings + pg_trgm recipe-name search remain). Ingredient-level fuzzy / semantic is **retracted**; `/v1/ingredients/search` is deleted.
- **FR141 — Per-ingredient confidence badge in caret expansion.** Retracted; per-ingredient confidence badge depended on `matched_ingredient_id` null-check which no longer exists.
- **FR144 — `IngredientRowStateBadge` (✨ glyph for pending-review canonicals).** **DELETED.** Pending-review column is gone; badge has no data source.
- **FR-MEAL-12 / NFR-MEAL-4 — Sum-within-meal shopping-list dedup.** **Retracted.** Duplicate line items across component recipes are expected and acceptable; "olive oil × 2" is first-class. Ordering is preserved (`meal.components × recipe.ingredients`) so duplicates stay adjacent.
- **Pantry check on shopping-list generation (implicit in shopping-list PRD language).** **Retracted.** `check_pantry` parameter deleted; shopping-list generation does not consult `PantryIngredient`. Pantry remains a read-only "what I have" log.

### New / reframed principles

- **Ingredients are per-row strings, not cross-row identity.** The `ingredients` table becomes a bag of rows keyed by opaque UUID, one row per unique name-write. No uniqueness constraint; no canonical semantics. FKs from `recipe_ingredients`, `pantry_ingredients`, `shopping_list_items`, `pantry_ingredient_events` remain for referential integrity and cheap display-name lookup, but they carry no identity promise.
- **Similarity is read-time inference, not write-time graph.** A future epic wanting "what else could I use instead of olive oil" runs an LLM or vector inference call in the relevant request handler.
- **Shopping-list duplicates are a feature, not a bug.** No future epic may silently re-introduce dedup.
- **Autocomplete rebuild is a future epic.** Options: user history, frozen seed list, LLM completions. Not a server fuzzy match.

### Cross-epic impact

- **`epic-review-import-ingredient-polish`** (backlog) is rescoped. `riip-4`'s pending-review annotation half is dropped (keeps the `/v1/units/aliases` endpoint half); `riip-7` (IngredientRowStateBadge) is **deleted** in full. `riip-1/2/3/5/6/8` (unit normalization + one-line row layout + regression smoke) are unaffected.
- **`epic-calendar-per-meal-shopping-add`** (done) already inherits the no-dedup behaviour for free.
- **`epic-meals-calendar`** (done) — `mcal-2`'s aggregate-meal-ingredients dedup test subset is deleted as part of str-ing-2.
- **`epic-pantry`** (done) — pantry screens unchanged; pantry-check-on-shopping-list deleted.

### Known regressions (accepted by user 2026-04-20)

- Duplicate line items on shopping lists derived from Meals with overlapping ingredients.
- No pantry cross-reference on shopping-list generation (pantry is read-only vs. the list).
- No ingredient autocomplete in recipe create/edit flows; pantry ingredient-search widget becomes a plain text field.
- `shopping_list_items.category` is always NULL (column retained; value was previously read from `ingredients.category` which is dropped).
- Admin has no pending-review ingredient review queue (there is no concept to review).

### Retained-as-placeholder

- `shopping_list_items.already_have_quantity` is retained as always-NULL. A future epic revisiting pantry cross-check can write into it without an extra migration. Cost: one column; zero runtime.

## Addendum — 2026-04-20 — Extractor field-level inference (`epic-extractor-field-inference`)

### Context

Today every extractor prompt carries the rule *"Only include fields you can find in the content"* (`ai_extractor.py:89`, with the `text_extractor.py:127` variant explicitly saying *"Set missing fields to null rather than guessing"*). That's safe, but it leaves Review Import with blank recipe-level fields — cook time, prep time, servings, description, cuisine, category, vibes — on any source that doesn't surface them. Leo's ask, verbatim: *"how hard would it be to have our extractor also be able to guess some of the additional details like 'cook time/prep time' even if doing so tanks the confidence score … I'd love to see if that's a doable user experience."*

Current state rolled up across research: confidence plumbing is live end-to-end (irrd-3 — model self-report + heuristic fallback + API surface), canonical units are live (riip-* — tbsp enum), per-ingredient matching has its own confidence signal (`match_ingredients_task`), and the Flutter `ConfidenceBadge` exists but is scoped to the Activity Hub's `ImportRow` expansion. No field-level provenance exists on `parsed_recipe`; no extractor marks a field as "guessed vs found"; no UI affordance distinguishes an AI-inferred value from an extracted one; no user-correction signal flows back from Review Import / Recipe Edit for eval tuning. Eval has ground-truth for cook_time / prep_time / servings on the ~7 text fixtures but no per-field inference accuracy metric and no hallucination-rate anti-metric.

### Pivot

- **Inference becomes a first-class extractor mode.** A new feature flag `EXTRACTOR_INFER_MISSING_FIELDS` (default on, flippable via ECS task def without redeploy — matches the `EXTRACTOR_EMIT_CONFIDENCE` / `EXTRACTOR_EMIT_CANONICAL_UNITS` pattern) swaps each LLM extractor's prompt into an **"extract OR best-guess"** mode for a tight allow-list of recipe-level fields. The model is instructed to emit a value **and** append the field name to a top-level `inferred_fields` array when the value was synthesized rather than found in source. Downstream pipeline clamps the value to a sane range, applies a confidence penalty proportional to the number of inferred fields, persists the annotation, and surfaces it in API responses.
- **Flutter renders a sparkle badge (`Icons.auto_awesome`) next to every inferred recipe-level field** on the Review Import screen and Recipe Edit screen. Tap opens a brief bottom-sheet explainer ("AI guessed this — verify or edit"). The badge disappears the moment the user edits the field — any edit is treated as acceptance or override, no separate "accept" button.
- **User corrections to inferred fields are logged** via a new `POST /v1/import-items/{id}/corrections` endpoint that writes one `error_logs` row (`service="audit"`, `error_type="InferredFieldCorrected"`) capturing the field name, the inferred value, and the user's corrected value. Server resolves the original from `parsed_recipe` — client sends only `{field, corrected}`. This is the feedback signal that lets us tune heuristic penalties and prompts in the next iteration without guesswork.
- **Eval gains two metrics:** `field_inference_accuracy` (on fixtures with ground-truth, how close the inferred value landed — ±20% tolerance for times, exact for servings/cuisine/category/vibes) and `hallucination_rate` (an **anti-metric** — fraction of inferred fields where the source actually did have a value the extractor missed; lower is better). Both are **soft gates** for v1 — measured and reported, not merge-blocking.
- **Per-ingredient inference is explicitly deferred** to a follow-up epic `epic-extractor-ingredient-inference`. Leo called out the hallucination concern; this epic ships the pattern on recipe-level fields only, proves the UX, and lets the feedback-log data inform whether per-ingredient is worth the risk.

### Functional Requirements (addition)

- **FR-EFI-1 — `EXTRACTOR_INFER_MISSING_FIELDS` feature flag.** `libraries/utils/utils/services/recipe_extractors/inference_prompt.py` exposes `infer_missing_fields() -> bool` read via `os.environ.get("EXTRACTOR_INFER_MISSING_FIELDS", "true")`. Read at extractor-call time, not startup, so flips apply to the next request. When `false`, the extractors revert to the current "only extract present values" behaviour and skip the inference allow-list + confidence penalty entirely.
- **FR-EFI-2 — Inferable-field allow-list.** The set of fields the extractor may infer is fixed and small: `prep_time_minutes`, `cook_time_minutes`, `total_time_minutes`, `servings`, `description`, `cuisine`, `category`, `primary_vibe`, `secondary_vibe`. Name / ingredients / instructions / steps / image_url / source_url / author are NOT inferable — absence stays absence. The allow-list lives in `libraries/utils/utils/services/recipe_extractors/inference_prompt.py` as `INFERABLE_FIELDS: tuple[str, ...]` and is the single source of truth (backend guardrails + eval + Flutter client all read from or mirror this constant).
- **FR-EFI-3 — Extractor prompt rewrites (`ai_extractor.py`, `vision_extractor.py`, `text_extractor.py`).** When the flag is on, the prompt's field list carries a new rule: *"For the following fields, if not present in source, produce a best-guess value based on recipe complexity / step count / ingredient signals: prep_time_minutes, cook_time_minutes, total_time_minutes, servings, description, cuisine, category, primary_vibe, secondary_vibe. For every field you infer (not extract), append its exact schema name to a top-level `inferred_fields` array. If nothing was inferred, emit `inferred_fields: []`."* Worked-example delta added to each prompt showing an inferred cook_time flowing into the annotation. The existing "Only include fields you can find" instruction is rewritten to scope only to non-inferable fields. `json_ld.py` is untouched — schema.org data is authoritative; it never infers.
- **FR-EFI-4 — `ExtractedRecipe.inferred_fields: list[str]`.** New field on the dataclass in `libraries/utils/utils/services/recipe_extractors/base.py` with `field(default_factory=list)`. Each extractor populates it from the model output when the flag is on; defaults to `[]` when the flag is off or when the model emits nothing. Order is insignificant; duplicates are deduped server-side.
- **FR-EFI-5 — Clamp-and-log guardrails on inferred values.** `libraries/utils/utils/services/recipe_extractors/inference_guardrails.py` exposes a per-field clamper:
  - `prep_time_minutes`: clamp to [1, 240], log if source was outside.
  - `cook_time_minutes`: clamp to [1, 720], log if outside.
  - `total_time_minutes`: clamp to [1, 960], log if outside.
  - `servings`: clamp to [1, 24], log if outside.
  - `description`: truncate to 240 chars, log if truncated.
  - `cuisine`, `category`: free-string; 40-char cap; log if truncated.
  - `primary_vibe`, `secondary_vibe`: must pass existing `validate_vibe()` (drop + log if invalid).
  Guardrails apply ONLY to fields present in `inferred_fields` — extracted values are trusted. Clamp events write one `error_logs` row per clamp with `service="audit"`, `error_type="InferredFieldClamped"`, `metadata={"field", "raw", "clamped", "import_item_id"}`. Dropped fields (vibes that fail validation) are removed from `inferred_fields` too so the API never flags a field as inferred when the value was discarded.
- **FR-EFI-6 — Confidence penalty.** `libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py` gets a new helper `apply_inference_penalty(score: float, inferred_count: int) -> float` that subtracts `0.05 * min(inferred_count, 5)` from the resolved score (max penalty 0.25). Applied AFTER `resolve_confidence()` regardless of whether confidence is model-reported or heuristic-fallback — the penalty represents "this score is less trustworthy because N values were guessed." Clamped to [0, 1]. Effective when the flag is on; no-op when off.
- **FR-EFI-7 — `extract_recipe_task` persists `inferred_fields` + applies guardrails + applies penalty.** Sequence: extract → validate + clamp inferred values via guardrails → persist `inferred_fields` on `parsed_recipe` top-level key → apply inference-count penalty to confidence → persist. Happens regardless of extractor used (ai / vision / text). `json_ld` path never emits `inferred_fields`; the task writes `inferred_fields: []` for json_ld-extracted items so the API response shape is uniform.
- **FR-EFI-8 — API response surfaces `inferred_fields`.** `GetImportItem`, `list_import_items`, and `list_import_jobs` responses expose `inferred_fields: list[str]` at the item response root (hoisted from `parsed_recipe` — mirrors the existing `confidence_score` hoist). Empty list on no-inference items; always present (never null) to keep the client contract uniform.
- **FR-EFI-9 — `POST /v1/import-items/{id}/corrections` endpoint.** Accepts `{field: str, corrected: <any JSON-serializable>}`. Authorization: caller must own the import-item. Server looks up the original value from `parsed_recipe` (so the client's trust surface is minimal — client can't lie about what was originally there), then writes one `error_logs` row:
  ```json
  {
    "service": "audit",
    "error_type": "InferredFieldCorrected",
    "import_item_id": "...",
    "user_id": "...",
    "metadata": {
      "field": "cook_time_minutes",
      "original": 30,
      "corrected": 45,
      "was_inferred": true
    }
  }
  ```
  `was_inferred` reflects whether the field was in `parsed_recipe.inferred_fields` — lets future eval filter "corrections to guessed fields" vs "corrections to extracted fields that were wrong." Response: 204 No Content on success, 400 if field not in allow-list, 403 on non-owner, 404 on missing item.
- **FR-EFI-10 — Flutter `InferredFieldBadge`.** New widget at `app/lib/features/recipes/add_recipe/widgets/inferred_field_badge.dart`. Renders a 14pt `Icons.auto_awesome` glyph (`colorScheme.tertiary` tint). Tap opens a tiny bottom sheet: *"AI guessed this value. Verify or edit it below — your correction helps the extractor learn."* Badge is stateless — its visibility is driven by the parent (`inferredFields.contains(fieldName)`), so once the parent removes the field from the set (on user edit), the badge vanishes.
- **FR-EFI-11 — Review Import wires the badge to all 9 fields.** `import_item_review_screen.dart` renders `InferredFieldBadge` adjacent to the label of each inferable field when `item.inferredFields.contains(<field_name>)`. On first edit of a field, the screen's local state removes the field from the inferred set AND dispatches the correction via `POST /v1/import-items/{id}/corrections`. Dispatch is debounced 1500ms (to batch rapid edits into one correction row per field) and fires on focus-loss. Description / cuisine / category / vibes use the existing text input widgets; the badge sits inline with the field label.
- **FR-EFI-12 — Recipe Edit wires the badge symmetrically.** `edit_recipe_screen.dart` pulls `inferred_fields` from the recipe payload (populated into `recipes.inferred_fields` JSONB column when the recipe is created from an import-item with inferred values — see FR-EFI-14) and renders the same badge. Same edit-dismisses-badge rule. Corrections dispatch to a parallel recipe-level correction endpoint **not built in this epic** — the dismiss-on-edit behaviour is wired, but the correction round-trip is deferred (Recipe Edit corrections go to a local-only log for v1). This is an explicit deferral; flagged in design principles.
- **FR-EFI-13 — Sparkle badge disappears on first edit, never returns.** The badge's visibility is derived state from `inferredFields`. Any value change on a badged field removes the field name from the in-screen `inferredFields` set. No "undo" UI — if the user reverts to the inferred value, the badge stays gone. This is intentional: the user's engagement with the field counts as acceptance / override regardless of the final value.
- **FR-EFI-14 — `recipes.inferred_fields` JSONB column.** New migration adds a nullable `inferred_fields JSONB` column to `recipes` (default `[]`, NOT NULL once populated). `create_recipe_task` copies `import_item.parsed_recipe.inferred_fields` into `recipes.inferred_fields` when the recipe is created from an approved import. `GetRecipe` + `UpdateRecipe` expose and accept the field so Recipe Edit can read and mutate it.
- **FR-EFI-15 — Eval metrics: `field_inference_accuracy` + `hallucination_rate`.** Two new modules under `services/eval/src/metrics/`:
  - `field_inference_accuracy.py` — for each fixture with ground-truth on an inferable field AND the extractor-output fixture has that field in `inferred_fields`, score: ±20% tolerance for numeric times/servings counts as 1.0; exact match required for vibes/cuisine/category/description (first 20 chars, case-insensitive) counts as 1.0; partial for description (Levenshtein-based). Emit per-field mean + overall mean. Soft gate ≥ 0.6 in v1.
  - `hallucination_rate.py` — for each fixture with ground-truth value on an inferable field, if the extractor INFERRED that field (marked in `inferred_fields`) rather than extracting it, that's a hallucination (the model guessed despite source having the answer). Rate = hallucinations / (extractable field count across fixtures). Soft gate ≤ 0.15.
  - Both register into `eval.config.yaml` and emit in the per-run report. No hard CI gates in v1.

### Non-Functional Requirements (addition)

- **NFR-EFI-1 — Zero regression on non-inferred extractions.** When the source has `cook_time_minutes` in the markup / OCR, the extractor MUST extract it (not infer). Prompt discipline + eval `hallucination_rate` metric together enforce this. A fixture unit test asserts: source with explicit cook_time = 45 → extractor output has `cook_time_minutes = 45` AND `cook_time_minutes NOT in inferred_fields`.
- **NFR-EFI-2 — Cost envelope.** The prompt grows by ~350 tokens for the inference instructions + worked examples. Per-extraction cost delta: ~$0.00005 at gpt-4o-mini pricing — negligible. No new API calls; no batch infrastructure changes. Measured before/after in one eval run and recorded in the epic retrospective.
- **NFR-EFI-3 — Latency envelope.** No new round trips. Extractor completion token count may rise ~10–40 tokens (the inferred values + the `inferred_fields` array). Total latency delta expected < 100ms at P95.
- **NFR-EFI-4 — Coverage stays at 100% on `services/api`.** All new endpoint code + migration + hoisted-field surface ship with tests.
- **NFR-EFI-5 — Flag-off path is binary-clean.** When `EXTRACTOR_INFER_MISSING_FIELDS=false`, the prompt contains zero inference instructions, the guardrails module never runs, the confidence penalty is not applied, and `inferred_fields` persists as `[]` on every new `parsed_recipe`. Existing pre-flag `parsed_recipe` rows (without the key at all) are treated as if `inferred_fields = []` by the API hoist and the Flutter decoder.
- **NFR-EFI-6 — Correction endpoint is low-traffic and low-weight.** P95 < 150ms. Writes one row to `error_logs` (existing, append-only, well-indexed by `created_at + service`). No new tables, no new indexes.
- **NFR-EFI-7 — Accessibility.** `InferredFieldBadge` has a `Semantics(label: "AI-inferred value, tap for details")`. Screen reader announces the badge when the focused field has it. Minimum 40pt tap target. The bottom-sheet explainer is keyboard-dismissible.

### Non-Goals (this epic)

- **No per-ingredient inference.** Leo explicitly deferred this. A follow-up epic `epic-extractor-ingredient-inference` will revisit after this epic's `error_logs`-fed feedback signal has 2+ weeks of data.
- **No hard merge gates on eval metrics.** Both new metrics are measured + reported; neither blocks CI. We want to see the numbers on real traffic before pinning thresholds.
- **No recipe-level Recipe-Edit correction dispatch.** FR-EFI-12 wires the badge-dismiss-on-edit behaviour but not the `POST` round trip for recipe-edit corrections. Deferred deliberately — the Review-Import dispatch gives us the signal we need; recipe-edit corrections can flow through a future admin-dashboard consolidation.
- **No admin UI for viewing correction logs.** Logs are queryable via SQL for the first pass; a dashboard is out of scope.
- **No `inferred_fields` diff / highlight in recipe version history.** When Recipe Edit saves, the version snapshot will preserve `inferred_fields`, but no UI calls out "these fields were originally AI-guessed" in the diff view. Low-value for v1.
- **No retroactive enrichment.** Existing `parsed_recipe` rows without `inferred_fields` are left alone — no backfill job. They render without badges, correctly.
- **No `json_ld` inference.** Schema.org data is authoritative; `json_ld_extractor` never infers and always emits `inferred_fields: []`.
- **No vibe inference outside the allow-list.** The extractors already get asked for vibes today; this epic formalizes the provenance annotation when a vibe is model-synthesized rather than source-stated, but does not expand the vibe taxonomy or the inference scope beyond the two existing vibe slots.

### Locked decisions

1. **Q1 = Recipe-level only** (2026-04-20). Per-ingredient qty/unit/notes inference deferred to a follow-up epic. This epic proves the pattern; follow-up decides if the ingredient-level risk is worth it informed by correction-log data.
2. **Q2 = All recipe-level inferable fields** (2026-04-20). `prep_time_minutes`, `cook_time_minutes`, `total_time_minutes`, `servings`, `description`, `cuisine`, `category`, `primary_vibe`, `secondary_vibe`. No mid-scope tiering.
3. **Q3 = Sparkle badge** (2026-04-20). `Icons.auto_awesome` next to each inferable-field label, tap for bottom-sheet explainer, disappears on first edit. Reuses the visual vocabulary Leo already recognizes from the (now-retired) `IngredientRowStateBadge`.
4. **Q4 = `error_logs` with `service="audit"`, `error_type="InferredFieldCorrected"`** (2026-04-20). Cheapest path; no new table; queryable. Server resolves original value from `parsed_recipe` to minimize client trust surface.
5. **Clamp ranges are server-authoritative** (2026-04-20). Client trusts the persisted value and does no re-validation. Guardrails module owns the truth.
6. **Confidence penalty is additive-to-the-resolved-score** (2026-04-20). `0.05 * min(inferred_count, 5)` regardless of model vs heuristic source. Flat rule, no field weighting in v1.
7. **All-or-nothing feature flag** (2026-04-20). Flag off → prompt reverts to current "only extract present" language and the guardrails + penalty + annotation skip. No per-field flags.
8. **Badge dismissal is any-edit, not save** (2026-04-20). Focus-loss with a changed value dispatches the correction; no explicit "accept" button. Matches how the rest of Review Import handles structured edits.
9. **Recipe-Edit correction round-trip deferred** (2026-04-20). Recipe-Edit gets the badge + dismiss-on-edit UX, but the `POST` to the correction endpoint is wired only on Review Import. Review-Import is where the signal volume is highest; Recipe-Edit corrections wait for a future consolidated dashboard.
10. **Flag-order coordination** (2026-04-20). `EXTRACTOR_INFER_MISSING_FIELDS` flips on LAST relative to `EXTRACTOR_EMIT_CONFIDENCE` and `EXTRACTOR_EMIT_CANONICAL_UNITS` — the inference penalty depends on the confidence machinery being live, and the prompt rewrites stack with the other flag deltas.

## Addendum — 2026-04-20 — Home Meal promotion (`epic-meals-home-promotion`)

### Context

The three Meals epics that shipped to date (`epic-meals-create-and-view`, `epic-meals-discoverability`, `epic-meals-calendar`) gave Meals full backend support + detail/edit screens + a tile on the home grid + search + calendar integration. What is still missing is **home-screen agency over Meals**: today a user who already has a Kale Salad recipe and a Lemon Dressing recipe on their home grid cannot combine them without navigating into a book. Meals on the home grid today are *visible* but not *actionable* — they render as a MealTile with a component-count badge and that is it.

This addendum adds one Flutter-only epic (no backend changes) to:

1. **Let the user create and grow Meals from the home grid itself** via a long-press multi-select pattern, with a context-sensitive bulk action bar.
2. **Distinguish a Meal visually on the grid** beyond the existing "N recipes" badge — surface the component recipes by name + add a subtle Meal accent chrome + close the favorite-overlay parity gap with RecipeCard.
3. **Give the user a filter lever** to either scope the grid to Meals-only / Recipes-only or to de-clutter by hiding recipes that are already components of any Meal they can read.

### New functional requirements

- **FR-HMP-1 — Long-press to enter selection mode on home.** Long-pressing a RecipeCard OR a MealTile on the home grid enters selection mode. The home AppBar swaps to a "N selected" count with a close (X) affordance. Tap toggles selection; re-tap deselects. Long-press on recipe detail, on book detail (`recipe_book_detail_screen.dart`), and anywhere else is unchanged — this change is scoped to `home_screen.dart` only. The previous home long-press bottom sheet (Start Cooking / Archive) is retired; both actions continue to live on the recipe detail screen's FAB (Start Cooking) and overflow menu (Archive) — no migration needed, they already exist there.

- **FR-HMP-2 — Context-sensitive bulk action bar on home.** While selection mode is active a bottom bar docks over the grid. Its primary action is computed from the selection contents:
  - **≥2 recipes AND 0 Meals selected** → primary is **Create Meal** (opens `CreateMealSheet` with those recipes as initial components; target book is the first-selected-recipe's book, surfaced as an editable field in the sheet).
  - **Exactly 1 Meal AND ≥1 recipes selected** → primary is **Add to "<Meal Name>"** (calls `POST /v1/meals/{id}/recipes` once per selected recipe_id; client-side dedupes against the Meal's existing component set before dispatch; partial failure surfaces a snackbar "Added X of Y — see details" that opens a follow-up dialog listing the failures).
  - **Any other selection shape** (≥2 Meals selected, 1 Meal alone, 1 recipe alone with 0 Meals, empty) → primary is **disabled with a muted tooltip** explaining what to do next ("Select 2+ recipes to create a Meal" / "Select one Meal to add recipes to it" / "Select at least one item").
  - **Always enabled while selection non-empty** → secondary action: **Archive** (reuses `POST /v1/recipes/bulk/archive` for recipes; client iterates `POST /v1/meals/{id}/archive` per selected Meal since no bulk endpoint exists; same partial-failure snackbar shape).
  - **Cancel** (X button in AppBar, or the system back gesture, or tap outside the grid) exits selection mode without action.

- **FR-HMP-3 — Home filter gains a "Show" type axis.** The existing `FilterBottomSheet` (`app/lib/features/home/widgets/filter_bottom_sheet.dart`) gains a new section "Show" with single-select chips `[All | Recipes only | Meals only]`. Default is "All". Selection is client-side only — no API call. "Recipes only" hides MealTiles from the grid; "Meals only" hides RecipeCards. "All" is identical to today's render.

- **FR-HMP-4 — Home filter gains a "Hide components of Meals" toggle.** Same sheet, new toggle row under the "Show" section. Default is OFF. When ON: any recipe whose `id` appears in the component list of any Meal the user can read (i.e., is in the home's already-loaded `meals` list) is hidden from the grid. Implementation is purely client-side — compute `componentRecipeIds = union(m.components.map((c) => c.recipeId) for m in meals)` once per filter run; filter the recipes list by `!componentRecipeIds.contains(r.id)`. Zero backend changes.

- **FR-HMP-5 — MealTile v2: component-name chips (G2).** Below the Meal name, `MealTile` gains a single line showing up to 2 component names joined by a middot (`·`). If more than 2 components, the line ends with `· +N more`. Names are resolved **client-side via an in-memory join** against home's already-loaded recipe list (party-mode 2026-04-20 decision): the tile accepts a `componentNameResolver: String? Function(String recipeId)` callback, and home passes `(id) => _recipesById[id]?.name`. Components whose recipe_id is not in the map (archived recipes, recipes from books no longer readable) fall back to a single `· (archived)` suffix regardless of how many. No new API calls, no new response fields. Font size and weight: `textTheme.bodySmall`, muted color. Truncation via ellipsis when the chip line overflows its single-row budget. Also: **the existing decorative "N recipes" badge is retired** — the chip row's `+N` suffix carries the count; the "Meal" pill (FR-HMP-6) carries the type signal.

- **FR-HMP-6 — MealTile v2: accent chrome (G3).** Subtle "Meal" visual marker — implementation is (a) a 2px accent border (using the same primary-muted color family as existing Meal affordances) on the whole card, AND (b) a small `Icons.layers_outlined` glyph in the top-left corner inside a translucent white pill reading "Meal" in small-caps body text. Non-interactive. Purpose: signal "this is not a recipe" before the user reads the collage/name.

- **FR-HMP-7 — MealTile v2: favorite overlay parity.** `MealTile` gains the same tap-to-favorite star overlay pattern `RecipeCard` has (`app/lib/features/home/home_screen.dart` RecipeCard star, lines 69–91). Calls `POST /v1/meals/{id}/favorite` / `DELETE /v1/meals/{id}/favorite` (foundation ships these). Optimistic update with rollback on error. This closes a pre-existing parity gap noted during research.

### New NFRs

- **NFR-HMP-1 — Zero backend surface.** This epic introduces zero new endpoints, zero schema changes, zero env vars, zero infra changes. If the draft or party-mode workshop proposes a backend change, it MUST be explicitly justified or rolled back to client-side.

- **NFR-HMP-2 — Zero-Meal zero-regression.** A user with zero Meals (on any accessible book) must see pixel-identical behavior to today on the home grid, in the filter sheet (the two new filter rows simply do nothing visible on the output), and in selection mode (long-press on a recipe still enters selection mode, but the "Add to Meal" primary action will never be reachable since there is no Meal to select). Widget tests assert this with a zero-Meal fixture.

- **NFR-HMP-3 — Long-press latency unchanged.** Entering selection mode is a synchronous state flip — no network call. A user's long-press-then-tap flow must remain indistinguishable from today's long-press-then-sheet-tap in perceived responsiveness.

- **NFR-HMP-4 — Filter apply is instant.** The two new client-side filters operate on in-memory lists. No network round-trip. The filter sheet's existing "Apply" behavior is unchanged.

### Design principles

1. **Home is where Meals get made.** The fast-path for creating a Meal moves from "navigate to a book, multi-select recipes, create" to "long-press recipes on the grid you were already on, create." The book-detail fast-path (`recipe_book_detail_screen.dart`) stays — it is still the right move when the user is already in a book — but home is now a first-class creation surface.
2. **Long-press is the single selection gesture.** The only way to enter selection mode on home is long-press. There is no pencil toggle, no header icon, no FAB. This is the user's locked choice (2026-04-20) — alternative B (pencil) was considered and rejected.
3. **Old home long-press sheet is retired, not moved.** Start Cooking and Archive already live on recipe detail — the home sheet duplicated them. Retiring the home sheet is a net simplification.
4. **Bulk bar is context-sensitive, not option-heavy.** One primary action, computed from selection contents. No "Create Meal" button that stays next to an "Add to Meal..." button — that would force the user to read labels every time. The selection implies the intent.
5. **Add to Meal uses the selection itself as the anchor.** Including a Meal in the selection turns the whole selection into "grow that Meal." No separate Meal-picker sheet for this flow — that is the point of multi-select.
6. **Filters are client-side.** Every filter added in this epic operates on already-loaded data. The server is authoritative on what the user can see; the client decides what to hide.
7. **Component chips leak the composition.** G2's component-name chips are the load-bearing piece of the visual distinction — the collage already shows thumbnails, but a user who does not recognize a thumbnail can now read "Kale Salad · Lemon Dressing" directly. The chrome (G3) is secondary polish.
8. **Favorite parity is table stakes.** Meals being favoritable in backend but not on home is a glitch, not a feature. Close it.
9. **Partial-failure surfaces are consistent.** Both "Add to Meal" (N `add_recipe_to_meal` calls) and "Archive" (N archive calls) show the same "Added/Archived X of Y — see details" snackbar shape with a details dialog for the failed rows. This pattern is net-new but small and worth locking here so future bulk actions inherit it.

### Cross-epic impact

- **`epic-meals-create-and-view`** (done) — no regressions expected. `CreateMealSheet` is reused verbatim from foundation; its `initialComponents` parameter already handles the multi-select-prefill case.
- **`epic-meals-discoverability`** (done) — no regressions expected. The home grid merge logic (`home_screen.dart` lines 152–164) is unchanged in its fetch pattern; only the rendered tile changes (MealTile v2).
- **`epic-meals-calendar`** (done) — no impact. `meal_events.meal_id` / plan-meal / per-meal shopping add — all untouched.
- **`epic-meals-sharing-and-ai`** (backlog) — no blocking interaction. Share is still the Meal detail action bar's slot 6.
- **`epic-bugs-home-polish`** (backlog) — soft interaction. `home-polish-2-post-add-recipe-nav` will land independently; this epic does not touch the post-create nav flow.

### Accepted regressions

- None. This is a strictly additive epic. Every surface it touches either gets a new affordance (long-press sheet → selection mode) or a cleaner visual (MealTile v2). The only functional removal is the home long-press bottom sheet, and both of its actions remain available on recipe detail.

### Open questions for the user — NONE

All questions surfaced in the initial options presentation were resolved by the user's picks (gesture A, filter default F1+F2, visual G2+G3, Add-to-Meal via selection). Party-mode workshop may surface more; those will be escalated per the /dev-plan loop.


## Addendum — 2026-04-21 — Performance Health Initiative

### Motivation

Single-user prod ("few recipes") still feels slow after `epic-observability-latency` and `perf-1/perf-2` landed. Observability is deployed (`request_latencies` / `task_latencies`, `/admin/metrics` at p50/p95/p99) and ready to pinpoint hot paths; empirical + static analysis surfaced four converging contributors:

1. **Infra floor** — `db.t4g.micro` burst-credit exhaustion, untuned PG parameter group (`shared_buffers=128MB`, `work_mem=4MB` defaults), no Performance Insights, API ECS task at 256 CPU / 512 MB — all together shift absolute latency up on every request.
2. **Backend N+1 and redundant queries** — `list_shopping_lists` lazy-loads `items`/`members` in a loop; `list_meals` calls `_readable_book_ids()` once per meal (30× redundant); `list_activities` runs a heavy `COUNT` on every cursor-less request; `unified_search` re-runs `_get_my_book_ids()` twice; `list_calendars` aggregates `CalendarUser` across the whole table; auth dependency runs `_ensure_default_calendar()` per request.
3. **Flutter redundant polling** — activity badge/shell + notifications-tab + imports-tab all poll at 30s on overlapping paths; shell + tab double-fetch the same data. User has opted to fix the redundancy only (not to slow base cadences).
4. **Hot-path secondary** — Auth0 JWKS cache is in-memory per task (reheats on every task restart); select legacy migrations used non-`CONCURRENTLY` index creation.

### Scope

Three epics, shippable in dependency order but individually non-breaking:

1. **`epic-perf-infra-and-measurement`** — cost-bumping and measurement foundation. RDS `t4g.micro` → `t4g.small` (+$10/mo), tuned PG parameter group (`shared_buffers`, `work_mem`, `effective_cache_size`, `log_min_duration_statement=100`), Performance Insights enabled, API ECS task 256→512 CPU / 512→1024 MB, tiny Redis + Auth0 JWKS cache backed by it, `services/api/scripts/analyze_latency.py` ops script with regression-hunt query, backport `CONCURRENTLY` into any pre-`20260420` index migration. Under NFR29 $50/mo cap (+$15/mo).
2. **`epic-perf-backend-query-tuning`** — pure code-level fixes to the N+1 and redundant-query patterns. No API shape changes, no breaking contracts. Each story is an isolated endpoint-level improvement with a microbenchmark AC.
3. **`epic-perf-flutter-client-polish`** — redundant polling consolidation (activity shell + tabs into a single `activityHubProvider`), `Image.network` audit → `CachedNetworkImage`, recipe detail keep-alive cache, verify `perf-2` hasn't regressed (home filter re-applies). Imports 2s poll and admin logs 5s poll preserved per user decision.

### Targets

Tied to existing NFR1 (P95 core actions < 2s) and NFR50 (`/admin/metrics` endpoints < 300ms on 10M rows):

- P95 of `GET /v1/recipes`, `GET /v1/meals?scope=home`, `GET /v1/shopping-lists`, `GET /v1/activities`, `GET /v1/calendars` each ≤ 300ms on single-user-prod data volume.
- P95 of `GET /v1/admin/metrics/endpoints?window=24h` ≤ 300ms (unchanged from `epic-observability-latency`).
- Cold-start home load: total outgoing Flutter GETs on home mount ≤ 4 (from observed 6–8).
- No regression on any `sprint-status.yaml` story marked `done`; tests pass; coverage stays at 100% for `services/api`.

### Non-functional constraints

- **No breaking contracts.** No endpoint shape changes, no client protocol changes, no story removal from current roadmap. All additions — new indexes, new eager-loads, new cache layer — are additive.
- **Data-grounded.** Every story's AC names a specific `normalized_path` or task and requires the `/admin/metrics` p95 before/after to be captured in the QA walkthrough.
- **Cost-capped.** Absolute infra budget stays ≤ $50/mo (NFR29). Terraform change set must show a cost delta line.

### Explicit out-of-scope

- Re-architecting observability — `epic-observability-latency` is the source of truth and is not rewritten.
- Rewriting `unified_search` tier boundaries — we only close the N+1 gaps within the existing shape.
- A UI for the regression-hunt query — CLI only (`analyze_latency.py`) until real signal asks for more.
- Reducing any polling cadence beyond fixing the duplicate-poll case — user reserved that call.
- Redis as a general-purpose app cache — scope is strictly Auth0 JWKS (+ optional future additions out of this plan).

### Open questions — NONE at draft time

All scope and cost questions resolved in the 2026-04-21 user batch.

---

## Addendum — 2026-04-21 — Notifications Comprehensive Coverage

### Context

Push-notification *plumbing* is now live end-to-end on iOS (proven on Leo's phone via the admin "Send test push" button in `services/api/src/api/v1/admin/notifications.py`). The supporting epics — `epic-notifications-ios-proofoflife` and `epic-notifications-push-diagnostics-hardening` — landed APNs forwarding, Crashlytics-routed error reporting, the boot-time auto-prompt, a per-user health endpoint, and the 17-member `NotificationType` enum. Recent commits `4827d96` (drop `content-available=1`, set `apns-priority=10`) and `7fe41d9` (wire Runner.entitlements) closed the last delivery gap.

What remains is the **callsite layer**: most enum values are either dead or fire generic copy, the user has no way to schedule a meal-time reminder, the cooking-timer notification surface is iOS-only on quick actions and missing the in-app overlay, and per-category notification preferences don't exist. This addendum scopes the work to bring every notification we *want* up to the same proven-working bar as the admin test push.

### User-locked decisions (from 2026-04-21 batch)

1. **Partner activity in shared books — high-signal only.** Push on: book shared (already wired), recipe added (fix arity bug), recipe forked, note added, partner cooked your recipe. Skip every individual edit / version-bump (would be too noisy on active books).
2. **Notification preferences — per-category toggles.** The current 3-toggle screen (`push_enabled`, `partner_activity`, `auto_approve_imports`) expands to per-category switches: Meal reminders, Timers, Shopping, Partner activity, Imports, Friends/invitations. Plus Quiet Hours + timezone (already exist). Auto-approve-imports stays as-is (it's a separate behavior, not a notification toggle).
3. **Meal-reminder fan-out — all accepted participants.** When a meal event is shared and has accepted participants, every accepted participant gets the meal-time reminder (not just the owner). Owner-only is the wrong default for shared dinners.
4. **iOS Live Activities for cooking timers — wire in scope.** The Swift UI in `app/ios/PalatefulWidgets/CookingTimerLiveActivity.swift` is fully built but Flutter never calls `LiveActivityService.startTimerActivity(...)`. As part of the timer epic, wire the Flutter side so active timers appear in Dynamic Island + lock-screen with live countdown.

### Sensible defaults I'm taking (call out for confirmation in the next /dev-plan if wrong)

5. **Meal-reminder timing model — single "Remind me at" wall-clock time per meal.** New nullable `meal_event.meal_reminder_time` (TIME) column. NULL = use slot default (8:00 / 12:00 / 18:30 / 15:00 for breakfast/lunch/dinner/snack — matches the existing client-side `_mealDefaultTime()` mapping in `app/lib/features/calendar/widgets/plan_meal_sheet.dart:404-415`). User can override per-meal in the create/edit sheet via a new time picker. The existing `notify_prep_start` / `notify_cook_start` offsets stay separate (they're prep-workflow reminders, not the meal-time reminder).
6. **Bulk-vs-single import copy threshold.** `total_items == 1` → single-recipe rich copy: `"Your {recipe.name} is ready to review"` (loaded from the first awaiting-review item). `total_items > 1` → bulk summary: `"Your bulk import has {n} recipes to review"`.
7. **Failure notifications — full-job-failure push only.** Per-item failures stay in the Imports tab (per existing `abi-2a` decision). Job-wide failure (every item failed extraction) gets a single push: `"Couldn't import from {source}. Tap to retry."` Don't spam per-item.
8. **In-app foreground banner upgrade — timer-completion overlay only.** Today every foreground push renders as a `SnackBar` from `_onForegroundMessage` in `push_notification_service.dart:484-523`. Cooking-timer expiration in cook-mode gets a NEW Cupertino-style modal overlay with `+2 min`, `+5 min`, `Reset`, `Stop` action buttons (matches Apple's timer alert UX, which the user explicitly referenced). Other notifications keep the SnackBar — no scope creep into a generic banner system.
9. **Meal-event deep-link.** New `/calendar/meals/:id` route + lightweight detail screen. `MEAL_EVENT_*` notifications route there instead of `/calendar` root. (Today's `_routeForNotification` lands on `/calendar` for all meal types — the user opens the calendar view but has to find the relevant event manually.)
10. **System broadcast topic — defer.** `NotificationType.SYSTEM` enum exists but isn't wired. Not in scope this round; revisit when there's a real broadcast use case.
11. **Weekly digest — defer.** No planned worker task; not in scope this round.
12. **Post-cook feedback prompt — in scope (partner activity epic).** 2-hour Celery-delayed push after a cooking-log row is created: `"How did your {recipe.name} turn out?"`. Routes to recipe detail. Subject to per-category opt-out via the new prefs screen.

### Scope of work (5 epics)

Each epic is a vertical slice — UI, API, data, infra all addressed where relevant — and the chunking lets PRs land independently. Total estimate ~10–14 days of dev work across the five.

#### Epic A: Notifications Foundation — Per-Category Prefs, Copy Library, Deep-Links
The cross-cutting plumbing every other epic builds on. Without this, the others ship rich behavior with stale wrappers.
- **User sees:** Profile → Notifications shows per-category toggles. Existing "Sweet Potato Quiche needs a review" copy is rich (recipe name, count); meal notifications deep-link to a specific meal detail screen.
- **Touches:** Frontend (notification prefs screen, new meal detail screen, notification copy module), Backend (per-category prefs schema, `notify_import_needs_review` loads recipe name, RECIPE_ADDED arity fix), Infra (one migration: prefs JSON schema bump).
- **Blocks:** B, C, D, E (each consumes the per-category prefs model and the copy library).

#### Epic B: Meal-Time Reminders
The user's #1 explicit ask. Schedules and fires meal-time reminders to every accepted participant.
- **User sees:** When creating/editing a meal, a "Remind me at" time picker appears below the slot chips, defaulted to the slot's default time (lunch → 12:00 PM). Editable per-meal. At the configured time, a push lands on every accepted participant: `"Lunch in 5 — Sweet Potato Quiche 🍳"`. Tapping opens the meal detail screen.
- **Touches:** Frontend (new time picker in `plan_meal_sheet.dart`, meal detail screen update), Backend (new `meal_reminder_time` column, `MealEventCreate/Update` schema, Celery beat task `send_meal_reminders` running every 5 min, MEAL_EVENT_UPDATED wired in `update_meal_event.py`), Infra (one migration; one Celery beat schedule entry).
- **Depends on:** A (per-category Meals toggle).

#### Epic C: Cooking Timer Quick Actions + Live Activities
The user's #2 explicit ask. Brings Android to iOS parity, wires the dead Live Activity, adds the in-app Apple-style overlay.
- **User sees:** Active timer in Cook Mode appears in Dynamic Island + lock screen with live countdown. Timer expires → OS notification with `+2 min` / `+5 min` / `Reset` / `Stop` actions on both iOS (already wired) AND Android (NEW). If app is foreground, a Cupertino-style modal overlay appears in cook-mode with the same four actions. Tapping +2 reschedules; Stop cancels; Reset restarts at original duration.
- **Touches:** Frontend (`cook_timer_notification_service.dart` Android `AndroidNotificationAction` wiring, new `TimerCompletionOverlay` widget in cook-mode, `live_activity_service.dart` integration into `cook_mode_screen.dart` lifecycle), iOS Native (no changes — Swift UI already exists), Backend (none — timers are 100% local).
- **Depends on:** A (per-category Timers toggle for in-app overlay opt-out).

#### Epic D: Partner Activity Notifications
High-signal social presence in shared books. Skip the noisy stuff (edits), ship the moments worth interrupting for.
- **User sees:** When a partner forks your recipe, adds a note to your recipe, or cooks your recipe, you get a rich push: `"Sarah cooked your Sweet Potato Quiche!"` with the recipe cover image. Two hours after you finish a cook, a deferred push: `"How did your Sweet Potato Quiche turn out?"` Acceptance of your meal invite pushes back to you: `"Sarah's coming to dinner!"` All include image where available, route to relevant detail screen.
- **Touches:** Frontend (none beyond consumption — handled by existing tap router), Backend (RECIPE_ADDED bug fix may already be done in A; new fan-out in `fork_recipe.py`, `add_recipe_note.py`, `cooking_log/create_cooking_log.py`, `meal_event/accept_invite.py`; new Celery task `post_cook_feedback_prompt` with 2h delay), Infra (none).
- **Depends on:** A (per-category Partner Activity toggle, recipe-name-loading helper used for image attachment).

#### Epic E: Scheduled Reminders Backend — Shopping Deadlines + Import Failures
The remaining backend gaps. Two small features, one shared Celery beat / event-trigger pattern.
- **User sees:** Shopping list items with a `due_at` date trigger a morning-of push: `"3 items on your Weekend BBQ list are due today"` (single push per list per morning, not per-item). When a bulk import fails completely (every recipe extraction errored), one push: `"Couldn't import 5 recipes from {source}. Tap for details."`
- **Touches:** Frontend (none beyond consumption), Backend (Celery beat task `send_shopping_deadline_reminders`, fix the silenced full-failure path in `extract_recipe_task.py` / `create_recipe_task.py`), Infra (one Celery beat schedule entry).
- **Depends on:** A (per-category Shopping + Imports toggles).

### Success metrics (epic-level)

- Every `NotificationType` enum value either fires from a real callsite OR is removed from the enum. No more dead code.
- Leo on his iPhone receives at least one notification of each new category during a single dogfood week (April 21 - April 28).
- Notification copy includes a meaningful proper noun (recipe name, partner name, list name) wherever the data exists at send time. No "Item added" / "Notification" / "Update" titles survive into prod.
- Quick actions (+2/+5/Reset/Stop) work on both iOS and Android timer notifications.
- Per-category opt-out is effective within one push of being toggled (no caching).
- Zero regression in existing wired notifications (shopping items, friend requests, invitations, meal invites, NEW_FEEDBACK, TEST).

### Non-functional constraints

- **No breaking contracts.** Per-category prefs is an additive JSON-shape change; old clients sending the legacy 3-toggle shape continue to work (defaulted to "all-on" for new categories).
- **Backwards-compat shim policy:** none. Remove dead enum values once their replacement ships.
- **Dogfood-driven.** The completion criterion is "Leo got pinged on his phone for each new category at least once during the test week", not test coverage in isolation.
- **Cost-capped.** Adds two Celery beat tasks (meal reminders every 5 min, shopping deadline once a day in user's morning timezone). Marginal cost; well within current $50/mo NFR29.
- **Live Activity APNs cost:** updates flow through FCM's Live Activity API (already provisioned). No new infra.

### Explicit out-of-scope (this round)

- System broadcast topic / `NotificationType.SYSTEM` activation.
- Weekly / monthly digest notification.
- Notification grouping/threading on the OS side (multiple meal reminders stack natively).
- Real-time activity-tab updates (currently 30s poll; separate concern).
- Per-event fine-grained toggles (e.g., "Shopping → Item added on" but "Item checked off"). Per-category is the granularity.
- Web notifications (web app is read-only for notifications today; out of scope).
- Android Live Activities (Android equivalent doesn't exist; Dynamic Island is iOS-only).

### Open questions — none at draft time

All five scope decisions resolved in the 2026-04-21 user batch (4 confirmed, 8 sensible-defaults documented above for retroactive escalation).

---

## Addendum — 2026-04-22 — Reactive state permeation across Flutter surfaces

### Problem

User feedback (dogfood, 2026-04-22): "There are a ton of places in the app where the state is not updating whenever we update the underlying objects. I click dismiss on a recipe import, it stays in that view. I recently added a recipe, it doesn't show up until I refresh. We want the state in the app to be entirely reactive whenever we update it ourselves."

Frontend audit confirms the app is ~50/50 reactive today:

- **Reactive already**: shopping-list via WS (`ShoppingCartService` stream controllers), shared recipe-book CRUD via WS (`broadcast_event_to_recipe_book`), activity badge counts via 30s `ActivityReadProvider` poll.
- **Not reactive**: HomeScreen recipe grid (imperative `_loadRecipes()` in `initState`, no Riverpod consumer), ImportHistoryScreen dismiss/retry/clear-all (optimistic `setState` only — `importsSeeAllProvider` is never invalidated), meal create/edit/archive (no cross-surface invalidation), calendar / meal-event mutations (no cross-surface invalidation), recipe-book CRUD (no invalidation back to books list), profile + notification prefs (no cross-surface), pantry mutations (no cross-surface).

The root architectural gap is the absence of a **cross-cutting mutation event primitive**. Each mutation site individually decides which providers to invalidate (or doesn't), so every new screen re-introduces the same bug class.

### Functional requirements

**FR-REACT-1 Mutation Bus primitive.** Introduce a single `Stream<MutationEvent>` (typed sealed class) in `app/lib/core/state/mutation_bus.dart`. Event types enumerate every resource mutation: `RecipeCreated`, `RecipeUpdated`, `RecipeArchived`, `RecipeFavorited`, `RecipeBookCreated`, `RecipeBookUpdated`, `RecipeBookArchived`, `ImportItemDismissed`, `ImportItemRetried`, `ImportJobDismissed`, `MealCreated`, `MealUpdated`, `MealArchived`, `MealFavorited`, `MealEventCreated`, `MealEventUpdated`, `MealEventDeleted`, `CalendarCreated`, `CalendarUpdated`, `CalendarDeleted`, `PantryItemAdded`, `PantryItemUpdated`, `PantryItemRemoved`, `NotificationPrefsUpdated`, `ProfileUpdated`. Events carry the resource id and the full updated object (or null for deletes). Bus is a Riverpod `StreamProvider<MutationEvent>` with broadcast semantics.

**FR-REACT-2 Mutation-site convention.** Every mutation handler (service method in features/*/services/*.dart, MCP-writing code, WS inbound frame handler) emits exactly one event on success. Convention is documented once in `app/lib/core/state/README.md` and enforced via `dart analyze` custom lint if feasible (otherwise by CodeRabbit-style review checklist in the epic QA walkthrough).

**FR-REACT-3 Subscriber convention.** Every list/detail provider — new or existing — declares which event types it cares about and calls `ref.invalidateSelf()` (or targeted patch) via `ref.listen(mutationBusProvider, ...)`. Detail providers also patch their cached object in-place when the event carries the full updated payload (no round-trip).

**FR-REACT-4 Home grid refactor.** HomeScreen migrates off imperative `_loadRecipes()` in `initState` to a `homeContentProvider` (Riverpod FutureProvider) that listens to the MutationBus and invalidates on `RecipeCreated` / `RecipeUpdated` / `RecipeArchived` / `MealCreated` / `MealUpdated` / `MealArchived` events. Pull-to-refresh still forces `ref.refresh(homeContentProvider)`. No visible UX change on happy path; the bug ("new recipe doesn't appear until refresh") disappears.

**FR-REACT-5 Imports tab refactor.** `importsSeeAllProvider` subscribes to `ImportItemDismissed`, `ImportItemRetried`, `ImportJobDismissed`. Local `setState`-based list removal is retained (optimistic path) but followed by event emit; the provider reconciles on next poll or on WS/SSE frame if applicable. Activity shell unread count updates via existing 30s poll plus MutationBus fast-path.

**FR-REACT-6 Reconcile-only update style for v1.** All mutations use the reconcile pattern: tap → subtle in-flight state (dimmed row, inline spinner, disabled control) → server responds → list/detail provider invalidates → UI updates. No predictive/optimistic updates for v1 *except* mutations that already have optimistic setState today (dismiss, favorite, check-off) — those keep their optimistic layer and add MutationBus emit on success. Optimistic-everywhere is a polish-pass follow-up epic.

**FR-REACT-7 Failure UX contract.** On mutation failure *after* an optimistic update, the UI reverts to pre-mutation state and a Snackbar surfaces with copy `"Couldn't <verb> <noun>. Tap to retry."` (verb/noun from a per-mutation copy map centralized in `app/lib/core/state/mutation_failure_copy.dart`). Tap-to-retry re-invokes the original handler. No persistent error banner; no silent rollback. Reconcile-only mutations fall back to the existing error-handler pattern (thrown exception → screen-level error state); no change.

**FR-REACT-8 Backend minor gaps.** `POST /import-items/{id}/dismiss` starts returning the full updated `ImportItem.Response` object (not the current partial `(id, dismissed_at, job_dismissed)` tuple). Favorite toggle endpoints (`/recipes/{id}/favorite`, `/meals/{id}/favorite`) return the full resource. All other mutation endpoints already return full objects — no backend change needed.

**FR-REACT-9 No WebSocket expansion in scope.** Existing WS paths (shopping-list items, recipe-book recipe CRUD) remain as-is. When a WS frame arrives, its handler lowers into a MutationBus emit so the downstream convention is identical to a local mutation. No new WS routes, no new connection managers. Cross-device sync for shared meals / calendars / meal_events is **explicitly deferred** to a future epic and is called out in the epic open-questions.

**FR-REACT-10 Audit coverage.** Every mutation site listed in the frontend audit receives a PR test (widget or unit test) that:
1. Renders a list surface that should react to the mutation.
2. Invokes the mutation handler.
3. Asserts the list surface re-renders with the expected new state **without** a manual pull-to-refresh.

This is the regression bar — if the test passes, the "stays stale until refresh" bug class is closed for that surface.

**FR-REACT-11 Double-source-of-truth cleanup.** Where a getIt service (e.g., `ActivityReadProvider`, `ShoppingCartService`) and a Riverpod provider both hold the same resource list, collapse to one source of truth in the migration epic for that feature. Existing WS-driven services keep their StreamController outward API but become thin adapters over MutationBus internally. No rewrite of the WS protocol; purely a client-side consolidation.

### Non-functional constraints

- **No API contract breaks.** FR-REACT-8 (dismiss + favorite) is an additive response-shape change — old clients reading only `id` / bool work unchanged.
- **No infra change.** Zero Terraform, zero env vars, zero new ECS/RDS/Elasticache resources.
- **Performance bar.** MutationBus must not introduce >5ms added latency per mutation on a mid-range device; invalidation storms (one event → many refetches) are mitigated by coarsest-useful-key invalidation and per-subscriber event-type filters.
- **Zero regression** in the two fully-reactive paths today (shopping list, shared recipe book recipe CRUD).
- **Test bar.** Query-count-style assertions where applicable; widget tests for every migrated surface.

### Out of scope (this round)

- Optimistic updates everywhere (polish-pass follow-up).
- Stale-while-revalidate on app resume-from-background (deferred; user can run /dev-plan on it when it becomes a dogfood complaint).
- Cross-device WS broadcasts for meals / calendars / meal_events (explicitly deferred per user call 2026-04-22).
- Offline mutation queuing / conflict resolution (out of scope; separate concern).
- A "Last synced N seconds ago" UI indicator (not requested).

### Success metrics

- **Zero manual-refresh bugs** in the next dogfood week (2026-04-22 → 2026-04-29): no "had to pull-to-refresh to see X" reports from Leo.
- **Every mutation site** in the frontend audit has a passing regression test that verifies cross-surface reactivity.
- **No more than one** MutationBus subscriber per resource domain per surface (no invalidation storms).
- **Dismiss import** and **add recipe** user-visible bug traces (documented in research) are both verifiably fixed with automated regression coverage.

## Addendum — 2026-04-22 — Meal Cook Mode (sectioned steps, interlaced ingredients, persistent resume)

### Context

Recipe cook mode (Epic 6 + `epic-cook-mode-timers` + `epic-cook-mode-polish`) lets a user walk through **one recipe's** steps with a timer column, ingredient strip, and post-cook rating. A Meal is a user-curated collection of recipes (`meals` + `meal_components`, each component = `recipe_id` + `order_index`). Today the user must cook each component separately: open Meal → tap component → back to Meal → tap next component. There is no unified cook flow for a meal.

Separately, cook progress (current step, checked ingredients, active timers) is **entirely ephemeral** — if the user backgrounds + kills the app, the session is lost. For a single recipe that's mildly annoying; for a 3-recipe meal that can span 90+ minutes, it's unacceptable.

### Requirements

**FR-MCM-1 Meal cook mode entry.** `meal_detail_screen.dart` gets a bottom-right FAB "Start Cooking" mirroring the recipe-detail FAB (`recipe_detail_screen.dart:593–599`). Tap → `context.push('/meals/${mealId}/cook')` → mounts `MealCookModeScreen`.

**FR-MCM-2 Meal-cook loader.** `MealCookModeScreen(mealId)` issues (1) `GET /v1/meals/{mealId}` → meal + thin components, (2) N parallel `GET /v1/recipes/{recipeId}` for every component (ordered by `order_index`). Error, offline, and partial-failure states render in the cook palette (reuse `CookModeTheme`). Offline: fall back to `RecipeCache` per-component; if any component is un-cacheable and not reachable, present an explicit "This meal isn't fully available offline — retry when online" error with per-component status.

**FR-MCM-3 Sectioned step traversal.** Steps are grouped per-recipe in component order. The step card shows a **recipe-section header** above each step like `Dressing · 3 / 7` (component name, position within that recipe, total steps in that recipe). Advancing past the last step of component K moves to step 1 of component K+1. Swipe/tap-zone/pill-tap navigation is preserved; the `StepNavigator` pill row is expanded to show **all steps from all components** with inter-recipe visual separators (a thin vertical rule between component groups) and per-pill Semantics that announce the component name ("Dressing, step 3, current").

**FR-MCM-4 Interlaced combined ingredients.** The `IngredientStrip` at the top of meal cook mode renders **one combined strip** built from `aggregate_meal_ingredients(meal)` — the existing backend helper used by "Add meal to shopping list". **No deduplication** — two recipes with "1 cup flour" render as two rows, each with a small per-recipe tag chip ("from Dressing" / "from Salad") so the user can see which recipe needed what. Check-off state is tracked by a stable key (recipe_id + ingredient_index) so reordering or filtering doesn't corrupt it.

**FR-MCM-5 Timer UX is unchanged per step.** Extracted timers (`step.timers`), regex fallback, and the header manual-timer button (`epic-cook-mode-timers`) all work identically on the current step regardless of which component it belongs to. Active timers live in a single meal-level row — a timer started on Dressing step 2 persists visibly while the user walks Salad's steps. Timer labels auto-prepend the component name on disambiguation collision (e.g., two "simmer" timers from different recipes → `"Dressing · simmer"` and `"Salad · simmer"`).

**FR-MCM-6 Per-component post-cook rating.** The post-cook sheet shows **N star rows**, one per component (component name + 5 stars + optional note). Submitting writes one `cooking_logs` row per rated component (0-star = skip that component). Reuse `PostCookFeedbackSheet` widget internally but accept a `List<ComponentRatable>` rather than a single recipe. No new meal-level `cooking_logs` row.

**FR-MCM-7 Persistent resume — both recipe AND meal cook modes.** Cook-mode state (`current_step`, `completed_steps`, `checked_ingredients`, `active_timers[]` with remaining durations, `cooking_elapsed_ms`) persists to SharedPreferences keyed by `recipe_id` for recipe cook and `meal_id` for meal cook. When the user re-enters cook mode for the same target **and** state exists, present a **Resume / Reset** gate sheet BEFORE the cook UI loads:
  - **Resume** — restore state, rebuild active timers with remaining durations (dropping any whose deadline is now in the past; they fire a "While you were away: `X` timer is done" snackbar on mount).
  - **Reset / Start Over** — clear the persisted key, start fresh at step 0.
  - A "Started 2h ago, step 3 of 12" summary line on the gate so the user knows what they're resuming.
  After Post-cook sheet submission, the persisted key is **cleared**. Explicit "Reset" from the cook-mode header (new affordance) also clears it without leaving the screen.

**FR-MCM-8 Remove `CookModeChatSheet` from both cook modes.** Delete `cook_mode_chat_sheet.dart`, its header chat button in `cook_mode_screen.dart`, the `/v1/recipes/{id}/chat` route wiring on the Flutter side, and all related tests. Backend route stays for now (cheap to keep; may be repurposed later). No new chat surface is added for meal cook mode. Rationale: "messy there, want to come back to how we incorporate it" (user call, 2026-04-22).

**FR-MCM-9 Theme reuse.** Meal cook mode uses the same `CookModeTheme` extension introduced in `epic-cook-mode-polish`. If cook-mode-polish hasn't shipped yet, meal cook falls back to `colorScheme` via the same `_resolveCookTimer` helper pattern. No new theme tokens.

**FR-MCM-10 Shared-widget discipline.** `IngredientStrip`, `StepNavigator`, `StepTimersRow`, `ManualTimerSheet`, `TimerCompletionOverlay`, active-timers row, and timer services (`cook_timer_notification_service`, live-activity service) are extracted to a `features/recipes/cook_mode/shared/` folder (or kept in `widgets/` with imports from meal_cook_mode/). Recipe cook mode and meal cook mode are two screens consuming the same widget atoms and a shared controller/plan abstraction (`CookPlan`: an ordered list of `{componentLabel?, recipeId, steps, ingredients}` — where `componentLabel == null` and `length == 1` for single-recipe cook). Single source of truth for gesture handling, timer lifecycle, pill-row rendering.

### Non-functional constraints

- **Backend additive only.** FR-MCM-4 reuses existing `aggregate_meal_ingredients` untouched. No schema changes. No new endpoints. (The N-recipes-by-id fetch is client fan-out.)
- **No infra change.** Zero Terraform, zero env vars, zero new AWS resources.
- **Performance bar.** Cold open of a 3-component meal cook is ≤ 1.2s on a mid-range device on good network (sum of the N parallel recipe GETs, bounded by the slowest). Offline cache fallback ≤ 400ms.
- **Persistence bar.** Writes to SharedPreferences must be debounced (≥ 250ms window) — step-advance, ingredient-toggle, and timer-tick all mutate state; naive sync-on-every-setState is too chatty.
- **Test bar.** Per-epic widget tests mirror the existing cook-mode test pattern (`cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`). A new `meal_cook_mode_test.dart` + `meal_cook_mode_ingredients_test.dart` + `cook_mode_resume_test.dart` anchor the new surface.

### Out of scope (this round)

- **No cross-recipe step scheduler** — no "start the sauce while the pasta boils" smart interleaving. Steps remain grouped per recipe in component order. (User call 2026-04-22: "headers make the most sense, like to know which recipe I'm on".)
- **No ingredient deduplication / summing** — raw aggregation only (user call 2026-04-22).
- **No meal-level cook log** — ratings are per-component rows in `cooking_logs`; no new `meal_cooking_logs` table.
- **No AI chat** in either cook mode — explicit removal, not a deferral (user call 2026-04-22).
- **No cross-device resume** — persistence is local SharedPreferences. Cooking on iPhone and resuming on iPad is out.
- **No `MealComponent.course`** / appetizer-main-side concept. Components are ordered only by `order_index`.
- **No backfill of old recipe cook sessions** — if a user had a recipe cook session in-flight before FR-MCM-7 ships, there's nothing to resume; they see a fresh start. Not a regression.

### Success metrics

- **Functional completeness:** a user can open a 3-component meal, cook through all components end-to-end, rate each, and see per-component rows in `cooking_logs`.
- **Resume works both directions:** force-kill mid-cook, reopen → Resume sheet appears; pick Resume → state restored (step, checks, timers). Pick Reset → fresh state, old state gone.
- **Zero chat references remaining** in `app/lib/features/recipes/cook_mode/**` after the chat-removal epic lands (enforced by grep gate).
- **Per-component ingredient tags visible** on every ingredient chip in meal cook mode; user can tell which recipe each ingredient came from.
- **Shared widget usage:** `IngredientStrip`, `StepNavigator`, `StepTimersRow`, `ManualTimerSheet` each have exactly one definition, consumed by both recipe and meal cook modes.

## Addendum — 2026-04-22 — Extractor Richer Ingredient Extraction (softened units, JSON-LD parse pass, convertible-unit bias)

### Context

Two concrete ingredient-extraction bugs surfaced from dogfooding:

1. **"1 clove garlic" loses the `clove` unit.** The AI extractor (ai/vision/text) was rewritten in `riip-3` (commit `9245e68`, 2026-04-18) to force units into a 19-token canonical enum via the hard rule *"use EXACTLY one of these tokens… Do not write out full words."* Even though `clove` IS in that canonical set, the force-the-enum framing combined with a conservative "only include what's clearly there" stance causes the LLM to occasionally fold `clove` into the ingredient `name` field instead of emitting it as `unit`. Review Import then shows `[      ] [     ] [clove of garlic]` — the quantity and unit are missing in the UI.

2. **"300 gram of vinegar" loses BOTH quantity and unit on URL imports.** Root cause: `json_ld.py` (`libraries/utils/utils/services/recipe_extractors/json_ld.py:141-145`) creates `ExtractedIngredient(text=ing_text.strip(), quantity=None, unit=None, name=None)` for every entry in the Schema.org `recipeIngredient` array — the spec defines that field as a plain-string list, not a structured one, so JSON-LD has no qty/unit/name/notes to pull from. Those `None`s ride all the way through `_serialize_recipe` → `parsed_recipe.ingredients[]` → the review screen, which falls back to putting the entire raw string into the `name` field (`ingredient_edits_mapping.dart:22-26`). The user sees one big unstructured string instead of `[300] [g] [vinegar]`.

Both bugs collapse into one underlying issue: **the extractor's ingredient-level fidelity is too conservative** — for prompt-driven extractors because the canonical-enum rule is too strict, and for JSON-LD because no parsing pass runs against its string-valued ingredients. Leo's ask:

> I actually want the ability for the unit to be whatever it wants to be, but to err on the side of the enum we set that is easiest. Also though values will be the most "transferrable" to other unit types… Update the prompt to make sure that we always input the quantity if it has access to it and also the notes and unit.

Decoded via 2026-04-22 planning session:

- **Q1/A — Soften the canonical stance, don't expand the enum.** The 19-token enum stays as the *preferred* list. The prompt changes from "EXACTLY one of these tokens" to "prefer these tokens; if the source uses a more accurate freeform word (stalk, bunch, packet, sprig, head, can, sheet, strip, piece), emit it literally." Alias table + `normalize_unit_display` still coerce common spellings (tablespoon→tbsp). Non-canonical units that survive normalization persist through the pipeline as-is.
- **Q2/A — JSON-LD ingredient-parse-only AI pass.** When `json_ld.py` yields text-only ingredients (the Schema.org default), run a focused AI parse pass — not the full AI extractor, just an ingredient-string-list-in, structured-ingredient-list-out prompt — via `gpt-4o-mini`. Cost is ~$0.0001 per URL import. Recipe-level fields (name, description, times, servings, source) still come from JSON-LD as authoritative.
- **Q3/B — Bias toward convertible units.** When the source is ambiguous between a count unit and a measurable one (e.g., "half an onion" vs "1/2 cup onion"), the prompt instructs the model to prefer the convertible unit (`cup`, `tbsp`, `tsp`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `fl oz`) over the count unit. Count units (`clove`, `pinch`, `each`, `slice`, `dash`, `mg`, `gallon`, `quart`, `pint`, plus freeform fallbacks) survive unchanged when the source explicitly uses them. This is future-proofing for a later US↔metric conversion feature.
- **Q5/A — One epic.** `epic-extractor-richer-ingredients` ships the soft-prompt + JSON-LD parse + eval fixtures + alias-table seed expansion as one cohesive fix.

### Requirements

**FR-ERI-1 Prompt softening (ai/vision/text extractors).** `unit_prompt.py::unit_rule()` is rewritten. Today's rule (`riip-3`):

> - "unit": use EXACTLY one of these tokens — `tsp`, `tbsp`, `cup`, `fl oz`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `each`, `pinch`, `dash`, `clove`, `slice`, `mg`, `gallon`, `quart`, `pint`. Do not write out full words. Do not add trailing punctuation…

New rule shape:

> - "unit": **prefer** one of these tokens where applicable: `tsp`, `tbsp`, `cup`, `fl oz`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `each`, `pinch`, `dash`, `clove`, `slice`, `mg`, `gallon`, `quart`, `pint`. If the source uses a more accurate freeform unit word that isn't in this list (e.g., `stalk`, `bunch`, `sprig`, `head`, `can`, `packet`, `stick`, `sheet`, `strip`, `piece`, `sachet`, `jar`, `bottle`, `bar`), emit that word literally in lowercase singular form. **When the source is ambiguous between a convertible unit (cup, tbsp, tsp, ml, l, g, kg, oz, lb, fl oz) and a count unit, prefer the convertible one** — it lets us convert later. Use null for count-of-item when the item itself is uncountable ("salt to taste" → unit: null). Never include the number or ingredient name here.

Feature flag `EXTRACTOR_SOFTEN_UNIT_RULE` (default **true**) gates the new rule. When false, `unit_prompt.py` returns the current `riip-3` strict rule verbatim (clean rollback path).

**FR-ERI-2 Aggressive qty/unit/notes capture.** Each extractor prompt's ingredient section is augmented with an explicit instruction: *"For every ingredient line, always extract `quantity`, `unit`, and `notes` when they appear in the source, even if the quantity is a fraction, a range, or implied by context (e.g., '1/2', '1–2', 'a'). Notes capture preparation hints: 'minced', 'melted', 'room temperature', 'to taste'."* Worked examples are added for:
- `"1 clove garlic, minced"` → `{quantity: 1, unit: "clove", name: "garlic", notes: "minced"}`
- `"300 gram of vinegar"` → `{quantity: 300, unit: "g", name: "vinegar", notes: null}` (after alias-table coercion of `gram` → `g`)
- `"2 stalks celery, chopped"` → `{quantity: 2, unit: "stalk", name: "celery", notes: "chopped"}` (freeform unit passes through)
- `"Salt, to taste"` → `{quantity: null, unit: null, name: "salt", notes: "to taste"}`
- `"1/2 cup olive oil"` → `{quantity: 0.5, unit: "cup", name: "olive oil", notes: null}`

**FR-ERI-3 JSON-LD ingredient parse-only pass.** A new module `libraries/utils/utils/services/recipe_extractors/ingredient_parse.py` exposes `parse_ingredient_strings(strings: list[str], openai_client) -> list[ExtractedIngredient]`. When `JsonLdExtractor` successfully extracts recipe-level fields AND its raw ingredient list is string-valued (the Schema.org default), `extract_recipe_from_html` / `extract_recipe_from_url` invokes this pass on the string list and replaces the text-only ingredient list with the parsed structured list. Recipe-level fields (name, description, prep/cook/total times, servings, source, yield, cuisine, category) still come from JSON-LD unchanged. The parse pass uses `gpt-4o-mini`, a focused prompt (ingredients-only — no recipe context), and supports batch sizes up to ~50 ingredients per call. Feature flag `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` (default **true**). When false, `json_ld.py` behaves as today (text-only ingredients, structured fields null).

**FR-ERI-4 Normalize-on-write still runs.** The output of FR-ERI-3's AI parse pass flows through the same `normalize_unit_display` guard as every other write path (`riip-2`). So `gram` → `g` happens on the backend regardless of which pipeline produced the ingredient. `300 gram of vinegar` → JSON-LD-ingredient-parse → `{unit: "gram"}` → normalize → `{unit: "g"}` persisted.

**FR-ERI-5 Expanded alias-table seeds.** The `unit_aliases` table is seeded with ~15 additional entries covering the common freeform unit words that the softened prompt will now accept: `stalks` → `stalk` (new canonical), `bunches` → `bunch` (new), `sprigs` → `sprig` (new), `heads` → `head` (new), `cans` → `can` (new), `packets` → `packet` (new), `packs` → `packet`, `sticks` → `stick` (new), `sheets` → `sheet` (new), `strips` → `strip` (new), `pieces` → `piece` (new), `sachets` → `sachet` (new), `jars` → `jar` (new), `bottles` → `bottle` (new), `bars` → `bar` (new). These "new canonicals" are freeform-pass-through values — they're NOT added to the 19-token `CANONICAL_UNIT_TOKENS` enum in `unit_prompt.py`. The alias table treats them as canonical destinations for plural→singular normalization only. A data migration reverts cleanly.

**FR-ERI-6 Eval fixtures for ingredient fidelity.** A new eval metric `ingredient_field_completeness` measures, per fixture, what fraction of ingredients have each of {quantity, unit, name, notes} populated correctly vs. ground truth. Target ≥ 0.85 on the extractable-field denominator (i.e., fields the source genuinely has — not hallucinated). Three net-new fixtures anchor the historically-broken cases:
1. `1_clove_garlic_minced.jsonld` — a JSON-LD source with `recipeIngredient: ["1 clove garlic, minced", "2 tbsp olive oil"]`. Ground truth: `[{q:1, u:"clove", n:"garlic", notes:"minced"}, {q:2, u:"tbsp", n:"olive oil"}]`. Verifies FR-ERI-3.
2. `300_gram_vinegar_urlimport.jsonld` — JSON-LD source with `recipeIngredient: ["300 gram of vinegar", ...]`. Ground truth: `{q:300, u:"g", n:"vinegar"}`. Verifies FR-ERI-3 + FR-ERI-4.
3. `stalks_celery_aiprompt.txt` — plain-text source for AI extractor: `"2 stalks celery, chopped"`. Ground truth: `{q:2, u:"stalk", n:"celery", notes:"chopped"}`. Verifies FR-ERI-1 (freeform unit pass-through) + FR-ERI-5 (alias-table plural→singular).

**FR-ERI-7 Confidence-penalty interaction.** `efi`'s inference penalty applies to **recipe-level** inferred fields. This epic's changes are about **ingredient-level** extraction fidelity and do not alter the confidence score path. No interaction. Ingredient-level inference remains deferred to a future `epic-extractor-ingredient-inference` (per `efi`'s scope decision).

### Non-functional constraints

- **Cost.** The JSON-LD parse pass adds ~$0.0001 per URL import (≈ 200 tokens prompt + 200 tokens output via gpt-4o-mini). At expected dogfood volume (~10 URL imports/day) that's under $0.001/day. Documented; not a gate.
- **Latency.** One extra OpenAI round-trip on URL imports that have JSON-LD with text-only ingredients. Budget: P95 < 2s added latency; P99 < 4s. Measured in eval output and `error_logs` structured latency events.
- **Idempotency.** The parse pass MUST be deterministic-ish for the same input string — temperature 0. Re-running the same JSON-LD source yields the same structured ingredient list (within LLM noise).
- **Backwards compatibility.** Legacy `parsed_recipe` rows in the DB are unchanged. The softened prompt applies only to new extractions. No retroactive fix-up or migration.
- **Flag-off parity.** When both `EXTRACTOR_SOFTEN_UNIT_RULE=false` and `EXTRACTOR_JSON_LD_INGREDIENT_PARSE=false`, behavior is 100% identical to pre-ERI. Verified by a test that pins a fixture's output under both flag states.
- **Coverage.** `services/api` stays at 100%. `libraries/utils` coverage is not reduced.

### Out of scope (this round)

- **Expanding the `CANONICAL_UNIT_TOKENS` enum** — the 19-token enum is the prompt's *preferred* list only; we're not adding new tokens to it. Growing the enum would require coordinated changes to `units` seed table, Flutter `kCuratedUnits`, and alias table; out of scope.
- **Per-ingredient inference of missing fields** (the "best-guess the quantity when source doesn't say" pattern from `efi` applied to ingredients). Deferred to `epic-extractor-ingredient-inference`.
- **Unit conversion engine** — converting `1 cup` to `240 ml` downstream. This epic biases extraction toward convertible units but doesn't actually convert. Separate future epic.
- **OCR / vision / photo paths for the JSON-LD parse pass.** Vision/OCR extractors already produce structured ingredients via their own prompts (which get the FR-ERI-1 softening). They don't go through JSON-LD.
- **Parser service changes.** The user said "Maybe just the extractor honestly." No changes to `services/parser/` — the URL → HTML fetch path is unchanged; only the downstream JSON-LD handling inside `libraries/utils/.../recipe_extractors/` is touched.
- **Flutter changes.** Review Import, the wizard, recipe edit, `UnitInput`, and `StructuredIngredientRow` are unchanged. Research confirmed these already render freeform units correctly (if unit is non-canonical, the unit field displays the literal word and `coerce-on-blur` via `SessionAliasMap` snaps to canonical on user touch). No Flutter work in this epic.
- **Retroactive backfill** of already-extracted recipes. New extractions benefit; historical `parsed_recipe` blobs stay as-is.
- **User-facing surfacing of the parse-pass latency.** No new loading copy, no progress indicator. The pass fits under existing URL-import latency budgets; user sees the same "Importing recipe…" state.

### Success metrics

- **`1 clove garlic, minced` and `300 gram of vinegar` eval fixtures both pass at ≥ 0.95 field-completeness** after this epic ships. Automated, reproducible.
- **URL-import ingredient-field-completeness moves from today's baseline (~0.55 on JSON-LD-dominant sources — measured in Phase 2 research) to ≥ 0.85.**
- **No regression** in the AI/vision/text extractor eval fixtures' field-completeness — the softened prompt does not decrease capture rate on the cases that worked under `riip-3`.
- **Zero `UnitAliasMiss` error_log rows** for the 15 new seeded freeform units after the alias-table migration ships (Leo cooks from a recipe with "2 stalks celery", URL import works, no miss logged).
- **Feature flags flippable without redeploy** — both `EXTRACTOR_SOFTEN_UNIT_RULE` and `EXTRACTOR_JSON_LD_INGREDIENT_PARSE` flip via ECS task-def env vars, read at call time.


## Addendum — 2026-04-22 — Cook Mode Redesign (toggleable per-recipe flow)

### Scope

Meal cook mode (`MealCookModeScreen`) is functionally correct but three real-kitchen behaviors emerged during dogfood:

1. **Downtime interleave.** Real meals have idle windows: "let sit 5 min", "rest 10 min", "bake 25 min". Today the user sits staring at the timer, because the flow is strictly sequential (finish all of Dressing, then Salad, then Chicken). They want to start Salad's prep *during* Dressing's rest, then return.
2. **Ingredient legibility.** The compact 80dp horizontal strip with 11px ALL-CAPS "INGREDIENTS" label and tiny per-chip source tags is hard to read mid-cook. User verbatim: "I can barely see the ingredients." They want the full grouped list surfaced permanently, with bigger, clearer text and recipe grouping as the source-of-truth.
3. **Layout drift.** Paddings, section headers, the redundant X button in the header, and an Expand/Collapse affordance that no longer earns its keep have all accumulated. Both cook modes (recipe + meal) feel slightly "off" spatially.

The redesign reshapes meal cook mode around **per-recipe step tracking with a toggle bar**, and applies a shared polish pass to both cook modes. It does not change what gets persisted philosophically (still one session, still `CookSessionPersister`-backed), but it does require a schema-v2 upgrade of the persisted payload.

### Vision — end-user flow (meal mode)

A user starts cooking a 3-recipe meal (Dressing, Salad, Grilled Chicken). The screen layout, top-to-bottom:

1. **Top bar** — back button, recipe/meal title, overflow menu. The current X close button is removed (redundant with back).
2. **Active timers row** (conditional) — horizontal-scroll chips. Each chip shows `{RecipeName} · {MM:SS}` (e.g., `Dressing · 0:17`) so the user always knows which recipe a timer belongs to.
3. **Full ingredient list** — always expanded, grouped by recipe with per-group headers (`Dressing`, `Salad`, `Grilled Chicken`). Bigger chip text (~14px names, accented quantities), no per-chip source tag (the group header is the source). No Expand/Collapse button. Scrolls internally if taller than its allotted area. The old `INGREDIENTS` ALL-CAPS label is removed.
4. **Recipe toggle bar** — horizontal scrollable row of pills, one per component recipe, each showing `{RecipeName} {currentStep}/{totalSteps}`. Active pill styled distinctly; completed pills get a checkmark and stay tappable (for review/rewind). A pill whose recipe has a timer firing pulses briefly. In single-recipe cook mode the toggle bar is not rendered.
5. **Step card** — the current step's instruction text for the active recipe. No `Dressing · 1 / 7` section header above it anymore (the toggle bar + bottom progress indicator carry that signal). Inline timer buttons below the instruction if the step has extracted/regex timers.
6. **Bottom progress indicator + nav** — linear progress bar + `5 / 7` text both scoped to the **active recipe only** (not meal-flat). Prev / Next / Done buttons. On last step of a recipe, Next **auto-advances to the first unfinished recipe** (in plan order); if all recipes are finished, Next opens the post-cook rating sheet.
7. **State model.** The flat `currentStep` int is replaced by a `Map<recipeId, stepIndex>` tracking each recipe's position independently, plus a `String activeRecipeId` pointer. Toggling a pill updates the pointer; step nav updates only that recipe's entry. Timer completions on inactive recipes trigger a pulse + prefixed label, not an auto-switch.

### Vision — end-user flow (recipe mode, shared polish)

Single-recipe cook mode inherits the same shared polish: X button removed, `INGREDIENTS` ALL-CAPS header removed, Expand/Collapse button removed (ingredients always shown), chip text enlarged, padding cleanup. No toggle bar (only one recipe). No per-recipe state map (a single recipe already is "one recipe"). Behavior is otherwise identical.

### Locked decisions (from 2026-04-22 planning session)

1. **Toggle bar placement.** Directly **below** the full ingredient list, above the step card. Hidden in single-recipe mode.
2. **Ingredient list shape.** All ingredients shown, always expanded, grouped by recipe (not a filtered-to-active-recipe view). No compact/expanded toggle.
3. **Chip readability.** Drop `INGREDIENTS` ALL-CAPS header. Drop per-chip source tag (group sections own that context). Bigger chip text, prominent quantities.
4. **Section header above step card.** Dropped entirely. The toggle bar + per-recipe progress indicator replace it.
5. **Bottom progress indicator.** Scoped to active recipe only (`5 / 7`), not meal-flat.
6. **End-of-recipe behavior.** Next on last step auto-advances to the first unfinished recipe. Post-cook rating sheet still fires once at meal-end (one sheet, one row per cooked recipe).
7. **Cross-recipe timer completion.** Completion snackbar + pulse on the owning recipe's toggle pill. No auto-switch. Active-timers row chips show recipe-name prefix (`Dressing · 0:17`) continuously, not just on completion.
8. **X button in cook-mode header.** Removed. Back button already exits; X was redundant.

### Non-functional constraints

- **Persistence schema bump.** `CookSessionPersister` payload schema moves v1 → v2. v1 sessions (single flat `currentStep`) are read with a migration: if `target_kind == meal`, unpack the flat index via `plan.stepAt()` into the per-recipe map; if `target_kind == recipe`, the map has one entry. v1 load path never crashes; unparseable sessions are cleared silently.
- **Backwards compatibility.** Recipe cook mode's behavior is unchanged apart from the visual polish. Existing recipe-cook tests keep passing with only widget-finder updates (no assertion rewrites).
- **Test coverage.** New meal-cook-toggle interactions get a dedicated test file; the per-recipe step map has a unit test; the v1 → v2 migration has a round-trip test.
- **No backend changes.** No API, no schema, no infra. Epic is Flutter-only.
- **Real-kitchen usability.** The `cook_mode_gesture_test.dart` 25%/50%/25% swipe-zone behavior is preserved; swipes stay within the active recipe (swiping past a recipe's last step auto-advances; swiping back from a recipe's step 0 rewinds to the prior recipe's last step iff that recipe exists and has been entered).

### Success metrics

- User can start Dressing, set a rest timer, switch to Salad, return to Dressing's exact step when the timer fires, without a resume gate or state loss. Manual repro checklist.
- Chip text legibility verified in-hand at arm's length (no magnification). No regression in Dynamic-Type / accessibility scaling.
- Existing cook-mode test files pass after widget-finder updates; new `meal_cook_mode_toggles_test.dart` pins toggle bar + per-recipe progress + cross-recipe timer + auto-advance + persister v2 migration.
- Zero new `error_logs` rows from the persister migration path (verified post-deploy via `audit_errors.py --service=app --window=7d` after the roll).

### Out of scope (this round)

- Smart step interleaving (i.e., proposing "start Salad step 1 now since Dressing is resting"). Toggling remains user-driven.
- Per-recipe finish/complete buttons (the auto-advance covers the common case; an explicit "Finish this recipe" button would be a future add).
- Timer mode where firing a timer auto-switches to the owning recipe. User said no — pulse only.
- Android-specific Live Activity variants for the per-recipe timer prefix. Existing notification copy path already has recipe name available; prefix reuses it.
- Reordering recipes mid-cook. The plan order is fixed at entry.


## Addendum — 2026-04-23 — Frontend Performance Audit + Client-Side Analytics

### Scope

User observed a stream of repeated network calls in Chrome DevTools while running Flutter web — particularly to endpoints ending in "items" (primarily `/v1/import-items` and its siblings). The server-side query tuning epic (`epic-perf-backend-query-tuning`, 2026-04-21) closed the known N+1s and the infra floor was raised (`epic-perf-infra-and-measurement`) — but the **client-side fetch surface** has not had a holistic audit, and **client-observed latency** has no instrumentation. Today `analyze_latency.py` reads server-side `request_latencies` + `task_latencies`; there is no equivalent for what the Flutter app experiences (screen paint, route transition, frame jank, cold-start).

Phase-2 audit (2026-04-23) surfaced concrete client-side fetch-reduction targets and a gap in client-side observability. This addendum packages both into three parallel epics that ship together as the "Performance Health v2" initiative.

### Functional requirements

**FR-PERF2-1 Shared recipe-books provider.** Every Flutter surface that today calls `apiClient.getRecipeBooks()` directly (home, recipe detail, all import entry screens) reads from a single Riverpod `recipeBooksProvider` with `ref.keepAlive()` + MutationBus invalidation. No direct `getRecipeBooks()` call survives outside the provider body. QA verifies via grep on `app/lib/`.

**FR-PERF2-2 Collapse N+1 import-item fetches.** Imports tab + See-all currently issue `listImportItems(jobId)` once per job (10 jobs = 10 serial GETs). Backend accepts either `GET /v1/import-items?job_ids=<csv>` (additive, non-breaking) OR `GET /v1/import-jobs?include=items` (flag on the existing endpoint). Flutter caller becomes one request per page regardless of job count. Response-shape choice decided in party-mode.

**FR-PERF2-3 Activity-poll + MutationBus dedup.** When a MutationBus `ImportItem*` event triggers a silent reload, the next scheduled 30s `ActivityReadProvider` tick is suppressed (`_lastReloadAt` floor). Prevents double-fetch during active import sessions.

**FR-PERF2-4 Notifications-tab single-fetch-on-mount.** Today mount calls `getActivities()` + `refreshUnreadCount()` back-to-back. `getActivities()` response gains a nullable `unread_count` header field (or response-level field, additive); the tab uses that count directly. `refreshUnreadCount()` call on mount is deleted.

**FR-PERF2-5 Lazy `listMealsInBook()`.** Book detail screen defers the `mealsByBookProvider(bookId)` fetch until the user taps the Meals tab inside the book detail. Mounting the screen (or scrolling through a book grid on home) does not pre-fetch per-book meals.

**FR-PERF2-6 Session-cache TTL.** Providers currently marked `ref.keepAlive()` with session-only lifetime (books, profile, home content, pantry, notification prefs) gain an optional staleness timer. A `maxAge` parameter (default 10 minutes for books/profile/prefs; 5 minutes for home content) triggers a silent revalidation on next read after the TTL window. MutationBus invalidation path is unchanged.

**FR-PERF2-7 Response-shape trims.** `GET /v1/recipes/{id}` accepts `?include=ingredients,steps,comments,versions` (additive). Default omits versions + comments (moved to lazy fetch on detail tab expand). `GET /v1/import-items/{id}` accepts `?include=parsed_recipe` (default false; caller explicitly opts in — telemetry viewer already does). No breaking changes; omitted fields return `null` or absent keys.

**FR-PERF2-8 Image-cache sweep.** Every remaining `Image.network(` in `app/lib/features/calendar/**` (9 sites) and `app/lib/features/recipes/**` (7 sites outside cook mode) converts to `CachedNetworkImage` with equivalent `fit`/`errorBuilder`/`width`/`height`. CI grep guard blocks re-introduction of `Image.network(` in hot paths.

**FR-PERF2-9 Dio request-dedup interceptor.** New Dio interceptor coalesces in-flight identical GETs (method + path + query + Authorization subject) so parallel callers see one network roundtrip. Applies to GET only; writes pass through. 300ms coalesce window.

**FR-PERF2-10 Client-latency ingest endpoint.** New backend resource `POST /v1/client-latencies` accepts batched JSON payloads (max 100 events per call). Body schema:
```
{ events: [{ type, route|endpoint|metric_name, duration_ms, platform, app_version,
             device_class, user_id (server-derived), created_at }] }
```
`type` enum: `route_paint`, `app_start`, `network_request`, `frame_jank_p95`, `metrickit_daily`, `jankstats_daily`, `web_navigation`. Payloads persist to new `client_latencies` table (mirrors `request_latencies` shape + platform/app_version/device_class columns).

**FR-PERF2-11 Flutter Navigator observer + PostFrameCallback instrumentation.** A `PerfNavigatorObserver` records `didPush` → first `addPostFrameCallback` of the new route's first build; emits `route_paint` event with route name + duration. Events batch in memory (flush every 30s or 50 events, whichever first) and POST to `/v1/client-latencies`.

**FR-PERF2-12 Cold-start timing.** `main()` awaits `WidgetsBinding.instance.endOfFrame` after `runApp`; emits `app_start` event once per launch with duration from `DateTime.now()` captured at the top of `main()`.

**FR-PERF2-13 Dio client-timing interceptor.** The existing Dio interceptor records `onRequest` timestamp; `onResponse`/`onError` emits `network_request` with duration + endpoint pattern (path-param-redacted). Piggybacks on the auth/error interceptor chain.

**FR-PERF2-14 Frame jank aggregation.** `SchedulerBinding.instance.addTimingsCallback` aggregates per-minute p95 of `totalSpan` (build + raster) and flushes one `frame_jank_p95` event per minute per active route. Events include build-span p95 and raster-span p95 separately.

**FR-PERF2-15 Firebase Performance Monitoring enabled.** `firebase_performance: ^0.10.x` added to `pubspec.yaml`; `FirebasePerformance.instance.httpMetric(...)` wired on the existing Dio interceptor. Auto-captures app-start + screen-rendering + HTTP traces. No custom dashboards; dashboard is the Firebase console. Cross-checks the custom pipeline; secondary source of truth.

**FR-PERF2-16 iOS MetricKit payload receiver.** New iOS `MetricKitReceiver` (Swift) in `app/ios/Runner/` implements `MXMetricManagerSubscriber`; daily aggregate payloads (`MXMetricPayload`) ship via platform channel to Dart, which POSTs as `metrickit_daily` events. Captures hang rate, launch time, scroll hitch, memory warnings, energy impact.

**FR-PERF2-17 Android JankStats receiver.** `androidx.metrics:metrics-performance` JankStats added to `app/android/app/build.gradle`. `JankStats.createAndTrack` on the main activity; per-route dropped-frame stats flush as `jankstats_daily` events via platform channel.

**FR-PERF2-18 Web Navigation Timing bridge.** On Flutter web, `dart:html` `window.performance.getEntriesByType('navigation')` + `PerformanceObserver` for `paint` entries bridge to the same `/v1/client-latencies` endpoint as `web_navigation` events. No Firebase/MetricKit equivalent; web uses the browser API.

**FR-PERF2-19 `analyze_latency.py --section client`.** The existing ops script gains a `client` section that reads from `client_latencies` and reports p50/p95/p99 per route + per endpoint + per platform. Combined `--section all` renders server + client side-by-side so admins can tell "slow because of backend" from "slow because of frontend paint".

**FR-PERF2-20 Admin dashboard client-side view.** `/admin/metrics` (Flutter-based admin dashboard) gains a Client tab with the same tables + sparklines but sourced from `client_latencies`. Filters: platform (ios/android/web), app_version, route.

**FR-PERF2-21 Debug perf overlay (debug builds only).** `kDebugMode`-gated long-press trigger on a corner of the home screen toggles a floating overlay listing the last N HTTP requests with durations, sorted by most recent. Useful for dogfood self-audit.

**FR-PERF2-22 Per-screen fetch-count budget regression guard.** A new integration test harness drives each top-level screen in a `patrol`-style flow; asserts HTTP call count against a per-screen budget (committed as a YAML file). Failing the budget fails CI. Prevents accidental re-introduction of duplicate fetches.

**FR-PERF2-23 `bin/perf-audit` repeatable audit command.** A shell script that (a) runs the Flutter integration test harness in budget-capture mode (records actual call counts vs budget, no assertion), (b) fetches current p95s from `analyze_latency.py --section all`, (c) prints a diff table vs the committed baseline. Usable standalone or wrapped in the regression guard.

### Non-functional constraints

- **Response-shape changes are additive only.** Any `?include=` or `?fields=` parameter defaults to today's response shape. No breaking changes for shipped clients. Old clients pin their current behavior by omitting the parameter.
- **Request-dedup correctness.** Dedup applies only to GET; any header difference (e.g., different `If-None-Match`) prevents coalescing. Writes never coalesce. Dedup window is 300ms — short enough that no user-observable staleness is introduced.
- **Client-latency ingest cost.** `POST /v1/client-latencies` is a fire-and-forget batched write. Batch size capped at 100 events; batches rejected with 413 beyond that. Ingest handler is sync-DB write with no task fan-out. Expected load: ~500 events/minute per user at peak.
- **Privacy.** Client-latency events carry `user_id` (derived server-side from JWT) for aggregation; no PII in event bodies. Route names are redacted of path params client-side before ingest (e.g., `/recipes/abc123/edit` → `/recipes/:id/edit`).
- **No PII in Firebase Performance.** Firebase Perf's auto-captured HTTP traces use path-param URLs by default. We do not customize trace names with recipe IDs or user IDs.
- **MetricKit / JankStats ship only in release builds.** Debug/profile builds skip the receiver hookup to avoid polluting dev numbers.
- **Sampling.** Firebase Perf stays at Firebase's default (~100% up to quota). Custom client-latency pipeline is 100% of sessions; batch-and-flush keeps overhead bounded. Sampling knob is on the roadmap, not in v1.
- **Backfill.** No backfill of client_latencies. The table is empty at ship; dashboards show "no data for this window" until users start reporting.
- **Cost.** Firebase Performance free tier covers expected volume (~50 users, well under the 500k events/day free cap). Custom pipeline writes to the existing Postgres instance — no new DB infrastructure. MetricKit + JankStats are free OS APIs.
- **Coverage.** `services/api` stays at 100% coverage. Client-latency tests cover the ingest endpoint + serializer; Flutter observer tests cover the Navigator observer emitting a single event per route push.
- **Binary-size delta.** Adding `firebase_performance` is ~300KB on iOS, ~250KB on Android. Documented; not a gate.

### Out of scope (this round)

- **Session replay / user-path reconstruction.** Sentry/Datadog-style replay is deferred — Firebase Performance is the secondary source.
- **Error tracing** (beyond what Crashlytics already does). Separate epic if warranted.
- **Server-side per-user cost tracking / budget enforcement.** Existing AI cost caps are unchanged; perf analytics doesn't add cost enforcement.
- **A/B perf experiments.** Feature flags for perf features (e.g., dedup on/off) exist but no experimentation framework.
- **Predictive prefetch / route warming.** Out of scope; pure reactive pipeline.
- **Offline queue for client-latency events.** If the ingest POST fails, events are dropped. No retry, no on-disk queue. Acceptable for telemetry.
- **Pre-render critical screens at app start.** Out of scope; cold-start timing only measures baseline, not optimizes.

### Success metrics

- **Fetch count baseline diff:** a fresh Home → Activity Hub → Recipe detail flow issues **≥30% fewer HTTP GETs** than the pre-epic baseline (captured 2026-04-23 via Chrome DevTools HAR). Measured by `bin/perf-audit`.
- **Zero duplicate `getRecipeBooks()` calls** per app session. Grep guard + integration test.
- **Route-paint p95 visible in admin dashboard** within 5 minutes of a release. Admins can answer "is the app slow" with a URL, not a guess.
- **Firebase Performance dashboard ≥90% agreement** with custom pipeline on app-start + per-screen p95 (within 20% tolerance). Cross-check as sanity test.
- **MetricKit + JankStats daily payloads flowing to `client_latencies`** with `platform='ios'` / `platform='android'` within 7 days of dogfood rollout.
- **CI catches a synthetic regression** — deliberately adding a duplicate `getRecipeBooks()` fails the per-screen budget test.
- **`bin/perf-audit` runs < 5 minutes** end-to-end on CI. Usable in PR workflows.
