---
hash: pcw000
type: plan
created: 2026-07-27T17:21:00-06:00
title: Pantry — cook with what you have (decrement hooks, cookable ranking, use-it-up nudge)
from: _bmad-output/planning-artifacts/epic-pantry-cook-with-what-you-have.md
status: ready
mode: YOLO
---

## Scope
Close Palateful's biggest differentiation moat by making the pantry visible, trustworthy, and connected. Pantry CRUD shipped in `epic-pantry`; this epic adds the write-side hooks — cook-completion decrements pantry quantities (with `cook_session_id` idempotency, a 5-second undo snackbar, and a `pantry_decrement_events` table), and shopping-checkout adds purchased items to the pantry (opt-in auto-add toggle, default OFF). On the read side, a new `GET /v1/recipes/cookable` endpoint ranks the user's recipes by pantry coverage (with expiry bonus and a denormalized ingredient count for perf), surfaced as a home-screen "What Can I Cook Tonight?" card, a recipe-detail coverage badge, and a use-it-up nudge for soon-to-expire items — plus a `GetCookableRecipesTool` for the AI agent/MCP server. Household sync flows over a `pantry_applied` WS frame lowered into MutationBus bulk events. No new AWS resources; unit normalization is reused from `epic-extractor-richer-ingredients`, not rebuilt.

## Pre-split stories (BMAD)
- pantry-cook-1a — Backend: pure `pantry_decrement` service + unit-normalization reuse + ingredient-matching CSV fixture suite (synonyms, plurals, false-positive blockers like "chicken broth" vs "chicken"); no endpoint (split from pantry-cook-1 per party-mode 2026-04-25)
- pantry-cook-1b — Backend: `POST /v1/pantry/apply-cook-completion` + `pantry_decrement_events` idempotency table (unique user_id+cook_session_id) + `undo-cook-completion` endpoint + `service="pantry"` audit rows
- pantry-cook-2 — Backend: `POST /v1/pantry/apply-shopping-checkout` + `auto_add_to_pantry_on_checkout` preference + `pantry_items.purchased_at` migration
- pantry-cook-3 — Backend: `GET /v1/recipes/cookable` ranking endpoint (coverage + expiry bonus, missing-ingredient diff) + `GetCookableRecipesTool` for AI agent/MCP
- pantry-cook-3-5 — Backend: WS `pantry_applied` broadcast + three Postgres indexes + `tools/perf-budgets.yaml` entries + denormalized `recipe_ingredient_count` column (added by party-mode; infra-flavored)
- pantry-cook-4 — Frontend: home cookable card + recipe-detail coverage badge/sheet, new pantry MutationEvent subtypes, `pumpWithMutation` regression tests, partner-device WS updates
- pantry-cook-5 — Frontend: post-cook decrement sheet (default Yes, undo snackbar), tap-to-mark-cooked from recipe detail + meal events, shopping checkout paths, use-it-up nudge, sparse-pantry (<3 items) CTA, pantry preferences screen, e2e sweep

## Dependencies / notes
- No hard dependencies beyond shipped pantry CRUD (`epic-pantry` Stories 1-3); unit normalization reused from `epic-extractor-richer-ingredients`.
- Soft sequencing: pairs with `epic-nutrition-auto-calc` for a "what should I cook tonight that's healthy?" positioning story; no code dependency either way (nutrition filter on cookable ranking explicitly deferred).
- Perf budgets are in-scope, not follow-up: cookable p95 ≤200ms at 500 recipes / 100 pantry items, apply-cook-completion p95 ≤150ms; capture `analyze_latency.py` baseline before merge.
- Trust risk is the headline: wrong decrements kill the moat — v1 matches on exact normalized `ingredient_id` only, backed by the CSV fixture suite, undo snackbar, and per-DeltaPlan audit rows.
- Locked cross-epic decisions to honor: pantry MutationBus event names, `cook_session_id` as the canonical cook-mode idempotency key, `service="pantry"` audit pattern, `pantry_applied` WS frame, perf-budget-in-same-epic convention.
- When /devx-plan picks this up it should emit dev specs from the pre-split stories rather than re-chunking from scratch.

## Status log
- 2026-07-27T17:21 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; no implementation commits on main as of import
