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
