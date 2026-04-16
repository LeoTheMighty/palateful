# Epic: Pantry Management — Non-Invasive Loop

## Overview

Ship a complete, usable pantry feature that stays out of the user's way. The pantry auto-populates when shopping items are purchased, auto-decrements when meals are cooked, and exposes a manual UI as the trust-builder and fallback for everything the automation misses. Shelf-life is shown as a *helpful estimate*, not tracked with promised accuracy.

The MVP schema (`pantries`, `pantry_users`, `pantry_ingredients` with `expires_at`) and read-side tooling (`GetPantryTool`, `check_pantry` dedup on shopping-list population) already exist. This epic is about connecting the unwritten write path, adding the Flutter surface, and attaching a shelf-life estimator good enough to be useful.

## Scope Themes

Three themes, one epic:

1. **Writable backend** — the CRUD endpoints and shelf-life estimator that everything else in the epic depends on.
2. **Non-invasive event hooks** — shopping-list purchases and cooked meals mutate the pantry as a side-effect of actions the user was already taking.
3. **Manual UI surface** — a pantry list screen, item editor, and "Use me up" CTA so the user can *see* what the automation thinks they have, correct it, and act on it.

## Design Principles (from Party Mode discussion)

1. **Pantry is a trust-builder for invisible automation** — users won't trust the shopping-list's "you already have" dedup until they can see their pantry state. The manual UI isn't a separate feature; it's the credibility anchor for the hooks.
2. **Side-effects, not inline mutations** — shopping-list and meal-event code paths emit events; a pantry subscriber reacts. Removing pantry later is one subscriber deletion, not a hunt-and-peck.
3. **Best-effort decrement on unit mismatch** — when the meal-cooked hook can't normalize units (recipe says "1 cup" but pantry has "2 onions"), it skips silently and logs. Never block the user's "mark as cooked" action on a unit conversion failure.
4. **Shelf-life is a display feature, not a tracking feature** — static seed JSON per category × storage location. No promises of accuracy, no AI calls on hot paths.
5. **Fuzzy display, absolute storage** — DB stores `expires_at` as a real timestamp; UI shows "~5 days" with a color bar. Humans plan in weeks, not UTC seconds.
6. **Urgency as the primary sort** — the pantry list groups by Expiring Soon / Fresh / No Date, not alphabetical or by category. The emotional hook is "what's about to go bad."
7. **Toast + undo on auto-add** — when the shopping-list hook adds items to the pantry, show a "Added 3 items to pantry" snackbar with Undo. Invisible magic becomes creepy magic fast.
8. **Never go negative** — decrement clamps at zero. A pantry entry at zero is auto-archived, not deleted, so history is preserved.

## Story Map

| # | Story | Theme | Priority | Est. Effort | Dependencies |
|---|-------|-------|----------|-------------|--------------|
| pantry-1 | Pantry CRUD API + `storage_location` column | Writable backend | 🔴 P0 | 1–1.5 d | None |
| pantry-2 | Shelf-life seed JSON + estimator service | Writable backend | 🔴 P0 | 0.5 d | None |
| pantry-3 | Shopping-list → pantry hook (with in-process dispatcher) | Event hooks | 🟡 P1 | 1 d | pantry-1, pantry-2 |
| pantry-4 | Meal-cooked → pantry decrement hook | Event hooks | 🟡 P1 | 1.5–2 d | pantry-1, pantry-3 |
| pantry-5 | Flutter pantry list screen | Manual UI | 🟡 P1 | 1.5–2 d | pantry-1 |
| pantry-6 | Flutter pantry item editor | Manual UI | 🟡 P1 | 1 d | pantry-1, pantry-2, pantry-5 |
| pantry-7 | "Use me up" CTA on expiring items | Manual UI | 🟢 P2 | 0.5 d | pantry-5 |

**Total estimated effort: 7–9 days**

## Sequencing

**Phase 1 — Backend foundation:** `pantry-1 ∥ pantry-2`. These are independent and can land in parallel. Nothing else in the epic can move without them.

**Phase 2 — First hook + dispatcher:** `pantry-3`. This story carries the cost of introducing the in-process event dispatcher (a small module, no external infra) since it's the first consumer. `pantry-4` gets the dispatcher for free.

**Phase 3 — Second hook (parallel with Flutter):** `pantry-4` can run in parallel with the Flutter work once `pantry-3` is merged.

**Phase 4 — Flutter surface:** `pantry-5 → pantry-6`. List screen first so routing, repository, and state shape are set; editor reuses those.

**Phase 5 — Polish:** `pantry-7`. Small feature that hooks into the existing recipe agent.

### Cross-phase priority

If forced to sequence strictly serially: **pantry-1 → pantry-2 → pantry-5 → pantry-6 → pantry-3 → pantry-4 → pantry-7**.

Rationale: landing the CRUD API and manual UI first means the pantry is *usable* end-to-end by Leo as early as possible, even without the hooks. The hooks are value-multipliers, not prerequisites for dogfooding. `pantry-7` ships last because it depends on the list screen existing.

## Explicit Cuts (Not In Scope)

These were discussed in Party Mode and deliberately excluded from this epic:

- **AI-inferred shelf-life per ingredient.** Would require OpenAI calls on ingredient-creation hot path and a caching story. Static JSON ships and is good enough for MVP.
- **Multi-user pantry sharing UX.** Schema supports it (`pantry_users` with roles) but UI treats each user's default pantry as single-user for this epic.
- **Storage location auto-detection.** User picks `fridge | pantry | freezer` manually or accepts the default from the seed data. No heuristics.
- **Barcode scanning or receipt image imports.** Pure manual entry plus the two hooks.
- **User-facing "unit mismatch, please confirm" prompts.** Leo has explicitly accepted the risk of silent-skip on decrement (best-effort). Can be added later if under-decrement becomes a real problem in practice.
- **Storage-location-change re-estimates.** Moving an item from pantry → fridge does not recompute `expires_at` automatically. User edits the date manually if they care.
- **Expiry push notifications.** The existing `GetPantryTool` already flags `expiring_soon` for the AI agent. Standalone expiry notifications are a future epic.
- **Pantry-level operations UI** (creating/renaming/archiving whole pantries, invitations). Only ingredient-level CRUD is in scope. Every user has one pantry for MVP.
- **Historical "what did I throw away" tracking.** Archived pantry entries are kept for history (never-negative rule) but there is no UI to review them.

## Definition of Done (Epic Level)

- All 7 stories merged and deployed to Leo's dogfood build.
- Leo can see a non-empty pantry on the Flutter pantry screen after purchasing at least one shopping-list item.
- Marking a meal as `completed` visibly decrements matching pantry items (where units normalize cleanly).
- At least 3 different storage-location expiry estimates are seeded and reflected in the UI when a user adds an item manually.
- The shopping-list "you already have" dedup behavior (which already exists) continues to work unchanged — no regressions in `populate_from_calendar` or `generate_from_meal_event`.
- `TODO.md` line "Pantry management UI" is checked off; "Pantry: Out of scope for MVP" note is updated to reflect that MVP pantry *is* now in scope and shipped.
- Leo's subjective answer to "do I trust what this thing says is in my fridge" is yes.

## References

- Party Mode discussion covering scope selection (option 2 — full non-invasive loop), architectural decisions (domain events, best-effort decrement), and UX principles (urgency grouping, fuzzy display, toast+undo)
- Existing pantry models: `libraries/utils/utils/models/pantry.py`, `pantry_user.py`, `pantry_ingredient.py`
- Existing read tooling: `libraries/agent/agent/tools/pantry.py` (`GetPantryTool`)
- Existing shopping-list dedup: `services/api/src/api/v1/shopping_list/populate_from_calendar.py`, `services/api/src/api/v1/shopping_list/generate_from_meal_event.py`
- Shopping-list item update endpoint: `services/api/src/api/v1/shopping_list/update_item.py` (hook attach point for pantry-3)
- Meal event update endpoint: `services/api/src/api/v1/meal_event/update_meal_event.py` (hook attach point for pantry-4)
- Migration directory: `services/migrator/migrations/versions/` (pattern: `YYYYMMDDHHmmss_description.py`)
- Flutter router: `app/lib/core/router/app_router.dart`
- Flutter pattern reference: `app/lib/features/shopping_cart/` (StreamController-based state, not Bloc)
