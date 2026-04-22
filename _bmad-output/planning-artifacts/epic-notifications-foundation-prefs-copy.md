<!-- refined via party-mode 2026-04-21 -->
# Epic: Notifications Foundation — Per-Category Prefs, Copy Library, Deep-Links

## Overview

Test push works end-to-end on Leo's iPhone (`epic-notifications-ios-proofoflife` + `epic-notifications-push-diagnostics-hardening` + commits `4827d96`/`7fe41d9`). The plumbing is solid; the *callsite layer* is uneven. This epic is the cross-cutting plumbing every other notification epic builds on.

Three problems to solve:

1. **Notification preferences are too coarse.** `notification_preferences_screen.dart` exposes 3 toggles (push_enabled, partner_activity, auto_approve_imports) plus quiet hours. The user wants per-category control: Meals, Timers, Shopping, Partner activity, Imports, Friends/invitations. Without this, downstream epics ship category-specific notifications with no in-app opt-out.
2. **Copy is generic and contextless.** `notify_import_needs_review` only knows the count, not the recipe name — so we can never say "Your Sweet Potato Quiche needs a review" without a refactor that loads the first awaiting-review item. `RECIPE_ADDED` has an arity bug (`recipe_router.py:91` calls a helper with mismatched params) so it crashes silently. There's no central "notification copy library" — each callsite invents its own strings.
3. **Deep-links are coarse for meals.** `_routeForNotification` in `push_notification_service.dart:582-585` lands every meal notification on `/calendar` root. The user has to scroll-find the relevant event. Need a `/calendar/meals/:id` route + a lightweight detail screen.

**Goal:** establish the foundation so later epics ship rich, on-brand, opt-out-able notifications with single-line callsite changes.

## Locked Decisions (inherited + added)

**Inherited from `epic-notifications-ios-proofoflife` and `epic-notifications-push-diagnostics-hardening` (do not re-litigate):**
- iOS-first scope; Android continues on `firebase_messaging` defaults.
- No feature flags, no backwards-compat shims, inline fixes.
- Two-row audit pattern for admin actions (`service="audit"` + `service="push_notifications"` on failure).
- `FIREBASE_CREDENTIALS_JSON` / `FIREBASE_CREDENTIALS_PATH` — both supported.
- Errors route through `ErrorReporter` with `area: "push"` tags. No user-facing toasts for delivery failures.
- Boot-time auto-prompt gated on `has_completed_onboarding == true`.

**Locked for this epic (from 2026-04-21 user batch + sensible defaults):**
- **Per-category prefs are the new default.** 6 toggles: `meals`, `timers`, `shopping`, `partner_activity`, `imports`, `friends_invitations`. Each defaults to `true` for new users. The existing `partner_activity` field is preserved (renamed semantics: now means specifically the partner-activity category in the new shape). `auto_approve_imports` stays — it's a behavior, not a notification opt-out, and stays separately available.
- **Backwards-compat shape:** old clients sending the legacy 3-toggle shape continue to work — backend defaults missing per-category fields to `true` (don't silently opt people out by sending an old payload).
- **Copy library lives in `libraries/utils/utils/services/notification_copy.py`.** A single module with one function per (notification_type, variant) pair returning `(title, body)`. Every callsite pulls from here; no inline strings.
- **`notify_import_needs_review` loads the first awaiting-review item to extract the recipe name** for single-recipe variants. Bulk variants use the count only.
- **Cover image attachment** for single-recipe imports uses the extractor's `parsed_recipe.image_url` if present at notification time. Source-photo promotion happens after approval — too late for the awaiting-review push.
- **`RECIPE_ADDED` arity bug fixed inline.** Confirmed by audit (services/api/src/routers/v1/recipe_router.py:91 calls `notify_recipe_added(...)` with mismatched param name). Fix at the callsite.
- **Meal detail deep-link route is `/calendar/meals/:id`.** New screen renders meal title, recipe (if any), participants, scheduled_at, and the "Remind me at" override (which Epic B wires). Screen is a sibling of the existing calendar list.

## Refinements via party-mode 2026-04-21

**Lens-by-lens cross-examination findings — incorporated into ACs below:**

- **PM:** Per-category granularity (6 toggles) hits the right value tier. No re-litigation. Don't expand to per-event sub-toggles in this epic — the user explicitly chose category-level. ✅
- **UX:** "Auto-approve high-confidence imports" row needs visual separation from the new per-category section (it's a behavior toggle, not a notification opt-out). Folded into nfn-4 AC.
- **Frontend:** Master switch + categories pattern requires clear visual hierarchy: master at top → categories block → quiet hours → other. Disabled state for category switches when master is off. Folded into nfn-4 AC 6.
- **Backend:** The order of suppression checks in `send_to_user` MUST be: (1) master `push_enabled`, (2) per-category, (3) quiet hours, (4) `force` override. Document this with an inline comment. Diagnostic types (`TEST`) bypass 1-3, respect 4. Folded into nfn-1 risks.
- **Backend:** `_category_for_type` exhaustiveness assertion is the load-bearing contract for future epics (B/C/D/E add new types). Failing to extend the mapping = CI break. Locked.
- **Infra/Devops:** No new infra. JSONB shape change is additive; no migration. Add a one-paragraph note to `docs/PUSH_NOTIFICATIONS.md` documenting the per-category schema for future debugging.
- **QA:** Test legacy `partner_activity` flat-field fallback explicitly (Test C in nfn-1). Add a test for the legacy 3-toggle shape arriving from an old client → backend defaults missing categories to `true`, doesn't silently opt the user out.

**Cross-epic locked decisions added by this workshop (propagate to B/C/D/E):**

1. **Suppression order is master → category → quiet hours → force.** Every epic that adds a new `NotificationType` must respect this contract by routing through `send_to_user` (don't bypass at callsite).
2. **`_category_for_type` exhaustiveness check stays in CI forever.** Every new enum value needs a category mapping or CI breaks.
3. **Notification copy is centralized in `notification_copy.py`.** No inline title/body strings in callsites for any new notification type. (B/C/D/E already follow this in their drafts.)
4. **`/calendar/meals/:id` deep-link is the canonical meal target.** Any future meal-related notification routes here.
5. **Image attachment uses the existing FCM `notification.image` field (already wired with `PalatefulNotificationService` extension).** Pass `image_url` to the `PushNotification` constructor; the iOS extension downloads + attaches automatically. (B/C/D/E inherit this — no per-epic image plumbing.)
6. **Per-recipient suppression is a `send_to_user` concern.** Callsites that loop over multiple recipients (e.g., shared book members) call `send_to_user` per user; each gets independent prefs/quiet-hours treatment.

## End-user flow

### Flow A — Existing user discovers granular preferences

1. User opens Profile → Notifications.
2. New layout: **Notifications by category** section above the master toggle, with 6 rows: Meal reminders, Timers, Shopping, Partner activity, Imports, Friends & invitations. Each is a switch defaulting to ON.
3. User toggles "Imports" off because they're getting too many "ready to review" pushes during a bulk re-import.
4. The next time an import finishes, the backend reads `prefs.categories.imports == false` and suppresses the push (logs "suppressed_by_category" so it's queryable).
5. User can still see the import via the Imports tab — the in-app activity surface is unaffected.
6. Master "Push Notifications" toggle still works as kill-switch (overrides all categories).

### Flow B — Leo gets a rich import push

1. Leo runs a single-URL import for a Sweet Potato Quiche recipe.
2. Worker finishes extraction → `notify_import_needs_review` runs → loads the first awaiting-review `import_item.parsed_recipe.name = "Sweet Potato Quiche"` and `parsed_recipe.image_url`.
3. Push lands on his iPhone: title "Your Sweet Potato Quiche is ready 🍳", body "Tap to confirm the details we extracted", with the recipe cover image attached (rendered by `PalatefulNotificationService` extension).
4. Tap → `/recipes/import/review-list/{job_id}` (existing route, unchanged).
5. Bulk variant for `total_items > 1`: title "Your bulk import is ready", body "5 recipes need a quick review". No image (no single hero).

### Flow C — Leo taps a meal-event notification

1. Sarah added Leo to a meal event "Saturday brunch — Sweet Potato Quiche".
2. Push: "You're invited to Saturday brunch 🥞" / "Sarah invited you — tap to RSVP".
3. Tap → `/calendar/meals/{meal_event_id}` (NEW). Lightweight detail screen shows title, recipe with thumbnail, scheduled time, participants list with statuses, RSVP buttons.
4. Today's behavior of routing to `/calendar` root remains a fallback if the meal_event_id isn't in the payload (defensive).

### Flow D — Partner adds a recipe to a shared book (RECIPE_ADDED fix)

1. Sarah adds "Banana Bread" to "Weeknight Dinners" (a shared book).
2. Backend: `recipe_router.py:91` now calls `notify_recipe_added(...)` with the right signature → notification fires to all other book members (NOT Sarah herself).
3. Leo gets: title "🍳 New in Weeknight Dinners", body "Sarah added Banana Bread", with recipe cover image attached.
4. Tap → `/recipes/{recipe_id}` (existing route).
5. Subject to per-category opt-out via `prefs.categories.partner_activity` (new) — falls back to legacy `prefs.partner_activity` for old clients.

## Frontend changes

- **`app/lib/features/profile/notification_preferences_screen.dart`** (MODIFIED)
  - New section above existing toggles: "Notifications by category" with 6 switches: Meal reminders, Timers, Shopping, Partner activity, Imports, Friends & invitations.
  - Each toggle reads/writes a key under `prefs.categories.{key}` (new nested shape). Local state defaults to `true` if the key is missing (matches backend default).
  - Master "Push Notifications" toggle stays — flipping it off disables everything; flipping on doesn't re-enable individual categories that were off.
  - "Quiet Hours" + timezone unchanged.
  - "Auto-approve high-confidence imports" stays as a separate row with a clear label (it's a behavior toggle, not a notification opt-out).
  - On save, POST the full prefs JSON shape (legacy + new keys both included for transition).
  - QA walkthrough must include: toggling a category off → triggering its event → confirming no push arrives + a "suppressed_by_category" line appears in API logs.

- **`app/lib/core/services/push_notification_service.dart`** (MODIFIED)
  - Add a new case in `_routeForNotification` for `meal_event_invite`/`meal_event_reminder`/`meal_event_updated`: if `data['meal_event_id']` is non-null, route to `/calendar/meals/$id`; otherwise fallback to `/calendar`.
  - No other behavior changes (foreground SnackBar, error reporting, etc. all stay).

- **`app/lib/features/calendar/screens/meal_detail_screen.dart`** (NEW)
  - Lightweight read-only-ish detail screen.
  - Renders: meal title, scheduled_at (formatted with timezone), meal_type chip, recipe card (with thumbnail) if recipe_id is set, participant list with statuses (pending / accepted / declined), RSVP buttons (Accept / Decline / Maybe) for the current user if they're a participant.
  - Edit button → opens the existing meal-edit sheet.
  - Loaded via `MealCalendarService.getMealEvent(id)` (use existing service; add the method if missing).
  - Empty/loading/error states: spinner while loading, "Couldn't load this meal — open Calendar instead" with a button on error.

- **`app/lib/core/router/app_router.dart`** (MODIFIED)
  - Add route: `GoRoute(path: '/calendar/meals/:id', ...)` mounted under the calendar nav shell so the bottom nav bar persists.
  - The route param is the meal_event UUID; the screen looks up the event via the calendar service.

## Backend changes

- **`libraries/utils/utils/services/notification_copy.py`** (NEW)
  - One function per (notification_type, variant) pair, returning a `(title, body)` tuple.
  - Variants are keyword args, e.g. `import_needs_review(recipe_name=None, count=1)` returns:
    - If `count == 1 and recipe_name`: `("Your {recipe_name} is ready 🍳", "Tap to confirm the details we extracted.")`
    - If `count == 1 and not recipe_name`: `("Your recipe is ready to review", "Tap to confirm the details.")`
    - If `count > 1`: `("Your bulk import is ready", f"{count} recipes need a quick review.")`
  - Module-level constants for emoji palette so we don't re-pick. Keep emoji *light* — title only when it adds clarity.
  - Initially populate with the rich variants needed by Epics B/C/D/E. Other epics extend the module.

- **`libraries/utils/utils/services/import_notifications.py`** (MODIFIED)
  - Refactor `notify_import_needs_review` to:
    1. Query the first awaiting-review `ImportItem` for the job (ordered by created_at).
    2. Extract `parsed_recipe.get("name")` for the recipe name; `parsed_recipe.get("image_url")` for the image.
    3. Call `notification_copy.import_needs_review(recipe_name=..., count=job.pending_review_items)` to get title/body.
    4. Pass `image_url` to the `PushNotification(image_url=...)` constructor.
  - Single new SQL query per call (acceptable — this fires once per terminal job state change, not in a hot loop).

- **`services/api/src/api/v1/recipe_book/notifications.py`** (MODIFIED) — fix RECIPE_ADDED arity bug
  - Audit findings (per Phase 2 backend research): `recipe_router.py:91` calls `notify_recipe_added(added_by_user=user, ...)` but the function signature expects a different param name. Confirm the exact mismatch during dev (could be `actor` vs `added_by_user`) and fix in place.
  - Add a smoke test that exercises the path end-to-end with a real DB session — this is exactly the kind of bug a CI integration test would catch.
  - Use `notification_copy.recipe_added(actor_name=..., recipe_name=..., book_name=...)` for title/body.

- **`services/api/src/db/models/user.py`** + migration (MODIFIED)
  - `notification_preferences` is already a JSONB column. No schema change.
  - Add a default-value helper in the User model: `categories_default()` returns `{meals: True, timers: True, shopping: True, partner_activity: True, imports: True, friends_invitations: True}`.

- **`libraries/utils/utils/services/push_notification.py`** (MODIFIED)
  - Add a `_category_for_type` mapping: each `NotificationType` maps to one of the 6 categories (or `None` for diagnostic types like TEST that bypass).
  - In `send_to_user`, after the `push_enabled` check and before the quiet-hours check, add:
    ```python
    category = _category_for_type.get(notification.notification_type)
    if category and not is_diagnostic and not force:
        categories = (prefs.get("categories") or {})
        # Default to True if missing — old clients without `categories` get all-on.
        if categories.get(category, True) is False:
            logger.info("push_notifications: suppressed (category=%s) user=%s type=%s", category, user.id, type_value)
            return {**base_result, "suppressed_by_category": True}
    ```
  - Update `base_result` to include `suppressed_by_category: False` field.
  - Legacy `partner_activity` flat field continues to work as a fallback when `categories.partner_activity` is missing — read via:
    ```python
    if category == "partner_activity" and "categories" not in prefs and prefs.get("partner_activity") is False:
        # Old client, legacy shape — respect.
    ```

- **`services/api/src/api/v1/user/preferences.py`** (or wherever the PUT prefs handler lives) (MODIFIED)
  - Accept the new nested `categories` key in the request payload.
  - Validate keys against the known set (reject unknown keys to prevent typos from silently being saved).
  - Store as-is in `notification_preferences.categories`.
  - Smoke test: GET /me, confirm `categories` echo matches what was PUT.

## Infrastructure changes

- **None.** No new tables, no Terraform, no Celery beat schedule. The `notification_preferences` JSONB shape change is additive and doesn't require a migration.

## Initial Design Principles (pre-party-mode)

1. **Foundation, not features.** This epic is consumed by B/C/D/E; it doesn't ship a brand-new user-visible category itself (apart from the prefs UI and the meal detail screen).
2. **Copy lives in one place.** `notification_copy.py` is the single source of truth. Callsites pass data, get strings.
3. **Per-category opt-out is enforced server-side.** Don't push noise the user opted out of. Frontend toggle is just the UI shell.
4. **Backwards-compat without shim sprawl.** Default missing prefs to `true` server-side. Legacy `partner_activity` continues to work. No version-detection branching.
5. **Rich copy where data exists.** Recipe name in single-import push, image where present. Don't pretend data we don't have.
6. **Inherit from prior epics.** No feature flags, no backwards-compat shims, inline fixes, ErrorReporter for failures.

## File structure (expected)

```
app/lib/core/router/
└── app_router.dart                                          # MODIFIED — /calendar/meals/:id route

app/lib/core/services/
└── push_notification_service.dart                           # MODIFIED — meal-event deep-link refinement

app/lib/features/calendar/screens/
└── meal_detail_screen.dart                                  # NEW — lightweight detail + RSVP

app/lib/features/profile/
└── notification_preferences_screen.dart                     # MODIFIED — per-category toggles

libraries/utils/utils/services/
├── notification_copy.py                                     # NEW — one source of truth for title/body
├── push_notification.py                                     # MODIFIED — _category_for_type + suppression check
└── import_notifications.py                                  # MODIFIED — load recipe name + image

services/api/src/api/v1/recipe_book/
└── notifications.py                                         # MODIFIED — RECIPE_ADDED arity bug fix

services/api/src/api/v1/user/
└── preferences.py                                           # MODIFIED — accept + validate categories key
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| nfn-1 | Backend per-category prefs check + categories defaults | 🔴 P0 | 0.5 d | None |
| nfn-2 | `notification_copy.py` module + import-needs-review rich copy with name + image | 🔴 P0 | 0.5 d | nfn-1 (uses category mapping) |
| nfn-3 | Fix RECIPE_ADDED arity bug + use copy library | 🔴 P0 | 0.25 d | nfn-2 (uses copy library) |
| nfn-4 | Frontend per-category prefs UI | 🔴 P0 | 0.5 d | nfn-1 (consumes new schema) |
| nfn-5 | `/calendar/meals/:id` route + meal detail screen + push deep-link refinement | 🟡 P1 | 0.75–1 d | None (parallel) |

**Total estimated effort: 2.5–3 days**

---

## Story nfn-1: Backend per-category prefs check + categories defaults

As a user,
I want to opt out of any one notification category without disabling all pushes,
so that I can keep timer alerts on while muting partner activity (or any combo).

### Acceptance Criteria

1. `notification_preferences` JSONB stores a `categories` sub-object with 6 keys: `meals`, `timers`, `shopping`, `partner_activity`, `imports`, `friends_invitations`. All default to `true`.
2. `_category_for_type` mapping in `push_notification.py` maps every non-diagnostic `NotificationType` to exactly one category. New types added in later epics extend this mapping.
3. `send_to_user` checks the category preference after the `push_enabled` master check and before quiet hours. On suppression: log INFO `suppressed (category=...)`, return `{..., suppressed_by_category: True}`.
4. Diagnostic types (`TEST`) bypass the category check (force=True is the existing path; preserve).
5. Legacy `partner_activity` flat field continues to work for the partner-activity category when `categories` is absent (old clients).
6. `PUT /v1/user/preferences` accepts `notification_preferences.categories`. Unknown keys → 400 with descriptive error. Persisted as-is.
7. Backend unit tests:
   - Test A: `categories.imports = False` + `IMPORT_NEEDS_REVIEW` send → suppressed, no FCM call, log line emitted, response shape correct.
   - Test B: `categories` absent + same send → fires (default `true`).
   - Test C: legacy `partner_activity = False` (no categories key) + RECIPE_ADDED → suppressed.
   - Test D: master `push_enabled = False` + any category `True` → still suppressed (master wins).
   - Test E: PUT with unknown category key → 400.

### Key Files
- Modify: `libraries/utils/utils/services/push_notification.py`
- Modify: `services/api/src/api/v1/user/preferences.py` (or equivalent PUT handler)
- Test: `libraries/utils/tests/services/test_push_notification.py`, `services/api/tests/api/v1/user/test_preferences.py`

### Risks / notes
- New types added in later epics MUST extend `_category_for_type`. Add a type-checked exhaustiveness assertion (e.g., `assert set(_category_for_type.keys()) >= {t for t in NotificationType if t != NotificationType.TEST}`) so adding a type without category mapping fails CI.
- Diagnostic types: only `TEST` for now. `SYSTEM` is deferred but should be added to `_DIAGNOSTIC_TYPES` if/when it activates.
- **Suppression order (locked by party-mode):** master `push_enabled` → per-category → quiet hours → `force` override. Document this ordering with an inline comment in `send_to_user`. Future contributors must not reorder these checks — `force` is a deliberate escape valve at the bottom; categories are the user's specific opt-out and trump quiet hours suppression-wise (a user who turns off Imports doesn't want Imports during waking hours either).

---

## Story nfn-2: `notification_copy.py` module + rich import copy

As Leo,
I want my single-recipe imports to surface the actual recipe name in the push (and the cover image where available), and bulk imports to summarize the count,
so that "Your Sweet Potato Quiche is ready 🍳" lands on my phone instead of "Your recipe is ready to review".

### Acceptance Criteria

1. New module `libraries/utils/utils/services/notification_copy.py` exports per-(type, variant) functions returning `(title: str, body: str)` tuples. Initial functions: `import_needs_review`, plus stubs for the variants Epics B/C/D/E will extend.
2. Each function accepts only the data it needs as keyword args; defaults are explicit; no global state.
3. `notify_import_needs_review` in `import_notifications.py` is refactored to:
   - Query the first awaiting-review `ImportItem` for the job (`session.query(ImportItem).filter_by(import_job_id=job.id, status='awaiting_review').order_by(ImportItem.created_at).first()`).
   - Extract `recipe_name = item.parsed_recipe.get("name")` and `image_url = item.parsed_recipe.get("image_url")` defensively (both nullable).
   - Call `notification_copy.import_needs_review(recipe_name=recipe_name, count=job.pending_review_items)`.
   - Pass `image_url` to `PushNotification(image_url=image_url)`.
4. Backend unit tests:
   - Test A: single-recipe job with `parsed_recipe.name = "Sweet Potato Quiche"` → push title contains "Sweet Potato Quiche".
   - Test B: single-recipe job with no name in `parsed_recipe` → falls back to "Your recipe is ready to review" (unchanged behavior).
   - Test C: bulk job (5 items) → push title is "Your bulk import is ready", body mentions "5 recipes".
   - Test D: single-recipe job with `image_url` present → `PushNotification.image_url` is set.
   - Test E: single-recipe job with `image_url` absent → `image_url` is None, no extra query attempted.
5. The image is the extractor's URL — the source-photo promotion runs after approval and is not yet available at this notification time. Document this in a one-line comment in the function.

### Key Files
- Create: `libraries/utils/utils/services/notification_copy.py`
- Modify: `libraries/utils/utils/services/import_notifications.py`
- Test: `libraries/utils/tests/services/test_notification_copy.py`, extend `test_import_notifications.py`

### Risks / notes
- Don't query the item if `pending_review_items > 1` — bulk variant doesn't need it. Save the round-trip.
- Recipe names can contain emoji or special chars — pass through as-is (FCM accepts UTF-8). Don't truncate; FCM enforces its own limits.
- The `parsed_recipe` JSON shape is owned by the extractor (`extract_recipe_task._serialize_recipe`) — any rename of the `name` field there breaks this. Reference the line number in the function comment.

---

## Story nfn-3: Fix RECIPE_ADDED arity bug + use copy library

As Leo,
I want shared-book members to actually receive a push when a partner adds a new recipe to a book they share with me,
so that the existing wired-up code path stops crashing silently and the notification lands.

### Acceptance Criteria

1. The arity / parameter mismatch in `services/api/src/api/v1/recipe_book/notifications.py` (called from `recipe_router.py:91`) is fixed — confirm during dev whether the issue is `added_by_user` vs `actor` vs missing `book` kwarg.
2. The function uses `notification_copy.recipe_added(actor_name=..., recipe_name=..., book_name=...)` for title/body. Suggested copy: `("🍳 New in {book_name}", "{actor_name} added {recipe_name}")`.
3. `image_url` from the new recipe (if any) is passed to `PushNotification(image_url=...)`.
4. Recipient list excludes the actor (don't push someone for their own action).
5. Each recipient is checked against `categories.partner_activity` via the nfn-1 path.
6. Integration test: create a shared book with two members, member A adds a recipe, assert member B's `send_to_user` is called with the right copy and image, assert member A's send is not called.
7. Manual verification: Leo and Sarah on a shared book; Sarah adds a recipe → Leo gets a push within seconds, with the cover image attached.

### Key Files
- Modify: `services/api/src/api/v1/recipe_book/notifications.py`
- Modify: `services/api/src/routers/v1/recipe_router.py` (if the bug is at the callsite, not the function)
- Test: `services/api/tests/api/v1/recipe_book/test_notifications.py`

### Risks / notes
- The "arity bug" is a Phase 2 audit finding and should be re-verified during dev. If the bug isn't reproducible, the story collapses to "swap to notification_copy.py" only.
- Don't add error suppression around the call — let CI integration tests catch regressions.

---

## Story nfn-4: Frontend per-category prefs UI

As a user,
I want a simple, scrollable Notifications screen that lets me toggle each category on or off, with the master switch and quiet hours still in place,
so that I have one obvious surface to manage notification noise.

### Acceptance Criteria

1. `notification_preferences_screen.dart` adds a "Notifications by category" section above the existing toggles, with 6 switches: Meal reminders, Timers, Shopping, Partner activity, Imports, Friends & invitations.
2. Each switch defaults to `true` for new users; reads from `prefs.categories.{key}` for existing users; falls back to `true` if missing (matches backend default).
3. The "Push Notifications" master switch and "Quiet Hours" rows stay visually distinct (above and below the categories block respectively).
4. "Auto-approve high-confidence imports" stays as a separate row, clearly NOT a notification opt-out.
5. Save flow: PUT `/v1/user/preferences` with the full `notification_preferences` JSON including the `categories` sub-object. Loading + error states handled (existing pattern in the screen).
6. Disabled state: when master toggle is off, the category switches are visually disabled (grey + un-tappable) but their saved values are preserved (toggling master back on restores prior state).
7. Flutter widget tests:
   - Test A: render with `categories` empty → all 6 switches default to ON.
   - Test B: render with `categories.imports = false` → Imports switch is off, others ON.
   - Test C: toggle Meal reminders off → save called with `categories.meals = false`.
   - Test D: master OFF → all category switches disabled (visual + tap-to-no-op).
8. QA walkthrough: toggle Imports off → trigger an import that lands in awaiting-review → verify NO push arrives + a "suppressed_by_category" line in API logs (via `bin/prod-logs` or local log).

### Key Files
- Modify: `app/lib/features/profile/notification_preferences_screen.dart`
- Modify: `app/test/features/profile/notification_preferences_screen_test.dart` (or equivalent)

### Risks / notes
- Keep the visual hierarchy obvious: master at top, categories in the middle, quiet hours at the bottom. Don't bury categories.
- For the labels, use the exact category keys' user-facing names — see the table at the top of the screen for the canonical labels (Meal reminders, Timers, Shopping, Partner activity, Imports, Friends & invitations).

---

## Story nfn-5: `/calendar/meals/:id` route + meal detail screen + push deep-link refinement

As Leo,
I want tapping a meal-event push to land me on a screen that shows that specific meal — title, recipe, time, who's coming — instead of the calendar root,
so that I don't have to scroll-find the meal someone just notified me about.

### Acceptance Criteria

1. New route in `app/lib/core/router/app_router.dart`: `/calendar/meals/:id` mounted under the calendar nav shell so the bottom nav persists. Path param is the meal_event UUID.
2. New screen `meal_detail_screen.dart`:
   - Loading state: spinner.
   - Loaded state: meal title (large), scheduled_at formatted with timezone, meal_type chip, recipe card with thumbnail (tap → `/recipes/:id`), participants list (name + status badge: pending/accepted/declined/maybe), RSVP buttons (Accept / Decline / Maybe) for the current user if they're a participant, an Edit button that opens the existing meal-edit sheet.
   - Error state: "Couldn't load this meal — open Calendar instead" with a button to `/calendar`.
3. The screen uses the existing `MealCalendarService.getMealEvent(id)` method (add it if missing). RSVP buttons call existing meal_event participant endpoints.
4. `_routeForNotification` in `push_notification_service.dart` updated: when `notification_type` is `meal_event_invite`, `meal_event_reminder`, or `meal_event_updated` AND `data['meal_event_id']` is present, route to `/calendar/meals/$id`. Fallback to `/calendar` when the id is absent (defensive).
5. Backend: confirm `MEAL_EVENT_*` notifications already include `meal_event_id` in the `data` payload (per Phase 2 audit, they do). No backend changes needed here.
6. Flutter integration test: simulate tapping a `meal_event_invite` notification with `data.meal_event_id` set → assert navigation lands on `/calendar/meals/<id>`. Without the id → fallback to `/calendar`.
7. Manual verification: Sarah invites Leo to a meal → push lands → Leo taps → detail screen renders correctly with Accept/Decline/Maybe buttons. Tap Decline → status updates → screen re-renders.

### Key Files
- Modify: `app/lib/core/router/app_router.dart`
- Create: `app/lib/features/calendar/screens/meal_detail_screen.dart`
- Modify: `app/lib/core/services/push_notification_service.dart`
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (if `getMealEvent` not present)
- Test: `app/integration_test/meal_detail_screen_test.dart` (or equivalent)

### Risks / notes
- The detail screen is intentionally minimal — it's a target for notifications, not a full meal-management surface. Resist adding features here; the existing meal-edit sheet covers updates.
- If the meal_event has been deleted between push send and tap, the screen's error state handles it gracefully.

## Dependencies

- nfn-1 blocks nfn-2 + nfn-4 (they consume the new prefs schema and category mapping).
- nfn-2 blocks nfn-3 (uses the copy library).
- nfn-5 is independent of the others — can ship in parallel.

## Open questions for the user

- None at draft time. All scope decisions resolved in the 2026-04-21 user batch.

## Definition of Done (Epic Level)

- Profile → Notifications shows 6 per-category toggles. Each toggle independently suppresses its category.
- An import-needs-review push for a single recipe lands with the recipe name in the title and the cover image attached.
- A bulk import push lands with the count in the body.
- A partner adding a recipe to a shared book triggers a push to the other members (the long-broken RECIPE_ADDED path is alive).
- Tapping any meal-event push lands on `/calendar/meals/:id`, not `/calendar` root.
- All five categories' opt-out paths are exercised in tests; manual smoke test confirms one round-trip per category.
- No regression in TEST push or any existing wired notification.
- `notification_copy.py` is the only place new category copy gets written for the rest of the notifications work.
