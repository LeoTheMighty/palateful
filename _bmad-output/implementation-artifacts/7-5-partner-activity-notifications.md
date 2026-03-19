# Story 7.5: Partner Activity Notifications

Status: done

## Story

As a user,
I want to receive push notifications when my partner shares a book with me or adds a recipe to a shared book,
So that I stay aware of household cooking activity without constant checking.

## Acceptance Criteria

1. **Given** my partner (another book member) adds me to a shared recipe book, **When** the membership is created, **Then** I receive a push notification via Firebase with type `recipe_book_shared` and tapping it navigates to that recipe book screen.

2. **Given** my partner adds a recipe to a shared book I belong to, **When** the recipe is created, **Then** I receive a push notification via Firebase with type `recipe_added` and tapping it navigates to that recipe book screen.

3. **Given** my partner performs actions rapidly (e.g. adds several recipes in succession), **Then** only recipe_added events trigger notifications — NOT recipe edits (update) or archives (remove) — approximating the "notable actions only" batching requirement.

4. **Given** I navigate to Notification Preferences, **When** I view the settings, **Then** I see a "Partner Activity" toggle I can enable or disable independently of the master push toggle.

5. **Given** I disable the "Partner Activity" toggle, **When** my partner adds a recipe to a shared book, **Then** I do NOT receive a push notification for that action.

6. **Given** I have the master push toggle disabled, **When** any partner activity occurs, **Then** no push notification is sent regardless of the Partner Activity toggle (master toggle always wins; handled by existing `PushNotificationService.send_to_user`).

## Tasks / Subtasks

- [x] Task 1: Backend — Notification helpers for recipe books (AC: 1, 2, 3, 5, 6)
  - [x] 1.1 Create `services/api/src/api/v1/recipe_book/notifications.py` following the exact pattern of `services/api/src/api/v1/shopping_list/utils/notifications.py`
  - [x] 1.2 Implement `notify_recipe_book_members(recipe_book_id, notification, database, exclude_user_id=None, category=None)` — queries `RecipeBookUser` for active members (archived_at is None), fetches their `User` objects, filters by `category` preference if supplied (default `True`), calls `push_service.send_to_users(..., database.db)`
  - [x] 1.3 Implement `notify_book_shared(recipe_book_id, recipe_book_name, invited_user, invited_by, database)` — checks `invited_user.notification_preferences.get("partner_activity", True)`, if enabled sends `PushNotification(title="...", body="...", notification_type=NotificationType.RECIPE_BOOK_SHARED, data={"recipe_book_id": recipe_book_id, "recipe_book_name": recipe_book_name})`
  - [x] 1.4 Implement `notify_recipe_added(recipe_book_id, recipe_book_name, recipe_name, added_by_user, database)` — calls `notify_recipe_book_members(...)` with `category="partner_activity"` and `exclude_user_id=str(added_by_user.id)` and `notification_type=NotificationType.RECIPE_ADDED`

- [x] Task 2: Backend — Wire up notifications in routers (AC: 1, 2)
  - [x] 2.1 In `services/api/src/routers/v1/recipe_book_router.py`, in `add_recipe_book_member`, after `AddRecipeBookMember.call(...)`:
    - Fetch the `RecipeBook` object: `book = database.find_by(RecipeBook, id=recipe_book_id)`
    - Fetch the target user: `target_user = database.find_by(User, id=params.user_id)` (already done inside endpoint, pass via response or re-fetch)
    - Call `notify_book_shared(recipe_book_id, book.name, target_user, user, database)` — fire and don't await (sync call)
    - Import `notify_book_shared` from `api.v1.recipe_book.notifications`; import `RecipeBook` from `utils.models.recipe_book`
  - [x] 2.2 In `services/api/src/routers/v1/recipe_router.py`, in `create_recipe`, after the `broadcast_event_to_recipe_book(...)` await:
    - Fetch book: `book = database.find_by(RecipeBook, id=book_id)` (imports `RecipeBook` from `utils.models.recipe_book`)
    - If `book and book.is_shared`: call `notify_recipe_added(book_id, book.name, params.name, user, database)`
    - Import `notify_recipe_added` from `api.v1.recipe_book.notifications`

- [x] Task 3: Backend — Add partner_activity to notification preferences API (AC: 4, 5)
  - [x] 3.1 In `services/api/src/api/v1/user/push_tokens.py`, update `UpdateNotificationPreferences.Params`: add `partner_activity: bool | None = None`
  - [x] 3.2 Update `UpdateNotificationPreferences.Response`: add `partner_activity: bool`
  - [x] 3.3 In `UpdateNotificationPreferences.execute()`, handle new field: `if params.partner_activity is not None: prefs["partner_activity"] = params.partner_activity`; include in Response with default `True`
  - [x] 3.4 Update `GetNotificationPreferences.Response`: add `partner_activity: bool`
  - [x] 3.5 In `GetNotificationPreferences.execute()`, return `partner_activity=prefs.get("partner_activity", True)` in Response

- [x] Task 4: Flutter — Update ApiClient for partner_activity (AC: 4, 5)
  - [x] 4.1 In `app/lib/core/services/api_client.dart`, add `bool? partnerActivity` param to `updateNotificationPreferences(...)`: `if (partnerActivity != null) 'partner_activity': partnerActivity`
  - [x] 4.2 The `getNotificationPreferences()` call already returns raw JSON — the `notification_preferences_screen.dart` reads `data['partner_activity']` directly

- [x] Task 5: Flutter — Add Partner Activity toggle to NotificationPreferencesScreen (AC: 4, 5)
  - [x] 5.1 In `app/lib/features/profile/notification_preferences_screen.dart`, add `bool _partnerActivity = true` state variable
  - [x] 5.2 In `_loadPreferences()`, set `_partnerActivity = (data['partner_activity'] as bool?) ?? true`
  - [x] 5.3 Add a "Household" section with a toggle titled "Partner Activity" / subtitle "Notify when a partner shares a book or adds a recipe"
  - [x] 5.4 On toggle: call `_apiClient.updateNotificationPreferences(partnerActivity: value)` and update state — follows same pattern as `_pushEnabled` toggle

- [x] Task 6: Backend — Tests (AC: 1–6)
  - [x] 6.1 Create `services/api/tests/test_recipe_book_notifications.py` with 12 tests covering:
    - `notify_book_shared` sends to invited user with RECIPE_BOOK_SHARED type
    - `notify_book_shared` skips when `partner_activity=False`
    - `notify_book_shared` includes inviter name in body
    - `notify_recipe_added` sends to members excluding actor
    - `notify_recipe_added` includes recipe name in notification
    - `notify_recipe_added` skips members with `partner_activity=False`
    - `notify_recipe_added` returns gracefully when no recipients
    - `UpdateNotificationPreferences` stores `partner_activity=False`
    - `UpdateNotificationPreferences` stores `partner_activity=True`
    - `GetNotificationPreferences` defaults `partner_activity` to `True`
    - `GetNotificationPreferences` respects stored `partner_activity=False`
    - Push service unavailable handled gracefully
  - [x] 6.2 All 288 existing tests continue to pass

- [x] Task 7: Flutter — Test partner activity toggle (AC: 4, 5)
  - [x] 7.1 Create `app/test/features/profile/notification_preferences_screen_test.dart` with 5 widget tests verifying the Partner Activity toggle label, enabled state, disabled state, callback on tap, and Household section header

## Dev Notes

### Critical Architecture: Notification Pattern

Follow `services/api/src/api/v1/shopping_list/utils/notifications.py` exactly. The pattern is:
1. A `notifications.py` module in the feature folder with helper functions
2. Each helper builds a `PushNotification` and calls `get_push_service().send_to_user/send_to_users(...)`
3. Category filtering happens in the helper (check `user.notification_preferences.get("partner_activity", True)`)
4. `PushNotificationService.send_to_user` handles `push_enabled` + quiet hours automatically — do NOT duplicate those checks

**Reference**: `services/api/src/api/v1/shopping_list/utils/notifications.py`

### Batching Clarification

The epics requirement "partner actions are batched (not every single edit triggers a notification)" is implemented pragmatically:
- **Only** `recipe_added` triggers a push notification (Task 2.2)
- Recipe **updates** (`update_recipe` route) do NOT trigger push — they use WebSocket only
- Recipe **archives** (`delete_recipe` route) do NOT trigger push — WebSocket only
- This means no complex rate-limiting / Celery delay queue is needed
- True time-based batching (e.g., "max 1 notification per 5 minutes per book") is deferred future work

### Notification Types Already Exist

`NotificationType.RECIPE_BOOK_SHARED` and `NotificationType.RECIPE_ADDED` are already defined in `libraries/utils/utils/services/push_notification.py:37-38`. Do NOT add new types.

### Flutter Deep Linking Already Wired

`app/lib/core/services/push_notification_service.dart:212-222` already handles:
```dart
case 'recipe_book_shared':
  final bookId = data['recipe_book_id'];
  if (bookId != null) return '/recipe-books/$bookId';
  return '/recipe-books';

case 'recipe_added':
  final recipeId = data['recipe_id'];
  if (recipeId != null) return '/recipes/$recipeId';
  final bookId = data['recipe_book_id'];
  if (bookId != null) return '/recipe-books/$bookId';
  return '/';
```
No changes needed to `push_notification_service.dart`. The `data` payload must include `recipe_book_id`.

### Notification Preference Storage

`user.notification_preferences` is a JSONB column (see `UpdateNotificationPreferences.execute()`). Adding `partner_activity` is a dict key addition — **no database migration required**. The backend reads it with `.get("partner_activity", True)` so existing users default to opted-in.

### RecipeBook Model

`utils/models/recipe_book.py` has `is_shared: Mapped[bool]` flag (line 25). Check `book.is_shared` before sending `notify_recipe_added` to avoid notifying members of personal books.

### Notification Helper: Member Query

The `RecipeBookUser` join table is in `libraries/utils/utils/models/recipe_book_user.py`. Query pattern:
```python
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

members = database.db.query(RecipeBookUser).filter(
    RecipeBookUser.recipe_book_id == recipe_book_id,
    RecipeBookUser.archived_at.is_(None),
).all()
user_ids = [m.user_id for m in members if str(m.user_id) != exclude_user_id]
users = database.db.query(User).filter(User.id.in_(user_ids)).all()
```

### Router Changes: add_recipe_book_member

The `add_recipe_book_member` route in `recipe_book_router.py` currently calls `AddRecipeBookMember.call(...)` which already fetches `target_user` internally. To get the target user for the notification, re-fetch from DB after the call (preferred — avoids coupling to the endpoint's internals):
```python
from api.v1.recipe_book.notifications import notify_book_shared
from utils.models.recipe_book import RecipeBook
from utils.models.user import User as UserModel

result = AddRecipeBookMember.call(...)
# Fire notification
target_user = database.find_by(UserModel, id=params.user_id)
book = database.find_by(RecipeBook, id=recipe_book_id)
if target_user and book:
    notify_book_shared(str(recipe_book_id), book.name or "Shared Book", target_user, user, database)
return result
```

The route handler is `async def`, but `notify_book_shared` is synchronous — call without `await`.

### State Management: NotificationPreferencesScreen

The screen uses `setState` only — no Riverpod. Follow the exact pattern of `_pushEnabled` for the new `_partnerActivity` toggle. Both toggles call `_apiClient.updateNotificationPreferences(...)` with their respective named param.

### Notification Text Suggestions

- Book shared: title `"You've been added to a recipe book!"`, body `"{inviter_name} added you to {book_name}"`
- Recipe added: title `"New recipe in {book_name}"`, body `"{adder_name} added {recipe_name}"`

### Project Structure Notes

- New file: `services/api/src/api/v1/recipe_book/notifications.py`
- Modified: `services/api/src/routers/v1/recipe_book_router.py` (add notification call in add_recipe_book_member)
- Modified: `services/api/src/routers/v1/recipe_router.py` (add notification call in create_recipe)
- Modified: `services/api/src/api/v1/user/push_tokens.py` (add partner_activity field)
- Modified: `app/lib/core/services/api_client.dart` (add partnerActivity param)
- Modified: `app/lib/features/profile/notification_preferences_screen.dart` (add Partner Activity toggle)
- New test: `services/api/tests/test_recipe_book_notifications.py`
- New/modified test: `app/test/features/profile/notification_preferences_screen_test.dart`

### References

- Shopping list notification pattern: `services/api/src/api/v1/shopping_list/utils/notifications.py`
- Push notification service: `libraries/utils/utils/services/push_notification.py`
- NotificationType enum: `libraries/utils/utils/services/push_notification.py:26-55`
- RecipeBook model (is_shared): `libraries/utils/utils/models/recipe_book.py:25`
- RecipeBookUser model: `libraries/utils/utils/models/recipe_book_user.py`
- add_recipe_book_member endpoint: `services/api/src/api/v1/recipe_book/add_recipe_book_member.py`
- recipe_book_router: `services/api/src/routers/v1/recipe_book_router.py`
- recipe_router create_recipe: `services/api/src/routers/v1/recipe_router.py:60-79`
- NotificationPreferencesScreen: `app/lib/features/profile/notification_preferences_screen.dart`
- ApiClient notification methods: `app/lib/core/services/api_client.dart:380-400`
- Flutter deep-link handler (no changes): `app/lib/core/services/push_notification_service.dart:212-222`
- Story 3.6 notes (notification infrastructure): `_bmad-output/implementation-artifacts/3-6-push-notifications-and-notification-preferences.md`
- Story 7.4 notes (WebSocket pattern, for context): `_bmad-output/implementation-artifacts/7-4-real-time-shared-book-updates.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `notify_book_shared` checks `partner_activity` preference before calling push service; `PushNotificationService.send_to_user` additionally checks `push_enabled` and quiet hours
- `notify_recipe_added` only fires for `recipe_added` events (not updates/removes) — this approximates the epics' "notable actions only" batching requirement without a delay queue
- `RecipeBook.is_shared` flag guards the `create_recipe` notification path — personal books produce no push
- `partner_activity` field stored as JSONB dict key — no DB migration needed; defaults to `True` for existing users via `.get("partner_activity", True)`
- Flutter deep-link handler (`push_notification_service.dart`) already handles `recipe_book_shared` and `recipe_added` navigation — no changes needed
- All 288 backend tests pass; all 54 Flutter tests pass

### File List

- `services/api/src/api/v1/recipe_book/notifications.py` (new)
- `services/api/src/routers/v1/recipe_book_router.py` (modified — notify_book_shared in add_recipe_book_member)
- `services/api/src/routers/v1/recipe_router.py` (modified — notify_recipe_added in create_recipe)
- `services/api/src/api/v1/user/push_tokens.py` (modified — partner_activity in UpdateNotificationPreferences and GetNotificationPreferences)
- `app/lib/core/services/api_client.dart` (modified — partnerActivity param in updateNotificationPreferences)
- `app/lib/features/profile/notification_preferences_screen.dart` (modified — Household section + Partner Activity toggle)
- `services/api/tests/test_recipe_book_notifications.py` (new)
- `app/test/features/profile/notification_preferences_screen_test.dart` (new)
