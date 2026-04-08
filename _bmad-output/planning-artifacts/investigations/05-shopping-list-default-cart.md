# Investigation: Shopping List Default Cart UX

## Executive Summary

Users with multiple shopping lists face friction every time they use "Add to Cart" from recipes or the calendar. The current implementation requires a list picker bottom sheet each time, which becomes repetitive and annoying for the 90%+ case where the user wants the same list. The core ask is a **"default shopping list"** concept -- similar to the existing `default_recipe_book_id` pattern on the User model -- so that "Add to Cart" flows directly to the user's preferred list, with an easy override for edge cases (travel, temporary lists, etc.).

This is a high-value, moderate-complexity improvement that directly addresses the UX design spec's principle: *"Smart defaults eliminate decisions"* and *"Maximum 2 taps to value."*

---

## Current State Analysis

### Data Model

Shopping lists are defined in `libraries/utils/utils/models/shopping_list.py`:

- **`ShoppingList`**: Has `id`, `name`, `status` (pending/in_progress/completed), `owner_id`, `is_shared`, `share_code`, `widget_color`, `sort_by`, plus relationships to items and members.
- **`ShoppingListItem`**: Items with name, quantity, unit, category, urgency fields, due dates, and collaboration metadata (added_by, assigned_to).
- **`ShoppingListUser`**: Join table for sharing lists between users (role: owner/editor/viewer).
- **`ShoppingListEvent`**: Activity log for real-time sync.

**There is no `default_shopping_list_id` on the User model.** The `User` model (`libraries/utils/utils/models/user.py`) has `default_recipe_book_id` as an existing pattern, but nothing equivalent for shopping lists.

### "Add to Cart" Flows (3 entry points)

**1. Recipe Detail Screen** (`app/lib/features/recipes/recipe_detail_screen.dart`, line 98-161)

The `_addIngredientsToCart()` method:
- Fetches all shopping lists via `service.getShoppingLists()`
- If 0 lists: shows snackbar "No shopping lists -- tap + to create one"
- If 1 list: auto-selects it (no picker)
- If 2+ lists: shows a `showModalBottomSheet` list picker -- user must tap to choose

**2. Calendar Screen - Single Event** (`app/lib/features/calendar/calendar_screen.dart`, line 112-180)

The `_addIngredientsFromEvent()` method: identical pattern -- fetches lists, shows picker if multiple.

**3. Calendar Screen - Weekly Generation** (`app/lib/features/calendar/calendar_screen.dart`, line 186-278)

The `_generateWeeklyShoppingList()` method: same pattern -- fetches all lists, picker if multiple.

### Cart Tab (List Management)

`app/lib/features/cart/cart_screen.dart` shows all shopping lists as cards in a vertical list. Users can:
- Create new lists (FAB button "New List")
- Join shared lists via share code
- Tap a list card to navigate to its detail screen

**There is no visual indicator of which list is "default" or "active."** All lists appear equal.

### Floating Cart Widget

`app/lib/features/shopping_cart/widgets/floating_cart_widget.dart` takes an optional `listId` parameter. This widget persists across screens and shows a single list's items. However, **there is no mechanism to determine which list this FAB shows** -- it requires the caller to pass in a specific list ID.

### API Endpoints

The shopping list router (`services/api/src/routers/v1/shopping_list_router.py`) has comprehensive CRUD operations but no concept of a default or active list:
- `GET /shopping-lists` -- lists all (owned + shared), ordered by `updated_at desc`
- `POST /shopping-lists` -- creates a new list
- `GET /shopping-lists/{id}` -- get single list with items
- `PUT /shopping-lists/{id}` -- update list
- `DELETE /shopping-lists/{id}` -- delete list

### Existing "Default" Pattern: Recipe Books

The `default_recipe_book_id` on the User model provides a direct precedent:
- Added via migration `20260119000001_add_default_recipe_book_id.py`
- Column: `UUID FK -> recipe_books.id, nullable, ON DELETE SET NULL`
- Used in `get_me.py` to return the default book ID
- Set during onboarding, changeable later

---

## User Scenarios

### Scenario 1: Household Partners (Primary Use Case)
Leo and his partner share a "Weekly Groceries" list. This is their everyday list. When either taps "Add to Cart" from a recipe, they want ingredients to go straight to "Weekly Groceries" without picking from a list every time.

### Scenario 2: Road Trip / Travel
Leo is going on a road trip. He creates a "Road Trip Snacks" list and sets it as his default. For the next few days, "Add to Cart" goes to this list. When he returns home, he switches his default back to "Weekly Groceries."

### Scenario 3: Special Occasion
Leo is hosting a dinner party. He creates a "Dinner Party - March 28" list. He may or may not want this as the default -- maybe he just wants to add items from specific recipes to this temporary list while keeping "Weekly Groceries" as default for everything else.

### Scenario 4: First-Time User (Single List)
A new user has exactly one shopping list. "Add to Cart" should auto-select it (this already works). Once they create a second list, they should be gently prompted to set a default.

### Scenario 5: Calendar Integration
When generating a weekly shopping list from the calendar, the default cart should be pre-selected. The user can override if they want ingredients from this week's meal plan to go to a different list.

---

## Research Findings: Competitor Patterns

### AnyList
- Has a concept of a "primary" list that opens first
- Other lists accessible via sidebar drawer
- Adding items always goes to whichever list is currently visible
- No explicit "default" setting -- most-recently-used is effectively the default

### OurGroceries
- Multiple lists shown as tabs or a list view
- No formal default, but the first list in the list is treated as primary
- Household members see the same list order
- Cross-list operations (moving items between lists) are supported

### Bring! (Popular EU grocery app)
- Lists are shown as cards with distinct colors
- Users can "pin" a list to make it the default
- Pinned list always appears first and is used for quick-add
- Each household member can have a different pinned list
- Recipe import always asks which list (even with a pin), but the pinned list is pre-selected

### Apple Reminders
- Lists have a "default list" setting in app preferences
- Siri and quick-add always use the default list
- Explicitly changing the default is in Settings, not on the list itself

### Google Keep / Todoist
- Default project/list concept for quick capture
- Override available at the moment of creation
- Default is a user-level setting, not a list-level property

### Common Patterns Observed

1. **Default is a user-level preference** (not a list-level flag) -- each user in a household can have a different default.
2. **Default is pre-selected, not forced** -- the best apps pre-fill the default but let you change it inline.
3. **Visual distinction** -- the default list has a pin, star, or color highlight.
4. **Recency heuristic as fallback** -- if no explicit default, "most recently used" or "most recently updated" wins.
5. **Easy switching** -- changing the default is 1-2 taps, not buried in settings.

---

## Proposed UX Flow

### Core Concept: "Active Cart"

Instead of a hidden settings toggle, introduce an **"Active Cart"** concept -- a prominent, user-visible default that is easy to set and switch.

### Setting the Active Cart

**Option A: Star/Pin on Cart Tab (Recommended)**
- On the Cart tab, each list card gets a small star/pin icon in the corner
- Tapping the star sets that list as the active cart (and unsets any previous)
- The active cart card is visually distinct (pinned to top, subtle highlight or accent border)
- First list created is auto-set as active cart

**Option B: Long-press to Set Default**
- Long-pressing a list card on the Cart tab shows "Set as Active Cart" option
- Less discoverable but cleaner UI

**Option C: In-list Header Action**
- Inside a shopping list detail screen, a button/toggle in the header: "Set as Active Cart"

**Recommendation:** Option A with Option C as a secondary access point. Both are needed -- one for browsing lists, one for when you're already inside a list.

### "Add to Cart" Flow (Revised)

**When user has an Active Cart set:**
1. User taps "Add to Cart" from recipe/calendar
2. Items are immediately added to the Active Cart (no picker)
3. Snackbar confirms: "Added N ingredients to [Active Cart Name]" with an **"Change"** action button
4. Tapping "Change" on the snackbar opens the list picker (allows one-time override without changing the default)

**When user has NO Active Cart set (or Active Cart was deleted):**
1. Fallback to current behavior: show list picker if multiple lists
2. After selecting, snackbar includes a **"Set as default?"** prompt

**When user has exactly 1 list:**
1. Auto-select (current behavior, no change needed)
2. That list is implicitly the active cart

### Switching the Active Cart

Three ways to switch:
1. **Cart tab**: Tap the star/pin on a different list
2. **Inside a list**: Tap "Set as Active Cart" in the list header/menu
3. **Snackbar override**: After an "Add to Cart" action, tap "Change" on the confirmation snackbar, then optionally "Set as default?" for the newly chosen list

### Cart Tab Visual Treatment

```
[Cart Tab]

  [pin icon] Weekly Groceries         [shared icon]
  Active Cart - 5 items remaining     [>]
  ─────────────────────────────────────

  Road Trip Snacks
  3 items remaining                   [>]

  Dinner Party - March 28
  Empty                               [>]

                              [+ New List]
```

The active cart gets:
- A pin/star icon on the left (instead of the generic shopping cart icon)
- "Active Cart" subtitle label
- Pinned to the top of the list regardless of sort order
- Optional: slightly different card background tint

### Floating Cart Widget

The floating cart widget (already accepts a `listId`) should auto-bind to the active cart. When the user's active cart changes, the floating widget switches too.

---

## API / Data Model Changes Needed

### 1. New Column on `users` Table

```sql
ALTER TABLE users ADD COLUMN default_shopping_list_id UUID
  REFERENCES shopping_lists(id) ON DELETE SET NULL;
CREATE INDEX ix_users_default_shopping_list_id
  ON users(default_shopping_list_id);
```

This exactly mirrors the `default_recipe_book_id` pattern.

### 2. Migration File

New migration: `20260323000001_add_default_shopping_list_id.py`
- Add `default_shopping_list_id` column (nullable UUID FK)
- Add index

### 3. User Model Update

In `libraries/utils/utils/models/user.py`:
```python
default_shopping_list_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("shopping_lists.id", ondelete="SET NULL"),
    nullable=True,
)
default_shopping_list: Mapped["ShoppingList | None"] = relationship(
    foreign_keys=[default_shopping_list_id],
)
```

### 4. API Changes

**`GET /v1/me` (get_me.py):** Include `default_shopping_list_id` in the response.

**New endpoint: `PUT /v1/me/default-shopping-list`:**
```json
Request: { "shopping_list_id": "uuid" | null }
Response: { "default_shopping_list_id": "uuid" | null }
```
- Validates user owns or is a member of the list
- Sets `user.default_shopping_list_id`
- Returns updated value

**`GET /v1/shopping-lists`:** Include `is_default: bool` in each list item (computed: `sl.id == user.default_shopping_list_id`).

### 5. Flutter Changes

**User model / auth state:** Store `defaultShoppingListId` from the `getMe` response.

**ShoppingCartService:** Add `setDefaultShoppingList(String? listId)` method.

**Cart tab (`cart_screen.dart`):**
- Sort active cart to top
- Add star/pin icon with tap handler
- Visual distinction for active cart card

**"Add to Cart" flows (recipe_detail_screen.dart, calendar_screen.dart):**
- Check for `defaultShoppingListId` first
- If set and list exists: use it directly, show snackbar with "Change" action
- If not set: fallback to current picker behavior
- After picker selection, offer "Set as default?" in snackbar

**Floating cart widget:** Bind to `defaultShoppingListId` when no explicit `listId` is passed.

---

## Recommendations

### Priority Ordering

1. **Phase 1 (Core):** Add `default_shopping_list_id` to User model, migration, API response. Update "Add to Cart" flows to use the default. Add "Set as Active Cart" to Cart tab. -- This solves the core pain point.

2. **Phase 2 (Polish):** Snackbar with "Change" action for one-time override. "Set as default?" prompt after override selection. Visual card treatment on Cart tab.

3. **Phase 3 (Advanced):** Floating cart widget auto-binding. Auto-set default when user creates their first shopping list. Clear default when list is deleted or user is removed from shared list (handled by `ON DELETE SET NULL` at DB level).

### Design Decisions

- **User-level, not household-level.** Each user in a shared household has their own active cart preference. Partners may have different defaults (one defaults to "Weekly Groceries", the other to "Party Planning").

- **Explicit > implicit.** Use an explicit pin/star rather than inferring from most-recently-used. The "most recently used" heuristic is unreliable -- if someone browses a list to check an item, that shouldn't change their default.

- **Non-destructive override.** The snackbar "Change" action lets users override without changing their default. Only an explicit "Set as default" action changes the persistent preference.

- **Graceful degradation.** If the default list is deleted or membership is revoked, `ON DELETE SET NULL` clears it automatically, and the app falls back to the picker behavior.

- **Auto-set on first list.** When a user creates their first-ever shopping list (and has no default set), automatically set it as the default. This avoids the "cold start" problem.

---

## Technical Considerations

### Consistency with Recipe Book Default Pattern

The `default_recipe_book_id` migration and model changes provide an exact template. Follow the same approach:
- Same column naming convention (`default_shopping_list_id`)
- Same FK constraint pattern (`ON DELETE SET NULL`)
- Same index strategy

### Cache Invalidation

The `defaultShoppingListId` should be part of the auth/user state in the Flutter app. When it changes (via API call), the local state must update. Consider storing this in SharedPreferences as well for offline access.

### Access Control

When setting the default, the API must verify the user either owns the list or is an active (non-archived) member. If a user's membership is revoked from a shared list that was their default, the `ON DELETE SET NULL` on the FK handles the DB side, but the app should also handle the null gracefully on next load.

### WebSocket / Real-Time

No real-time concerns for the default preference itself -- it's a user-level setting, not a collaborative field. However, if the floating cart widget auto-binds to the default list, it needs to handle the case where the default changes mid-session (reconnect WebSocket to new list).

### Migration Safety

The migration is additive (new nullable column + FK + index). No data backfill required. Fully backwards-compatible -- existing behavior works when `default_shopping_list_id` is NULL.

---

## Estimated Complexity

| Component | Effort | Notes |
|-----------|--------|-------|
| DB migration | S | Single column + FK + index, mirrors existing pattern |
| User model update | S | 2 lines in `user.py` |
| API: include in `get_me` response | S | Add field to response schema |
| API: `PUT /me/default-shopping-list` | S | Simple endpoint, access control check |
| API: `is_default` in list response | S | Computed field in `list_shopping_lists.py` |
| Flutter: store `defaultShoppingListId` | S | Add to auth/user state |
| Flutter: update "Add to Cart" flows | M | 3 entry points need updating (recipe detail, calendar x2) |
| Flutter: Cart tab active cart UI | M | Sort, pin icon, visual distinction, tap handler |
| Flutter: snackbar with "Change" action | M | Custom snackbar action, one-time override logic |
| Flutter: floating cart auto-binding | S | Pass default ID when no explicit ID |
| Backend tests | S | 3-5 new tests for set/get/clear default |
| Flutter tests | M | Update existing "add to cart" tests, new cart tab tests |
| **Total** | **M** | **Estimated: 1-2 sprint stories (one backend, one frontend)** |

**Overall: Medium complexity.** The backend changes are small and well-patterned. The bulk of the work is on the Flutter side -- updating three "Add to Cart" flows, redesigning the Cart tab cards, and building the snackbar override UX. No architectural changes required.

---

## Key File References

### Flutter App
- `app/lib/features/cart/cart_screen.dart` -- Cart tab (list management)
- `app/lib/features/shopping_cart/services/shopping_cart_service.dart` -- Shopping cart service
- `app/lib/features/shopping_cart/models/shopping_list.dart` -- Shopping list model
- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` -- Single list detail
- `app/lib/features/shopping_cart/widgets/floating_cart_widget.dart` -- Floating cart FAB
- `app/lib/features/recipes/recipe_detail_screen.dart` -- "Add to Cart" from recipe (line 98)
- `app/lib/features/calendar/calendar_screen.dart` -- "Add to Cart" from calendar (lines 112, 186)
- `app/lib/core/router/app_router.dart` -- Navigation structure

### API
- `services/api/src/routers/v1/shopping_list_router.py` -- All shopping list routes
- `services/api/src/api/v1/shopping_list/list_shopping_lists.py` -- List endpoint (add `is_default`)
- `services/api/src/api/v1/user/get_me.py` -- User profile (add `default_shopping_list_id`)
- `services/api/src/schemas/shopping_list.py` -- Response schemas

### Data Model
- `libraries/utils/utils/models/user.py` -- User model (add `default_shopping_list_id`)
- `libraries/utils/utils/models/shopping_list.py` -- ShoppingList model
- `libraries/utils/utils/models/shopping_list_user.py` -- Membership join table

### Migrations
- `services/migrator/migrations/versions/20260119000001_add_default_recipe_book_id.py` -- Template to follow
- `services/migrator/migrations/versions/20260129000001_add_calendar_meal_planning_models.py` -- Original shopping_lists table
- `services/migrator/migrations/versions/20260130000001_add_shared_shopping_cart.py` -- Sharing system addition

### Design Docs
- `_bmad-output/implementation-artifacts/8-2-add-recipe-ingredients-to-shopping-list.md` -- Current "Add to Cart" story
- `_bmad-output/planning-artifacts/ux-design-specification.md` -- UX principles (lines 151, 1081)
