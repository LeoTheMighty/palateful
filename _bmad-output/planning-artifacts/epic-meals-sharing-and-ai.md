<!-- refined via party-mode 2026-04-18 -->
# Epic: Meals — Sharing & AI Tools (public links, MCP, AI-assembled meals)

## Overview

The last of the four Meals epics. Two user-visible outcomes:

1. **Public Meal share link.** A user taps Share on a Meal detail screen (the 6th and final action-bar slot foundation drew), the server generates-or-returns a `share_token`, the user gets a `palateful://meal-public/{token}` deep link plus an `https://palateful.app/meal-public/{token}` universal URL, and anyone with the link sees a read-only public Meal page — name, description, collage hero, component recipe tiles. Tiles open the component's own public recipe page **iff that component has its own `share_token`**; otherwise the tile shows a "Sign in to view" affordance.
2. **AI-assembled Meals via MCP.** The AI assistant gets tools to create, read, list, update, add/remove components, reorder, archive Meals, AND the existing `create_meal_event` tool is extended to accept `meal_id` (XOR with `recipe_id`, per calendar-epic locked context). "Make me a meal from my lemon dressing and a kale salad" becomes one conversational turn: `list_meals` → `create_meal` → response with a deep link. The conversational composition is the value — a user who would have manually long-pressed two tiles and hit Create Meal can now do it by voice/text.

**Goal (Day-1 user value).** When this epic ships, Leo can:

- Open Kale Salad Meal, tap Share, pick "Copy Link" from the share sheet, paste `https://palateful.app/meal-public/ab12cd34` into iMessage, and a non-user friend sees the Meal with both components plus linked tiles to any publicly-shared component recipe.
- In AI chat, say "make me a meal with my lemon dressing and the kale salad" — the AI fires `create_meal` with two component IDs and replies with a tap-to-open deep link. "Rename it to Summer Lunch" triggers `update_meal`. "Add my pita chips" triggers `add_recipe_to_meal`.
- See the Share action on the Meal detail action bar go **live** — foundation drew the slot, calendar wired 4 more, this epic wires the 6th.

**Privacy rule — LOAD-BEARING from discoverability workshop.** Public recipe pages HIDE the "Used in these Meals" section (discoverability epic Principle 8). The inverse is equally load-bearing here: **public Meal pages must NOT leak private structure about component recipes beyond `{name, thumbnail, has_public_token}`**. If a component's recipe does not have its own `share_token`, the tile renders disabled with a lock icon and "Sign in to view" CTA. No recipe UUID is exposed on the public payload for a private component — a stranger must not be able to probe a recipe's existence by guessing. For publicly-shared components, the tile links directly to the existing `palateful://recipe-public/{token}` deep link that recipe sharing already ships.

**Scope boundary.** `meals.share_token` column exists from foundation (mcv-1) — **no migration in this epic**. No new AWS resources, no new env vars. No changes to the existing recipe public-link flow, chat UI, chat history, MCP auth model, or any existing MCP tool other than `create_meal_event` (gains `meal_id`). No changes to the calendar tile rendering, the cooking-log fan-out pattern, or the shopping-list aggregation path — this epic only adds share + MCP surfaces.

## End-User Flow

### Sharing flow

1. Leo opens Kale Salad Meal → taps the **Share** action (action-bar slot 6, previously disabled-with-tooltip "Available when sharing ships" from foundation; this epic removes the tooltip and wires it live).
2. Flutter fires `POST /v1/meal/{meal_id}/share` (route lives on `meal_router` to mirror `recipe_router`'s `/v1/recipe/{id}/share` pattern). Server behavior:
   - If the Meal already has a `share_token`, return it as-is (idempotent). No rotation. No 201-vs-200 distinction — always `200 OK` with the existing token, or `201 Created` the first time. Frontend does not branch on status.
   - Otherwise generate via `secrets.token_urlsafe(15)` — **reuse the exact same helper** used by `ShareRecipe` (services/api/src/api/v1/recipe/share_recipe.py line 39). Persist, return.
   - Response shape matches `ShareRecipe`: `{token, deep_link: "palateful://meal-public/{token}"}`.
3. On the client, the `share_plus` package opens the native share sheet (iOS: UIActivityViewController — "Messages / Mail / Copy / More"; Android: Android intent chooser — "Messages / Gmail / Copy / More"). The `SharePlus().share()` call accepts a text payload like `"Check out this meal on Palateful: https://palateful.app/meal-public/ab12cd34"` plus a subject line for share targets that honor subjects (Mail).
4. If the user picks **Copy Link**, `https://palateful.app/meal-public/ab12cd34` lands on clipboard. Universal-link URLs let non-installed recipients see the web fallback (out of scope for this epic — the universal link just falls back to a static placeholder the Palateful marketing page serves today).
5. Friend taps the link. App-installed: opens directly to `PublicMealScreen`. Non-installed: browser fallback to the same screen served via the web app's SSR pipeline (existing flow for `/recipe-public/{token}` — mirror it).
6. `PublicMealScreen` renders: collage hero (reuses foundation's `ComponentCollageHero`), Meal name, description, "N recipes" decorative badge via foundation's `kMealComponentCountLabel(int n)` helper, and a vertical list of component tiles:
   - **Component has `has_public_token=true`**: tile is tappable; tapping calls `getPublicRecipeByToken(token)` and navigates to the existing `PublicRecipeScreen` with the component's token.
   - **Component has `has_public_token=false`**: tile renders disabled (onSurfaceVariant color, `Icons.lock_outline` trailing icon) with a muted subtitle "Sign in to view." Tapping surfaces a snackbar: "This recipe isn't public. Sign in to Palateful to view." (No login routing from the public screen in v1 — the snackbar is the terminal state.)

### AI flow

1. Leo in chat: "Make me a meal with my lemon dressing and the kale salad."
2. AI calls `list_meals({q: "lemon dressing"})` or `list_recipes` (existing tool) to disambiguate names → recipe IDs. If multiple plausible matches, AI asks a clarifying question **before** any write call ("I see 'Lemon Tahini Dressing' and 'Lemon Vinaigrette' — which?"). Locked pattern from discoverability: no silent fuzzy picks on creates.
3. AI calls `create_meal({recipe_book_id, name: "Lemon Dressing + Kale Salad", component_recipe_ids: [dressing_id, salad_id]})`. Server does the foundation validation (≥2 components, unique, readable by user). Returns `{id, name, components, ...}`.
4. AI replies: "Done — I made 'Lemon Dressing + Kale Salad' with your two recipes. Tap to open: palateful://meals/{id}."
5. Leo follow-ups: "Rename to Summer Lunch" → `update_meal({meal_id, name: "Summer Lunch"})`. "Add my pita chips" → `list_recipes({q: "pita chips"})` → `add_recipe_to_meal({meal_id, recipe_id})`. "Schedule it for Monday dinner" → `create_meal_event({meal_id, scheduled_at, meal_type})` — the calendar epic's extended signature does the work.

### What does not change

Recipe public-link flow (exists). `palateful://recipe-public/{token}` routing (exists). Chat UI, chat history, MCP auth model (exist). Existing MCP tools `create_meal_event` (this epic extends only — signature gains one optional arg, does not remove or rename anything), `list_meals` (discoverability landed it), `get_meal`, recipe tools. Foundation's action-bar slot contract — positions, icons, tooltips — no slot renames, no reordering. Only the 6th slot (Share) goes from disabled-with-tooltip to live.

## Frontend Changes

Touches `app/lib/features/meals/` and `app/lib/core/router/app_router.dart`. Touches `app/lib/core/services/api_client.dart` for the two new API calls.

### Share action wiring — `meal_detail_screen.dart` (MODIFY)

- Remove the disabled-with-tooltip state from the Share slot (foundation made it a placeholder). The slot becomes a live `IconButton` with the same `Icons.ios_share` (or platform-appropriate — match what recipe detail uses).
- Action handler:
  ```dart
  Future<void> _onShare() async {
    final result = await getIt<MealService>().share(meal.id);
    final shareUrl = 'https://palateful.app/meal-public/${result.token}';
    await SharePlus.instance.share(
      ShareParams(
        text: 'Check out this meal on Palateful: $shareUrl',
        subject: meal.name,  // honored by email share targets
      ),
    );
  }
  ```
- Error handling: on `POST /share` failure, snackbar "Couldn't generate share link. Try again." — no retry logic in v1 (share is a one-tap flow; user re-taps).
- Loading: the button shows a tiny inline `CircularProgressIndicator` replacing the icon while the POST is in flight. Prevents double-tap.

### `public_meal_screen.dart` (NEW)

Mirrors `public_recipe_screen.dart` shape exactly — `StatefulWidget`, `_loadMeal()` in `initState`, `Scaffold` + `AppBar` + conditional body (loading / error / content). Concrete details:

- **Loading state**: `Center(child: CircularProgressIndicator())` — same as `PublicRecipeScreen`. No shimmer (keeping parity with the existing public recipe treatment — if we later upgrade that to shimmer, update both in the same change).
- **Error state (meal not found, archived, or revoked)**: `Icons.link_off_outlined` icon + text "This meal isn't available." (Terser than recipe's "Recipe not found or link has been revoked." because Meals can't be revoked in v1 — no revoke endpoint — so "isn't available" covers archive + invalid token without lying to the user about an action they can't currently take.)
- **Content**:
  - **SliverAppBar** with `ComponentCollageHero` at `height: 200` (matches recipe public-screen hero height).
  - **Attribution**: if the Meal's `recipe_book_name` is present, label "From: <BookName>" in `labelMedium` + `onSurfaceVariant` color (mirrors recipe screen line 127).
  - **Title**: Meal name in `headlineSmall`.
  - **Description**: optional, `bodyLarge` + `onSurfaceVariant`.
  - **Components header**: "N recipes" using `kMealComponentCountLabel(components.length)` (foundation helper, already imported by MealTile, calendar tile, day sheet, recurring plans — this screen must too).
  - **Component tiles**: vertical list (`Column` or `ListView.builder` inside the sliver). Each tile:
    - Leading: 48×48 thumbnail (or `Icons.restaurant` outlined placeholder if no thumb) — no recipe UUID exposed in the DOM even for private components.
    - Title: component name.
    - Trailing: either `Icons.chevron_right` (public) or `Icons.lock_outline` (private).
    - On tap:
      - `has_public_token=true` → `context.push('/recipe-public/${component.public_token}')` (reuse the existing route).
      - `has_public_token=false` → `ScaffoldMessenger.showSnackBar(SnackBar(content: Text("This recipe isn't public. Sign in to Palateful to view.")))`.
  - **Footer attribution**: `"Shared via Palateful"` in `labelSmall` + `outline` color (mirrors recipe line 213).

**Widget shape table**:

| State | Root widget | Key child |
| --- | --- | --- |
| Loading | `Center` | `CircularProgressIndicator` |
| Archived / 404 | `Center > Padding > Column` | `Icons.link_off_outlined` + "This meal isn't available." |
| Loaded, 0 public components | `CustomScrollView` | Component list rendered entirely with lock icons |
| Loaded, mixed public/private | `CustomScrollView` | Component list with mixed chevron/lock |

### Deep linking — `app/lib/core/router/app_router.dart` (MODIFY)

- Add route `/meal-public/:token` → `PublicMealScreen(token: token)`. Parallels the existing `/recipe-public/:token` route.
- Unauthenticated: the route must be reachable from cold-launch without auth. Mirror whatever gate `recipe-public` uses today (the existing `go_router` redirect logic already exempts `/recipe-public/*` — extend the exempt list to include `/meal-public/*`).
- Universal-link (HTTPS) mapping: `https://palateful.app/meal-public/{token}` → same route. The `go_router` + Flutter's `PlatformDispatcher.instance.onPlatformBrightnessChanged` equivalent for universal-link handling already catches the HTTPS URL for recipes; adding a new path segment does not require new iOS associated-domains or Android AAL entries (both already wildcard-match `palateful.app` for any path).

### `SEO metadata / OpenGraph / Twitter Card` — YES (was open question, resolved)

Add `<meta>` tags on the web SSR path for `/meal-public/{token}` that mirror the recipe public-page pattern. Tags:

- `<meta property="og:title" content="{Meal name}">`
- `<meta property="og:description" content="{description || '{N} recipes on Palateful'}">`
- `<meta property="og:image" content="{first component's image_url or the 4-up collage rendered to a static JPEG}">`
- `<meta property="og:type" content="article">`
- `<meta property="og:url" content="https://palateful.app/meal-public/{token}">`
- `<meta name="twitter:card" content="summary_large_image">`
- `<meta name="twitter:title" content="{Meal name}">`
- `<meta name="twitter:description" content="{description || '{N} recipes on Palateful'}">`
- `<meta name="twitter:image" content="{same as og:image}">`

Implementation: the SSR renderer (already exists for `/recipe-public/*`) gains a meals branch. This is trivial — a template-string variant. A `twitter:image` for the collage may require a server-side Pillow 2×2 composite at render time; v1 acceptable fallback is the first component's `image_url` if that's cheaper to implement. Test: paste the URL into Slack's preview harness + iMessage to verify rich preview renders.

### `api_client.dart` (MODIFY)

Add two typed wrappers:

```dart
Future<ShareMealResult> shareMeal(String mealId);
Future<PublicMealDto> getPublicMealByToken(String token);
```

`ShareMealResult` mirrors the existing `ShareRecipeResult` shape (`{token, deep_link}`). `PublicMealDto`: `{id, name, description, recipe_book_name, components: [PublicMealComponentDto]}`. `PublicMealComponentDto`: `{name, image_url, has_public_token: bool, public_token: String?}` — **never `recipe_id`** for private components (server strips; see Backend § Public endpoint).

### Widget tests (non-negotiable)

- `public_meal_screen_test.dart`:
  - Loading → loaded: renders name + description + N-recipe badge + components list.
  - Archived meal / invalid token: renders `Icons.link_off_outlined` + "This meal isn't available."
  - Mixed components: 1 public → tile with chevron; 1 private → tile with lock icon.
  - Public-component tap: navigates to `/recipe-public/{token}`.
  - Private-component tap: shows snackbar "This recipe isn't public. Sign in to Palateful to view."
  - Collage hero: uses foundation's `ComponentCollageHero` (shared widget — smoke-test that it's mounted).
  - Badge text: asserts `kMealComponentCountLabel(n)` output appears — protects against string duplication.
- `meal_detail_share_test.dart`:
  - Share action is **live** (not disabled, no tooltip).
  - Tap fires `MealService.share(mealId)` then `SharePlus.instance.share(...)`.
  - Double-tap guard: second tap during in-flight POST is a no-op (loading spinner in place of icon).
  - POST failure: snackbar "Couldn't generate share link. Try again." Button returns to enabled state.
- `router_meal_public_test.dart`:
  - Cold-launch with `/meal-public/abc` does NOT redirect through auth gate.
  - `/meal-public/:token` route resolves to `PublicMealScreen` with the token.

## Backend Changes

### Model — no changes

- `meals.share_token` column exists from mcv-1 (nullable, partial unique when non-null). This epic is the first to read or write it. No migration.

### Schemas — `services/api/src/schemas/meal.py` (MODIFY)

Add `ShareMealResponse` (`{token, deep_link}`) — matches `ShareRecipe.Response` verbatim. Add `PublicMealResponse` and `PublicMealComponent`:

```python
class PublicMealComponent(BaseModel):
    name: str
    image_url: str | None
    has_public_token: bool
    public_token: str | None  # set iff has_public_token=True

class PublicMealResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    recipe_book_name: str
    components: list[PublicMealComponent]
```

**Privacy invariant on wire**: `PublicMealComponent` has **no `recipe_id`, no `order_index`, no `book_id`**. Only name, thumbnail, and — iff the component is itself publicly shared — its `public_token` so the client can deep-link. Enforced at schema construction in `GetPublicMeal` (see below); validated in `test_public_meal_privacy.py`.

### Handlers — `services/api/src/api/v1/meal/` (NEW files; directory name singular to match `recipe/`)

- **`share_meal.py`** (NEW) — `POST /v1/meal/{meal_id}/share`.

  ```python
  class ShareMeal(Endpoint):
      def execute(self, meal_id: str):
          user = self.user
          meal = self.database.find_by(Meal, id=meal_id)
          if not meal:
              raise APIException(status_code=404, detail="Meal not found", code=ErrorCode.MEAL_NOT_FOUND)
          membership = self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=meal.recipe_book_id)
          if not membership or membership.role not in ("owner", "editor"):
              raise APIException(status_code=403, detail="You don't have permission to share this meal", code=ErrorCode.FORBIDDEN)
          if meal.share_token is None:
              meal.share_token = secrets.token_urlsafe(15)  # EXACTLY matches ShareRecipe helper
              self.db.commit()
              self.db.refresh(meal)
              status = 201
          else:
              status = 200
          return success(
              data=ShareMeal.Response(
                  token=meal.share_token,
                  deep_link=f"palateful://meal-public/{meal.share_token}",
              ),
              status=status,
          )
  ```

  Idempotency: re-POSTing returns the same token with `200`. No token rotation in v1. No `DELETE /share` revoke endpoint in v1 (not in scope; recipe has one — we could add symmetrically, but defer). Auth: book write membership (owner/editor) — same as `ShareRecipe`.

- **`get_public_meal_by_token.py`** (NEW) — `GET /v1/meal/public/{token}`. Unauthenticated.

  Implementation notes:
  - Single SELECT: `Meal` where `share_token = :token AND archived_at IS NULL`, joined to `RecipeBook` for `recipe_book_name`, with `selectinload(Meal.components).selectinload(MealRecipe.recipe)`.
  - For each component, compute `has_public_token` as `recipe.share_token is not None AND recipe.archived_at is None`. Archived components are included in the response (locked-context says leak none: archived recipes should render greyed but since this is the public endpoint, we can pretend archived-recipe components don't exist — decision: **omit archived components entirely from the public response**. Matches "don't leak structure" and parallels public_recipe_screen's treatment of archived ingredients).
  - Privacy: response schema excludes `recipe.id` unconditionally. `public_token` is included iff `has_public_token=True`. Stranger cannot enumerate a private recipe's UUID.
  - 404: meal not found, or found but archived, or token doesn't match.

- **`revoke_meal_share.py`** — NOT in scope for this epic. Noted here so the follow-up epic doesn't retread. (Recipe has `revoke_recipe_share.py` for parity; add symmetrically in a later polish epic if a user ever complains.)

### Router — `services/api/src/routers/v1/meal_router.py` (MODIFY — from foundation)

- Add `POST /meal/{meal_id}/share` → `ShareMeal` (auth-gated via normal `Depends(get_current_user)`).
- Add `GET /meal/public/{token}` → `GetPublicMealByToken`. **No auth dependency.** Handler route must be registered BEFORE any `/meal/{meal_id}` path-param route (ordering matters in FastAPI — recipe_router line 165 comment already documents this pattern). Skim the existing router and insert the public route above the `/{meal_id}` lookup.
- Under `api_v1_router` prefix `/v1` the full public path resolves to `/v1/meal/public/{token}`. Frontend's universal-link handler maps `https://palateful.app/meal-public/{token}` → `GET /v1/meal/public/{token}`. Deep link `palateful://meal-public/{token}` is Flutter-side routing only.

### MCP Tools — `services/api/src/mcp_server/tools/meals.py` (NEW)

One module, pattern-matched on `recipes.py`. Seven tools — each wraps an existing Endpoint from the foundation epic (mcv-2 and mcv-3) and foundation's list-meals-autocomplete handler (mcal-5). No new business logic.

```python
@mcp.tool()
def create_meal(
    recipe_book_id: str,
    name: str,
    component_recipe_ids: list[str],
    description: str | None = None,
) -> str:
    """Create a new Meal — a named grouping of 2 or more recipes. Use when the user
    says things like "make me a meal from X and Y" or "bundle these recipes."
    Components must be recipes the user can read. Returns the created Meal's id
    and a deep link palateful://meals/{id}.
    """
    ...

@mcp.tool()
def get_meal(meal_id: str) -> str:
    """Get a Meal by id. Returns name, description, component recipes, etc."""
    ...

@mcp.tool()
def list_meals(q: str | None = None, limit: int = 20) -> str:
    """List / search Meals the user can read. Optional `q` filters by name or
    description (case-insensitive). Use to disambiguate before create_meal."""
    ...

@mcp.tool()
def update_meal(meal_id: str, name: str | None = None, description: str | None = None) -> str:
    """Update a Meal's name or description. Component changes use
    add_recipe_to_meal / remove_recipe_from_meal."""
    ...

@mcp.tool()
def add_recipe_to_meal(meal_id: str, recipe_id: str, order_index: int | None = None) -> str:
    """Add a recipe as a component of a Meal. Rejects duplicates."""
    ...

@mcp.tool()
def remove_recipe_from_meal(meal_id: str, recipe_id: str) -> str:
    """Remove a component. Rejects if it would leave fewer than 2 components.
    This is a destructive action. If the resulting Meal would have 1 component,
    the tool returns an error and asks the caller to confirm the intent —
    either add a replacement first, or archive the Meal instead."""
    ...

@mcp.tool()
def archive_meal(meal_id: str) -> str:
    """Archive a Meal. If the Meal has scheduled meal_events or recurrence rules
    that reference it, the tool returns a CONFIRMATION_REQUIRED error listing
    the upcoming events. The caller must re-invoke with `confirmed=True` to
    proceed, or reschedule/remove the references first."""
    ...
```

**AI confirmation policy** (was open question — resolved): MCP tools prompt for confirmation only in two cases. Everything else executes silently.

1. **`remove_recipe_from_meal` that would produce <2 components**: returns `{error: "CONFIRMATION_REQUIRED", reason: "This would leave the Meal with 1 component. Confirm, add a replacement, or archive instead."}` — the AI surfaces this as a chat message and waits for user input before retrying.
2. **`archive_meal` with live references**: query `meal_events.meal_id = :id AND archived_at IS NULL AND scheduled_at >= now()` OR `meal_recurrence_rules.meal_id = :id AND archived_at IS NULL`. If non-zero, return `{error: "CONFIRMATION_REQUIRED", reason: "This Meal has {N} upcoming events and {M} recurring rules.", events: [...], rules: [...]}`. The tool accepts a `confirmed: bool = False` optional parameter that bypasses the gate when `True` — the AI invokes it a second time once the user says "yes."

All other AI-initiated writes (create_meal, update_meal name/description, add_recipe_to_meal, non-degenerate remove, archive with zero references) proceed without prompting — the user explicitly requested them and the action is reversible (restore, or re-add). This matches the existing MCP write posture for recipes.

**Auth**: every tool dispatches through the existing `call_endpoint` helper which injects `get_current_user` + `get_current_database` from the MCP auth context. Book membership is enforced by the underlying Endpoints from foundation — MCP adds zero auth logic.

### Existing MCP tool — `create_meal_event` extension (msa-4 / calendar-epic-locked)

- `services/api/src/mcp_server/tools/meal_planning.py` (MODIFY) — add `meal_id: str | None = None` parameter to the existing `create_meal_event` signature. XOR with `recipe_id` is enforced by the underlying `CreateMealEvent` Endpoint (calendar epic mcal-3 already owns that validation + check constraint). Docstring updated: "Pair a `recipe_id` or `meal_id` (not both) when planning from an existing recipe or Meal."
- **This is a signature extension, not a rewrite.** The existing recipe-only path of this tool does not change behavior.

### MCP registry — `services/api/src/mcp_server/tools/__init__.py` (MODIFY)

Exactly **one line** to register the new module:

```python
from mcp_server.tools import (  # noqa: F401
    agent_tools,
    import_tools,
    meal_planning,
    meals,          # <- ADD
    recipe_books,
    recipes,
    search,
    shopping,
    user,
)
```

The `@mcp.tool()` decorators in `meals.py` fire on import. Idempotent via the `_REGISTERED` flag.

### Eval fixtures — `services/eval/fixtures/` (NEW) — **≥6 fixtures, load-bearing**

(Was open question — resolved: **minimum 6 fixtures**. Justification below.)

**Why 6 and not 3**: the AI is now doing **mutations the user didn't double-check**. Creates, updates, adds, removes, archives — any silent regression in tool-dispatch, parameter parsing, or auth-context propagation is a data-integrity bug on the user's real Meal library. The minimum eval matrix must cover one fixture per **tool path that mutates state** plus one fixture per **ambiguity path that must clarify instead of guess**. That's:

1. **`meal_create_from_explicit_ids.json`** — user says "make a meal from Lemon Dressing and Kale Salad" where both are unambiguous names. Expected: `list_meals` optional; `list_recipes` to resolve IDs (or direct `create_meal` if model shortcuts); exactly one `create_meal` call with 2 component_ids; response contains the deep link.
2. **`meal_create_from_fuzzy_names.json`** — user says "bundle the kale one with my lemon dressing" where "kale one" matches two recipes ("Kale Salad" + "Kale Chips"). Expected: AI asks a clarifying question BEFORE any `create_meal` call. Assertion: zero write calls in the trace until the user clarifies.
3. **`meal_create_with_clarification_needed.json`** — user says "combine my two favorite salads" and the AI has no signal about which two. Expected: AI lists candidates and asks. Same zero-write assertion as above.
4. **`meal_update_name.json`** — user has a Meal open in context ("Summer Lunch Meal"), says "rename to Picnic Box." Expected: one `update_meal(meal_id, name="Picnic Box")` call. No `create_meal` leakage. No `add_recipe_to_meal`.
5. **`meal_add_and_remove_component.json`** — user with existing 3-component Meal says "add my pita chips" then "drop the lemon dressing." Expected: `add_recipe_to_meal` then `remove_recipe_from_meal`. The remove call leaves 3 components (within ≥2 floor) → no confirmation required → silent execution. Second fixture variation: user with 2-component Meal says "remove the dressing" → tool returns `CONFIRMATION_REQUIRED`, AI surfaces as chat message, user's next turn is "no, archive instead" → tool calls `archive_meal`.
6. **`meal_archive_with_references.json`** — user has a Meal with an upcoming recurrence. Says "delete the Kale Salad Meal." AI calls `archive_meal`, receives `CONFIRMATION_REQUIRED` with the reference list, surfaces to user. User confirms ("yes, delete anyway") → AI calls `archive_meal(meal_id, confirmed=True)`. Assertion: no silent `archive_meal` without `confirmed=True` when references exist.
7. **`meal_event_with_meal_id.json`** — user says "schedule the Summer Lunch Meal for Monday dinner." Expected: `create_meal_event(meal_id=..., scheduled_at=..., meal_type="dinner")`. `recipe_id` stays null. Covers the calendar-epic signature extension from the AI side. **This is msa-4's eval.**

Optional 8th if capacity allows (stretch, not minimum): `meal_schedule_recurring_rule.json` — "every Monday dinner, Kale Salad Meal" → recurrence_rule create with `meal_id`. Relevant but already covered by calendar's own evals; low marginal value here.

Bar: **all 7 fixtures must pass** in CI before this epic can ship. One failure = regression.

### Tests — `services/api/tests/`

- **`test_share_meal.py`** (NEW):
  - Happy first share: 201, token + deep_link in response, `meals.share_token` populated, `palateful://meal-public/{token}` format.
  - Happy re-share (idempotent): second POST returns 200 + same token; `meals.share_token` unchanged in DB.
  - Token format: 20 characters, URL-safe alphabet (matches `secrets.token_urlsafe(15)` output length = ceil(15*4/3) = 20).
  - Auth-fail: viewer-only on book → 403.
  - 404: missing meal; archived meal also 404 (share is a write; archived meals are not shareable).
- **`test_get_public_meal.py`** (NEW):
  - Happy: valid token → 200 with `{id, name, description, recipe_book_name, components: [...]}`.
  - **Privacy invariant test** (`test_public_meal_privacy.py` or merged here): the JSON response for a Meal with a private component contains NO `recipe_id` key on that component entry. Assert via direct dict-key check (not just schema validation — raw JSON inspection).
  - Component with `has_public_token=true`: response includes its `public_token`.
  - Component with `has_public_token=false`: response omits `public_token` (field is `None`, excluded by schema).
  - Archived component: excluded from the response entirely.
  - Archived meal: 404.
  - Invalid token: 404.
  - Revoked in the future (if revoke endpoint lands): 404. (Out of scope for v1 tests; noted.)
- **`test_mcp_meals_tools.py`** (NEW):
  - One test per tool: happy path, auth-fail (user not on book), validation reject, parameter parsing (string → UUID conversions).
  - `remove_recipe_from_meal` degenerate-state guard: 2 components → request to remove → `CONFIRMATION_REQUIRED` returned; no DB mutation.
  - `archive_meal` with live references: `CONFIRMATION_REQUIRED` + event list; `confirmed=True` bypass commits the archive.
  - `create_meal_event` XOR: both `recipe_id` and `meal_id` set → 422 / validation error surfaced through MCP boundary.
- **Coverage**: 100% branch on every new handler + every new branch in the MCP module. Pinned by CI per CLAUDE.md. The ShareMeal idempotent branch (201 vs. 200) is the only genuinely-new branch; both paths MUST be covered.

## Infrastructure Changes

**None.**

- No migration. `meals.share_token` column exists from foundation (mcv-1), partial-unique index on `WHERE share_token IS NOT NULL` was created then, no changes.
- No new AWS resources, no new env vars, no Dockerfile changes.
- MCP tools deploy with the existing API container. `register_all_tools()` runs at API startup (existing pattern); importing `mcp_server.tools.meals` triggers the `@mcp.tool()` decorators without any other wiring.
- Standard deploy: `npx nx run api:docker-build`, standard ECS rolling task swap. No migrator run required.
- Eval fixtures live in `services/eval/fixtures/` (existing directory). The eval harness CI job gains 7 new fixtures; the existing harness runs them on each push to main. If the harness is not yet CI-enforced, add it as a required check for this epic only — the AI mutation posture means a silent-regression in tool dispatch is not acceptable.
- Universal-link web SSR path (`/meal-public/{token}`): added to the existing web SSR route table. No new Lambda, no new CloudFront behavior — path is already covered by the catch-all handler that serves recipe-public today.

## Design Principles (refined)

1. **Meal share_token parallels recipe share_token exactly.** Same generator (`secrets.token_urlsafe(15)` — the byte-for-byte helper), same idempotent-POST shape, same deep-link scheme (`palateful://meal-public/{token}`), same universal-link pattern (`https://palateful.app/meal-public/{token}`). Users who know recipe sharing already know Meal sharing.
2. **Public Meal page shows structure, never implementation.** Name, description, component names, thumbnails, `has_public_token` per component. No recipe UUIDs, no `order_index`, no book IDs, no internal metadata. Privacy invariant enforced at the schema layer AND asserted by `test_public_meal_privacy.py`.
3. **Components that aren't publicly shared render disabled with a lock icon + "Sign in to view" CTA.** Tapping surfaces a snackbar, not a login redirect — the public screen is a terminal surface for strangers.
4. **Archived components vanish from the public response** — they were available when the Meal was assembled but aren't anymore; we show the current public truth, not the historical one. Parallels `public_recipe_screen`'s treatment of archived ingredient lines.
5. **MCP tools mirror REST 1:1.** Seven tools, each wraps one foundation Endpoint. Thin tool layer keeps the registry maintainable and keeps eval-coverage arithmetic simple (one tool → one or two fixtures).
6. **AI doesn't invent names or pick silently on fuzzy matches.** `list_meals` / `list_recipes` first; clarify second; write third. Fixtures 2 and 3 codify this as a regression bar.
7. **AI confirmation fires only on degenerate transitions or live-reference archives.** Everything else executes. Re-prompting on every write turns the agent into a chat-only assistant; the product vision is an agent that DOES things.
8. **Eval minimum is 6 (actually 7 once we count `create_meal_event` with `meal_id`).** Writes-via-AI demand a fixture per mutation path + per ambiguity path. ≥3 was too thin for a mutation-capable surface.
9. **SEO metadata matches recipe public page.** OpenGraph + Twitter Card on the `/meal-public/{token}` SSR route. Shared links render rich previews in iMessage + Slack. Trivial to implement (SSR templates already parameterized for recipes); skipping would leak a polish gap into a ship-day user-facing regression.
10. **Share is the 6th and final action-bar slot.** Foundation drew 6 slots; calendar wired 4 more (Plan-for-Date, Add-to-Shopping-List) alongside the existing Favorite / Archive / Edit; Share is the last disabled-with-tooltip slot. This epic removes its tooltip and makes it live. **No slot renames, no reordering** — the contract is locked.
11. **Shared `kMealComponentCountLabel(int n)` helper is the single format-string source.** MealTile (foundation), calendar tile + day sheet + recurring plans (calendar epic), AND the public Meal page (this epic) all import the helper. Do NOT duplicate the string `"$n recipes"` in this epic — foundation exports it.
12. **No revoke endpoint in v1.** Recipe has one (for symmetry with `ShareRecipe`); Meal deferred to polish. Error-state copy on `PublicMealScreen` says "This meal isn't available" — covers archive + invalid-token + future-revoked without lying about an action that exists.
13. **No rate limit on share generation.** The endpoint is a write + commit at user scale; API Gateway per-user throttle is sufficient. Same posture as `ShareRecipe`.
14. **`create_meal_event` with `meal_id` is a signature extension only.** The calendar epic (mcal-3) owns the XOR validation at the API layer; the MCP tool just passes `meal_id` through. Zero business logic in the MCP module.
15. **Eval fixtures are CI-gated.** All 7 minimum fixtures must pass before this epic can ship. Silent regression in tool dispatch is a data-integrity bug on live Meals — eval is the only safety net.

## File Structure

```
app/lib/features/meals/
  meal_detail_screen.dart                [MODIFY]  Wire Share slot (remove tooltip, live POST + share sheet)
  public_meal_screen.dart                [NEW]     Unauthenticated read-only Meal view
  services/meal_service.dart             [MODIFY]  +share(mealId), +getPublicMealByToken(token)

app/lib/core/router/app_router.dart      [MODIFY]  +/meal-public/:token (unauthenticated)

app/lib/core/services/
  api_client.dart                        [MODIFY]  +shareMeal, +getPublicMealByToken typed wrappers

services/api/src/api/v1/meal/            [NEW dir, mirrors services/api/src/api/v1/recipe/]
  share_meal.py                          [NEW]     POST /v1/meal/{meal_id}/share — idempotent
  get_public_meal_by_token.py            [NEW]     GET /v1/meal/public/{token} — unauthenticated

services/api/src/schemas/
  meal.py                                [MODIFY]  +ShareMealResponse, +PublicMealResponse, +PublicMealComponent

services/api/src/routers/v1/
  meal_router.py                         [MODIFY]  +share + public routes (public registered BEFORE /{id} path-param route)

services/api/src/mcp_server/tools/
  meals.py                               [NEW]     7 MCP tools (create/get/list/update/add/remove/archive)
  meal_planning.py                       [MODIFY]  +meal_id arg on create_meal_event (XOR with recipe_id)

services/api/src/mcp_server/tools/
  __init__.py                            [MODIFY]  Register meals module in register_all_tools()

services/eval/fixtures/                  [NEW files — 7 fixtures minimum]
  meal_create_from_explicit_ids.json
  meal_create_from_fuzzy_names.json
  meal_create_with_clarification_needed.json
  meal_update_name.json
  meal_add_and_remove_component.json
  meal_archive_with_references.json
  meal_event_with_meal_id.json

services/api/tests/
  test_share_meal.py                     [NEW]
  test_get_public_meal.py                [NEW]     Includes privacy-invariant assertions
  test_mcp_meals_tools.py                [NEW]
```

## Stories

### Story msa-1 — Backend: share endpoint + public Meal endpoint + privacy schema

**Acceptance criteria:**

- `POST /v1/meal/{meal_id}/share` (new handler `services/api/src/api/v1/meal/share_meal.py`):
  - If `meal.share_token is None`: generate via `secrets.token_urlsafe(15)`, persist, return `{token, deep_link: "palateful://meal-public/{token}"}` with status **201**.
  - If `meal.share_token is not None`: return same body with status **200**. Idempotent — no rotation.
  - Auth: `Depends(get_current_user)`; role check: book owner or editor (not viewer). 403 otherwise.
  - 404 on missing or archived meal.
- `GET /v1/meal/public/{token}` (new handler `services/api/src/api/v1/meal/get_public_meal_by_token.py`):
  - No auth dependency. Route registered in `meal_router.py` BEFORE any `/meal/{meal_id}` path-param route (FastAPI ordering — see `recipe_router.py` line 165 for the existing pattern).
  - Returns `PublicMealResponse` — id, name, description, recipe_book_name, components.
  - Each `PublicMealComponent`: `{name, image_url, has_public_token, public_token}`. **No `recipe_id` field.** `public_token` set iff the component recipe has its own `share_token` AND is not archived.
  - Archived components: **omitted entirely** from the components list.
  - Archived meal or missing token: 404.
- `services/api/src/schemas/meal.py`: `ShareMealResponse`, `PublicMealResponse`, `PublicMealComponent` added. `PublicMealComponent` schema does NOT declare a `recipe_id` field — the privacy invariant is enforced at construction.
- **Test matrix** (`test_share_meal.py` + `test_get_public_meal.py`):
  - Share happy (first, 201) + idempotent re-share (second, 200, same token).
  - Share auth-fail (viewer → 403), 404 (missing / archived meal).
  - Public happy (200), valid token, all component types (all public, all private, mixed, one archived).
  - **Privacy invariant**: raw-JSON assertion that `recipe_id` does NOT appear anywhere in a `components[*]` entry.
  - Public 404 (missing token, archived meal).
- **100% branch coverage** on both handlers. CI gate per CLAUDE.md.

### Story msa-2 — Flutter: Meal detail Share action + PublicMealScreen + routing

**Acceptance criteria:**

- `meal_detail_screen.dart` Share slot (currently disabled-with-tooltip from foundation): tooltip removed, button becomes live `IconButton`. Tap handler calls `MealService.share(meal.id)` then `SharePlus.instance.share(...)` with text `"Check out this meal on Palateful: https://palateful.app/meal-public/{token}"` and subject `meal.name`.
- Loading state: inline `CircularProgressIndicator` replaces the share icon during in-flight POST; second tap during in-flight is a no-op.
- Error state: on POST failure, snackbar "Couldn't generate share link. Try again." Button returns to enabled state.
- `public_meal_screen.dart` (NEW):
  - Parallels `public_recipe_screen.dart` in widget shape. `StatefulWidget`, `_loadMeal()` in `initState`, `Scaffold` + `AppBar` + conditional body.
  - Content: `CustomScrollView` → collage hero (`ComponentCollageHero` from foundation) → "From: {book_name}" attribution → name (headlineSmall) → description (bodyLarge) → "N recipes" badge using `kMealComponentCountLabel` (foundation helper — imported, not duplicated) → vertical component list → "Shared via Palateful" footer.
  - Component tile with `has_public_token=true`: tappable, trailing `Icons.chevron_right`, tap navigates `context.push('/recipe-public/{component.public_token}')`.
  - Component tile with `has_public_token=false`: disabled appearance (onSurfaceVariant), trailing `Icons.lock_outline`, tap shows snackbar "This recipe isn't public. Sign in to Palateful to view."
  - Loading: `Center(child: CircularProgressIndicator())`.
  - Error (404 / archived): `Icons.link_off_outlined` + "This meal isn't available." — centered.
- `app_router.dart`: route `/meal-public/:token` → `PublicMealScreen(token)`. Unauthenticated — added to the existing auth-exempt path list alongside `/recipe-public/*`.
- Universal-link: `https://palateful.app/meal-public/{token}` maps to the same route via the existing go_router universal-link handler. No new iOS associated-domains or Android AAL entries needed.
- `api_client.dart` wrappers added: `shareMeal(mealId)` → `ShareMealResult`, `getPublicMealByToken(token)` → `PublicMealDto`.
- **Widget tests** (`public_meal_screen_test.dart`, `meal_detail_share_test.dart`, `router_meal_public_test.dart`):
  - Public screen: loading, loaded (mixed components), archived/404 state, public-tap navigation, private-tap snackbar, badge text comes from `kMealComponentCountLabel`.
  - Meal detail: Share is live (not disabled/no tooltip); tap triggers API call + `SharePlus.instance.share`; double-tap guard; POST failure state.
  - Router: `/meal-public/{token}` cold-launch without auth; universal-link pattern.

### Story msa-3 — Backend: MCP tools for Meals (7 tools) + AI confirmation policy

**Acceptance criteria:**

- `services/api/src/mcp_server/tools/meals.py` (NEW) exports 7 `@mcp.tool()` functions: `create_meal`, `get_meal`, `list_meals`, `update_meal`, `add_recipe_to_meal`, `remove_recipe_from_meal`, `archive_meal`. Each wraps the foundation Endpoint via `call_endpoint`; no business logic outside of parameter shaping.
- `services/api/src/mcp_server/tools/__init__.py` `register_all_tools()` imports the new module (one-line addition to the import tuple). `_REGISTERED` flag keeps registration idempotent.
- AI confirmation policy enforced in the tool wrappers:
  - `remove_recipe_from_meal`: if the target Meal has exactly 2 components, return `{"success": false, "error": "CONFIRMATION_REQUIRED", "reason": "This would leave the Meal with 1 component. Confirm, add a replacement, or archive instead."}` without executing the removal. When >2 components, execute silently.
  - `archive_meal(confirmed: bool = False)`: if `confirmed=False` and the Meal has upcoming `meal_events` (`archived_at IS NULL AND scheduled_at >= now()`) OR active `meal_recurrence_rules` (`archived_at IS NULL`), return `{"success": false, "error": "CONFIRMATION_REQUIRED", "reason": "...", "events": [...], "rules": [...]}`. If `confirmed=True` OR zero references, execute silently.
  - All other tools: execute silently. No prompts on create, update-name, non-degenerate remove, add, or ambiguous-name (AI handles ambiguity before the tool call).
- Auth: all tools dispatch through `call_endpoint` with the MCP auth context. Book-membership checks are enforced by the underlying foundation Endpoints.
- **Tests** (`test_mcp_meals_tools.py`):
  - One per tool: happy, auth-fail, validation-reject, parameter-parsing (string → UUID).
  - `remove_recipe_from_meal` degenerate-state guard: at 2 components → `CONFIRMATION_REQUIRED`; no DB mutation; at 3 components → silent success.
  - `archive_meal` live-reference guard: with events → `CONFIRMATION_REQUIRED`; with `confirmed=True` → archive committed; with zero references → silent success.
- **100% branch coverage** on all tool dispatchers and confirmation-policy branches.

### Story msa-4 — Backend: create_meal_event MCP tool accepts meal_id + eval fixtures

**Acceptance criteria:**

- `services/api/src/mcp_server/tools/meal_planning.py` `create_meal_event` tool signature gains optional `meal_id: str | None = None` parameter. Docstring updated: "Pair a `recipe_id` or `meal_id` (not both) when planning from an existing recipe or Meal."
- XOR enforcement is delegated to the underlying `CreateMealEvent` Endpoint (calendar epic mcal-3 owns the Pydantic `model_validator` + DB check constraint `ck_meal_events_recipe_xor_meal`). MCP tool just passes through.
- Existing recipe-only path: behavior and response are byte-identical to pre-epic. Regression fixture asserts this.
- **Eval fixtures** — 7 minimum in `services/eval/fixtures/`, all CI-gated:
  1. `meal_create_from_explicit_ids.json` — unambiguous names → single `create_meal` call with 2 component IDs.
  2. `meal_create_from_fuzzy_names.json` — ambiguous "kale one" → AI clarifies BEFORE writing (zero-write assertion).
  3. `meal_create_with_clarification_needed.json` — no signal → AI lists candidates and asks (zero-write assertion).
  4. `meal_update_name.json` — rename only → one `update_meal` call.
  5. `meal_add_and_remove_component.json` — add then remove (non-degenerate) → two sequential tool calls, both silent. Variation: 2-component Meal + remove → `CONFIRMATION_REQUIRED`; user says "archive instead" → `archive_meal`.
  6. `meal_archive_with_references.json` — AI hits `CONFIRMATION_REQUIRED`, surfaces reference list, user confirms → `archive_meal(confirmed=True)`.
  7. `meal_event_with_meal_id.json` — "schedule the Summer Lunch Meal for Monday dinner" → `create_meal_event(meal_id=..., scheduled_at=..., meal_type="dinner")` with `recipe_id=null`.
- All 7 fixtures pass in the eval CI job. A single failure blocks ship.
- **Regression**: existing `create_meal_event` tests (calendar epic) pass unchanged. The XOR-reject path (422 `MEAL_EVENT_RECIPE_XOR_MEAL`) is tested here via the MCP boundary too — a tool call with both `recipe_id` and `meal_id` set surfaces the 422 as an MCP error.
- **100% branch coverage** on the extended dispatch logic in `meal_planning.py`.

## Dependencies

- **Blocks**: nothing. This is the last of the four Meals epics.
- **Depends on**:
  - `epic-meals-create-and-view` (foundation) — requires `meals` table, `meals.share_token` column, `MealTile`, `kMealComponentCountLabel`, `ComponentCollageHero`, `meal_router`, foundation CRUD Endpoints (mcv-2, mcv-3).
  - `epic-meals-discoverability` (landed) — soft dependency. Not strictly required; no endpoint conflict. But `list_meals` MCP tool benefits from the search-extensions already landed there (the tool can surface Meals the user would find in the UI).
  - `epic-meals-calendar` (landed) — hard dependency for msa-4 specifically. `create_meal_event` `meal_id` XOR requires the calendar epic's migration + Pydantic `model_validator` + `CreateMealEvent` handler extension. If calendar hasn't landed when this epic starts, msa-4 defers to a follow-up and msa-1/msa-2/msa-3 ship without it.
- **Parallelizable with**: nothing remaining. After this epic ships the Meals feature is end-to-end complete.

## Open Questions

**All three open questions are resolved:**

- **Public Meal page SEO metadata** → **YES**. OpenGraph + Twitter Card tags on the `/meal-public/{token}` SSR route, mirroring the recipe public-page pattern. Template-string parameterized from the existing recipe-public SSR renderer; `og:image` uses the first component's `image_url` as the v1 fallback, with a follow-up to render the 4-up collage to a static JPEG if preview quality suffers.
- **AI confirmation policy for destructive actions** → **Prompt only on degenerate-state transitions and live-reference archives.** `remove_recipe_from_meal` when <2 components would result; `archive_meal` when `meal_events` (upcoming) or `meal_recurrence_rules` (active) reference the Meal. Everything else (create, update, non-degenerate remove, add, archive-with-zero-references) executes silently. The `confirmed: bool` parameter on `archive_meal` is the bypass.
- **Eval fixture count** → **Minimum 7** (6 Meal-mutation-path fixtures + 1 `create_meal_event` with `meal_id` fixture). Each covers a distinct mutation path or ambiguity path. All CI-gated; one failure blocks ship. Justification: AI is doing mutations the user didn't double-check, so eval is the only safety net against silent tool-dispatch regressions.

**Nothing to escalate to the user.** All decisions are locked context or are trivially-specified follow-ons (SSR template extension, MCP registry one-liner, Pydantic schema additions). This is the last Meals epic — when it ships the 4-epic chain is complete.

**End-to-end feature completeness check (for the record):**

- **Foundation (mcv)**: Meal entity, book-scoped CRUD, multi-select → Create Meal flow, Meal detail with 6-slot action bar (Favorite live, 3 disabled-with-tooltip, Archive + Edit live), MealTile, `meal_favorites` table, `share_token` column reserved.
- **Discoverability (md)**: Meals on home grid, search (by name + by component name), "Used in these Meals" on recipe detail, favorites carousel, archive view.
- **Calendar (mcal)**: `meal_events.meal_id` + `meal_recurrence_rules.meal_id` XOR, plan-meal sheet Recipe/Meal toggle, calendar tile rendering, Open-Recipe chooser, `PopulateFromCalendar` with sum-within-meal dedupe, cooking-log fan-out, **Plan-for-Date + Add-to-Shopping-List slots go live** (4/6 live after calendar), `create_meal_event` signature extended to accept `meal_id`.
- **Sharing & AI (msa, this epic)**: Share endpoint, public Meal page, **Share slot goes live** (6/6 live after this epic), 7 MCP tools with confirmation policy, `create_meal_event` MCP tool extended, 7 eval fixtures.

**No silent gaps.** Every surface a user touches (home, search, recipe detail, Meal detail, calendar, shopping list, chat, share sheet, public page) has a Meal story that ships and is tested. Every action-bar slot on Meal detail is live by the end of the chain. Every MCP tool that could plausibly be invoked on a Meal exists. The privacy rule (public pages don't leak private structure, either direction) is enforced in schemas and tests on both discoverability (hiding "Used in these Meals" on public recipe pages) and sharing (stripping `recipe_id` from `PublicMealComponent`).
