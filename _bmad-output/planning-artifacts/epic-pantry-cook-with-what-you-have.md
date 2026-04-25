<!-- refined via party-mode 2026-04-25 -->
# Epic: Pantry — Cook With What You Have

## Overview

Close out Palateful's biggest differentiation moat. Pantry CRUD + read shipped (`epic-pantry`, partial). Missing: write-side hooks (shopping → pantry, meal-cooked → pantry decrement) and the "What can I cook tonight?" recipe ranking. With these, Palateful becomes the only app that ties "what you have" to "what you can cook" to "what you need to buy" — and Apple+Gemini Siri's late-2026 system-level pantry intelligence becomes a prompt-injection tailwind, not a threat.

## Goal

Make pantry visible, trustworthy, and connected. After this epic ships, a household can: (a) cook a recipe and trust the pantry self-updates, (b) check off shopping items and trust the pantry self-updates, (c) open the home screen and see ranked recipes they can cook *right now*, (d) get nudged when ingredients are about to expire. No more "is the pantry actually up to date?" friction.

## End-user flow

1. **Cooking a recipe — pantry decrement.** User cooks a recipe via cook mode. On the post-cook flow (after the existing "rate how it went" sheet), a new step asks: "Update pantry — used 200g chicken, 1 onion, 3 cloves garlic? [Yes] [Skip]" defaulted to Yes. Tapping Yes decrements those pantry items by recipe quantity (or marks them used up if depleted). Skip just continues — no pantry change.
2. **Shopping checkout — pantry add.** User checks off items at the store. If the user has the "Auto-add to pantry on shopping checkout" Settings toggle ON (default OFF for v1), each checked item auto-adds to pantry with `purchased_at = now`. With the toggle OFF, a long-press on a checked item shows an optional "Add to pantry" action.
3. **Home screen — "What Can I Cook Tonight?" card.** When the household pantry is non-empty, the home screen shows a new card above the recent-recipes section: "What Can I Cook Tonight?" with a horizontally-scrolling row of recipe tiles ranked by pantry coverage. Each tile shows the recipe + a coverage badge: "You have all 8 ingredients" (green) or "You're missing 2: heavy cream, basil" (yellow) with a "[Add missing to shopping list]" tap target.
4. **Recipe detail — pantry-coverage badge.** Every recipe detail screen displays a small badge near the title: "You have 6 of 8 ingredients" or "You have all 8 ingredients" (green checkmark). Tapping the badge expands a sheet listing ingredients colored by pantry-availability, with a one-tap "Add missing 2 to shopping list" action.
5. **Use-it-up nudge.** When any pantry item is within 3 days of its expiry date, the home screen surfaces a nudge above the cookable-recipes card: "Your chicken thighs expire Friday — here are 3 quick recipes that use them." Tap → filtered cookable-recipes view biased toward recipes using that ingredient.
6. **AI agent — `GetCookableRecipesTool`.** The existing AI agent + MCP server exposes a new tool: given pantry state, return ranked cookable recipes with missing-ingredient diff. Lets a Claude desktop user ask "what can I make tonight with what I have?" and get a real answer rooted in the user's actual pantry.

## Frontend changes

- New widget `app/lib/features/home/cookable_recipes_card.dart` — horizontal scroll of recipe tiles ranked by pantry coverage. Each tile = thumbnail + title + coverage badge + missing-ingredient mini-list + "Add to shopping list" tap target. Provider: new `cookableRecipesProvider` calling `GET /v1/recipes/cookable`.
- `app/lib/features/recipes/recipe_detail/recipe_detail_screen.dart` — add `PantryCoverageBadge` widget near the title. Tap expands a sheet with ingredients colored by availability + one-tap "Add missing to shopping list."
- `app/lib/features/cook_mode/post_cook_flow.dart` (or wherever the post-cook sheet lives) — add a new "Update pantry?" step after the existing rating step. Default action: Yes. Backend call: `POST /v1/pantry/apply-cook-completion`.
- `app/lib/features/shopping/shopping_list_screen.dart` — long-press on a checked item shows an optional "Add to pantry" action (when auto-add is OFF). When auto-add is ON, every check-off triggers `POST /v1/pantry/apply-shopping-checkout` silently.
- `app/lib/features/profile/notification_preferences_screen.dart` (or Settings → Pantry) — new toggle "Auto-add to pantry on shopping checkout" (default OFF). New toggle "Show 'What Can I Cook?' card" (default ON for households with non-empty pantries).
- New widget `app/lib/features/home/use_it_up_nudge.dart` — banner above the cookable card when any pantry item is within 3 days of expiry. Provider listens to pantry-state changes; nudge is dismissible (per-item, 24h dismiss cooldown).

## Backend changes

- New service `services/api/src/services/pantry_decrement.py` — given a recipe + serving count, compute per-pantry-item deltas with unit normalization (kg ↔ g ↔ oz ↔ lb; ml ↔ l ↔ tbsp ↔ tsp ↔ cup; reuse existing unit-aliases logic from `epic-extractor-richer-ingredients`). Returns a `DeltaPlan` for the caller to apply (or display for confirmation).
- New endpoint `POST /v1/pantry/apply-cook-completion` — body: `{recipe_id, serving_count}`. Uses `pantry_decrement` to compute + apply deltas. Returns the new pantry state for items that changed. Idempotent: same `recipe_id + serving_count` from the same cook-mode session within 5 minutes is a no-op.
- New endpoint `POST /v1/pantry/apply-shopping-checkout` — body: `{shopping_list_item_ids: [...]}`. For each item, look up the matching pantry item by ingredient_id; create or upsert with `purchased_at = now`, `quantity = item.quantity`. Returns affected pantry items.
- New endpoint `GET /v1/recipes/cookable?limit=20` — returns user's recipes ranked by pantry coverage descending. Response shape per item: `{recipe_id, recipe_title, recipe_thumbnail, total_ingredients, matched_ingredients, missing_ingredients: [{ingredient_id, name, quantity, unit}], coverage_score}`. Coverage score = matched / total, with bonus weight for recipes using soon-to-expire pantry items.
- New `GetCookableRecipesTool` in `libraries/agent/agent/tools/` — exposes `get_cookable_recipes(limit=10)` to the AI agent + MCP server. Returns the same response shape as `GET /v1/recipes/cookable`.
- **Schema additions** (Alembic migration):
  - `pantry_items.last_used_at: Mapped[Optional[datetime]]` — set by `apply-cook-completion`. Used for "use me up" sorting.
  - `pantry_items.purchased_at: Mapped[Optional[datetime]]` — set by `apply-shopping-checkout`. Used for "use me up" sorting + UX age display.
- **User preference** (extend `users.notification_preferences` JSON or `users.pantry_preferences` JSON): `auto_add_to_pantry_on_checkout: bool` (default false), `show_cookable_card: bool` (default true), `pantry_decrement_default: 'yes' | 'skip'` (default 'yes').

## Infrastructure changes

None. Existing pantry tables (`pantry_items`, `pantry_users`), existing endpoint patterns, no new env vars, no new AWS resources, no new pip deps.

## Initial design principles (from research; party-mode TBD)

- **Default to Yes on the post-cook pantry decrement.** The friction of remembering to confirm is what kills pantry trust. Default-Yes biases toward freshness; the Skip button is one tap if the user knows the recipe didn't use the listed amounts.
- **Auto-add on shopping checkout starts OFF.** Friction-free for users who don't care; opt-in for the power users who want full automation. Don't surprise people.
- **Coverage badge is hopeful, not punitive.** "You have 6 of 8 ingredients" + green-for-have / yellow-for-missing — frames the gap as a small step, not a wall.
- **Use-it-up nudge is opt-out, not opt-in.** Pantry waste is the explicit problem we solve. The nudge fires by default; users can dismiss per-item with a 24h cooldown if they're sick of it.
- **Unit normalization is borrowed, not new.** Reuse `epic-extractor-richer-ingredients` aliases — don't build a parallel unit-conversion table.
- **Cookable ranking weights expiry.** Recipes using ingredients within 3 days of expiry get a bonus in the score — naturally surfaces "make this before it goes bad" recipes.

## File structure (anticipated)

```
app/lib/features/
  home/
    cookable_recipes_card.dart                  # NEW
    use_it_up_nudge.dart                        # NEW
    home_screen.dart                            # mount the new card + nudge
  recipes/recipe_detail/
    recipe_detail_screen.dart                   # add PantryCoverageBadge
    pantry_coverage_badge.dart                  # NEW widget
    pantry_coverage_sheet.dart                  # NEW expanded view
  cook_mode/
    post_cook_flow.dart                         # add "Update pantry?" step
  shopping/
    shopping_list_screen.dart                   # long-press add-to-pantry
  profile/
    pantry_preferences_screen.dart              # NEW toggles

services/api/src/
  services/pantry_decrement.py                  # NEW
  api/v1/pantry/
    apply_cook_completion.py                    # NEW endpoint
    apply_shopping_checkout.py                  # NEW endpoint
  api/v1/recipe/
    list_cookable_recipes.py                    # NEW endpoint

libraries/agent/agent/tools/
  get_cookable_recipes_tool.py                  # NEW

services/migrator/migrations/versions/
  20260427010000_pantry_items_last_used_purchased_at.py  # NEW migration

_bmad-output/implementation-artifacts/
  pantry-cook-1-backend-pantry-decrement-and-cook-completion.md
  pantry-cook-2-backend-shopping-checkout-and-preference-toggle.md
  pantry-cook-3-backend-cookable-recipes-endpoint-and-mcp-tool.md
  pantry-cook-4-frontend-cookable-card-and-coverage-badge.md
  pantry-cook-5-frontend-post-cook-shopping-and-nudge-and-e2e.md
```

## Story list

- **pantry-cook-1 — Backend: pantry_decrement + apply-cook-completion endpoint.** New `services/api/src/services/pantry_decrement.py` computing deltas with unit normalization. New `POST /v1/pantry/apply-cook-completion` endpoint. Schema migration adding `pantry_items.last_used_at`. Idempotency: same recipe_id + serving_count within 5 minutes = no-op. **AC:** decrementing a recipe with 3 ingredients applies the right deltas; over-quantity-used decrements to 0 and marks used_up; idempotency works; integration test covers a full cook-completion flow; 100% coverage.
- **pantry-cook-2 — Backend: apply-shopping-checkout + preference toggle.** New `POST /v1/pantry/apply-shopping-checkout` endpoint. Extend user preferences with `auto_add_to_pantry_on_checkout` flag. Schema migration adding `pantry_items.purchased_at`. **AC:** checking off a shopping item with the flag ON adds to pantry; with the flag OFF, no change; preference flag is persisted; integration test covers both branches.
- **pantry-cook-3 — Backend: GET /v1/recipes/cookable + GetCookableRecipesTool.** New `GET /v1/recipes/cookable` endpoint with ranking algorithm + ingredient-diff response shape. Coverage score = matched / total + expiry bonus. New `GetCookableRecipesTool` in `libraries/agent/agent/tools/` exposing the same data to the AI + MCP server. **AC:** endpoint returns ranked recipes; missing-ingredient list is correct; expiry-bonus weighting works; AI tool callable from Claude desktop via MCP.
- **pantry-cook-4 — Frontend: home cookable card + recipe-detail coverage badge.** New `cookable_recipes_card.dart` mounted on home screen above recents. New `PantryCoverageBadge` + expanded sheet on recipe detail. `cookableRecipesProvider` calling the new endpoint. **AC:** card renders for households with non-empty pantries; coverage badge accurate; tapping badge expands sheet with one-tap "add missing to shopping list"; widget tests cover empty + full + partial-coverage states.
- **pantry-cook-5 — Frontend: post-cook + shopping checkout + use-it-up nudge + e2e sweep.** Post-cook pantry-update confirmation sheet defaulting to Yes. Shopping-list checkout long-press + auto-add path. `use_it_up_nudge.dart` mounted above cookable card when applicable. Settings → Pantry preferences screen. End-to-end test: cook a recipe → confirm pantry decrement → see updated coverage on next view of the recipe → check off a shopping item with auto-add ON → see new pantry item → see use-it-up nudge fire when that item approaches expiry. **AC:** all flows work in widget + e2e tests; no regressions on existing post-cook flow; nudge dismiss persists 24h.

## Dependencies

- **No hard dependencies** beyond pantry CRUD already shipped (`epic-pantry` Stories 1-3).
- **Soft:** unit-normalization logic from `epic-extractor-richer-ingredients` (reused, not duplicated).
- **Should ship before:** `epic-nutrition-auto-calc` doesn't depend on this directly, but cookable-recipes ranking + nutrition cards together create the "what should I cook tonight that's healthy?" story — sequencing both lets us bundle a positioning blog post.

## Open questions for the user

- **Default for `auto_add_to_pantry_on_checkout` — OFF or ON?** Default proposed is OFF (least surprising). If you want ON by default for the kitchen-power-user positioning, we flip and show an opt-out toast on first checkout.
- **Use-it-up nudge frequency — daily fire or once per item per 3 days?** Default proposed: once per item per 24h dismiss cooldown. If users find it nagging, we can move to weekly summary.
- **"What Can I Cook?" card placement on home.** Proposed: above the recents section, below any meal-of-the-day card. Pushes other content down — confirm or pick a different slot.

---

## Refinements applied (party-mode 2026-04-25)

### End-user-flow additions / rewrites
- **Add step 0.5 (between current 1 and 2):** "Mark recipe cooked from outside cook mode — same decrement sheet fires from recipe-detail tap-to-mark-cooked and from meal-event completion." Same idempotency model.
- **Append to step 1:** "Decrement sheet shows a **5-second undo snackbar** on confirm; one tap restores the prior pantry state." (Critical for trust.)
- **Append to step 3:** "When a household member cooks, the other member's open home screen updates the cookable card live via WS-lowered MutationBus event (no pull-to-refresh)."
- **Rewrite step 5 conditional:** Use-it-up nudge fires ONLY when the soon-to-expire item has at least one matching cookable recipe in the user's library; otherwise suppressed (no deadend).
- **Add step 7:** "Empty / sparse pantry behavior — cookable card hidden when pantry has <3 items; replaced by 'Add a few pantry items to see what you can cook' CTA with deeplink to pantry add."

### Frontend section additions
- **New `MutationEvent` subtypes:** `PantryItemAdded`, `PantryItemDecremented`, `PantryItemUsedUp`, `PantryItemDismissed`, plus bulk `PantryBulkApplied(sessionId, deltas)`. (One bulk event per cook completion, not N per ingredient.)
- All pantry mutations emit from a new `PantryService` class on the success branch.
- `cookableRecipesProvider` and `pantryCoverageProvider(recipeId)` both `ref.listen(mutationBusProvider)` and `invalidateSelf()` on any pantry event type.
- **WS-lowering** — backend broadcasts `pantry_applied` WS frame after `apply-cook-completion` and `apply-shopping-checkout` succeed; existing WS adapter lowers it into `PantryBulkApplied` so partner devices re-render.
- Failure-copy entries added to `mutationFailureCopy` map for each new event type.
- Each frontend story includes one `pumpWithMutation` regression test for its surface.
- **Undo snackbar** on post-cook decrement — 5-second window calls a new `POST /v1/pantry/undo-cook-completion` with the session_id.

### Backend section additions
- **Replace 5-minute idempotency window with `cook_session_id` UUID** generated client-side when cook mode opens. New `pantry_decrement_events` table with unique `(user_id, cook_session_id)` constraint; insert-on-conflict-do-nothing semantics. Re-cook = new session = new decrement; double-tap = same session = no-op.
- **New `POST /v1/pantry/undo-cook-completion`** — accepts `cook_session_id`, reverses deltas from `pantry_decrement_events`. 5-min window enforced server-side.
- **Every applied DeltaPlan writes to `error_logs`** with `service="pantry"`, `error_type="DeltaApplied"`, payload = JSON of delta plan + recipe_id + session_id (audit, not error). Mirrors `service="audit"` pattern from ops scripts.
- **Cookable-recipes ranking:** precompute denormalized `recipe_ingredient_count` column (filled by Alembic backfill in same migration) — coverage = matched / cached_count. Avoids count-aggregation per request on 500+ recipes.
- **WS broadcast** of `pantry_applied` frame to all household members after each successful apply.
- 100% coverage explicitly stated per story AC.

### Infrastructure section additions
- **Alembic migration adds three indexes** alongside the new columns:
  - `pantry_items(user_id, expires_at) WHERE expires_at IS NOT NULL` — for use-it-up nudge.
  - `pantry_items(household_id, ingredient_id)` — for cookable JOIN.
  - `recipe_ingredients(ingredient_id)` if missing — for use-it-up reverse lookup.
- **New table `pantry_decrement_events(id, user_id, cook_session_id, recipe_id, applied_at, delta_plan_json, reversed_at)`** with unique `(user_id, cook_session_id)`.
- **`tools/perf-budgets.yaml` entries:** `GET /v1/recipes/cookable` p95 ≤ 200ms at 500 recipes / 100 pantry items; `POST /v1/pantry/apply-cook-completion` p95 ≤ 150ms.

### Story changes
- **Split `pantry-cook-1` into `1a` + `1b`:**
  - `1a` — pure `pantry_decrement` service + unit normalization reuse + **ingredient-matching CSV fixture suite** at `services/api/tests/fixtures/ingredient_matching_cases.csv` (synonyms, plurals, brand prefixes, unit-only differences, zero-quantity, false-positive blockers like "chicken broth" vs "chicken"). No endpoint.
  - `1b` — `apply-cook-completion` endpoint + `pantry_decrement_events` idempotency table + `undo-cook-completion` endpoint + `service="pantry"` audit log.
- **Add `pantry-cook-3.5 — Backend: WS broadcast + perf budgets + indexes.`** Self-contained infra-flavored story: `pantry_applied` WS frame, three Postgres indexes, `tools/perf-budgets.yaml` entries, denormalized `recipe_ingredient_count` column.
- **`pantry-cook-4` AC expansion:** new MutationEvent subtypes wired, `pumpWithMutation` regression tests for cookable card + coverage badge, partner-device update via WS-lowered event.
- **`pantry-cook-5` extension:** undo snackbar on decrement sheet, tap-to-mark-cooked from recipe detail + meal-event completion, empty-pantry CTA, sparse-pantry threshold (<3 items hides card).

### Open questions (escalated)
1. Sparse-pantry threshold — hide cookable card below N items? **Recommend N=3.**
2. Undo window for cook decrement — 5-second snackbar only, or longer "recent cooks" history screen? **Recommend 5-second snackbar v1; history screen is a v2 story if requested.**
3. WS broadcast scope — every pantry mutation, or only cook + shopping batch events (skip per-item manual edits)? **Recommend bulk events only** (bandwidth + render cost discipline).
4. Ingredient-matching ambiguity — "chicken" pantry could match "chicken broth" or "chicken thighs"? **Recommend (a) exact normalized name only for v1**, evolve to (b) confirmation prompt post-launch.
5. Cookable card placement on home — above recents, above use-it-up nudge, or top-of-home? **Recommend above recents, below any meal-of-the-day card.**

### Locked decisions to propagate (2 remaining epics)
1. **MutationBus naming for pantry:** `PantryItemAdded` / `Decremented` / `UsedUp` / `Dismissed` + bulk `PantryBulkApplied(sessionId, deltas)`. Future pantry-touching epics MUST emit/subscribe via these — no parallel hierarchy.
2. **`cook_session_id` is the canonical idempotency key** for any cook-mode-derived mutation. Future epics hanging work off cook completion (post-cook nutrition snapshot, post-cook social share) reuse the same session_id.
3. **`service="pantry"` audit pattern** in `error_logs` — every applied DeltaPlan writes a row. Future pantry mutations follow `service="pantry"`, `error_type="<verb>Applied"`, payload JSON.
4. **WS frame `pantry_applied`** is the canonical household-sync frame for pantry mutations. Don't invent a new frame.
5. **Perf budget pattern** — every new list endpoint at risk of N+1 ranking gets a `tools/perf-budgets.yaml` entry in the same epic that introduces it; not a follow-up.

### Risks
1. **Pantry trust collapse from wrong decrements.** Unit-mismatch corrupts pantry → users stop using cook mode → moat dies. *Mitigation:* CSV-parametrized ingredient-matching fixture suite, conservative match (exact normalized-name only v1), 5-second undo snackbar, per-DeltaPlan audit row for fast triage.
2. **Ingredient-matching false positives** ("chicken broth" matches "chicken"). *Mitigation:* match on `ingredient_id` only after extractor canonicalizes — never raw text.
3. **Cookable-ranking p95 regression at 500+ recipes / 100+ pantry items.** *Mitigation:* Postgres indexes in same migration, cached `recipe_ingredient_count`, perf-budget entry enforced in CI, `analyze_latency.py` baseline captured before merge.
