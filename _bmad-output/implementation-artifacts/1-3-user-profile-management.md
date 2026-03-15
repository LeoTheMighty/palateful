# Story 1.3: User Profile Management

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to manage my profile with a display name and preferences,
so that my identity is personalized across the app.

## Acceptance Criteria

1. Given I am signed in, when I navigate to the Profile tab, then I see my display name, email, and profile picture (from Auth0)
2. And I can edit my display name and save changes via the API
3. And changes persist across app restarts (verified via `GET /v1/users/me`)
4. And the profile screen uses the standard design system styling (cream/chocolate palette, Playfair Display headings, theme-aware colors)

## Tasks / Subtasks

- [x] Task 1: Add missing API client methods (AC: #2, #3)
  - [x] Add `updateProfile({String? name})` method → `PUT /v1/users/me` (need to create this endpoint)
  - [x] Add `setUsername(String username)` method → `PUT /v1/users/me/username`
  - [x] Add `checkUsername(String username)` method → `GET /v1/users/check-username/{username}`

- [x] Task 2: Create backend update profile endpoint (AC: #2, #3)
  - [x] Create `services/api/src/api/v1/user/update_me.py` — `UpdateMe(Endpoint)` with `Params(name: str | None)`
  - [x] Add `UpdateProfileRequest` schema to `services/api/src/schemas/user.py`
  - [x] Wire route `PUT /v1/users/me` in `services/api/src/routers/v1/user_router.py`
  - [x] Only allow updating `name` field (not email/auth0_id/picture — those come from Auth0)

- [x] Task 3: Build profile screen UI (AC: #1, #4)
  - [x] Replace placeholder `ProfileScreen` with full implementation
  - [x] Display: profile picture (CircleAvatar from Auth0 picture URL), display name, email, member since date
  - [x] "Edit Profile" section: tappable name field opens edit dialog/inline edit
  - [x] Username section: display current username or "Set username" prompt, with edit flow and real-time availability checking
  - [x] Logout button (already exists — preserve current behavior)
  - [x] Style with `Theme.of(context).colorScheme.*` and `textTheme.*` — no hardcoded colors
  - [x] Use Playfair Display for section headings per design system

- [x] Task 4: Implement name editing flow (AC: #2, #3)
  - [x] Tap name → opens edit dialog with current name pre-filled
  - [x] Save button calls `apiClient.updateProfile(name: newName)`
  - [x] On success, update local state and show confirmation
  - [x] On error, show error message in themed error container
  - [x] Loading state during save (disable button, show indicator)

- [x] Task 5: Implement username editing flow (AC: #2)
  - [x] Username section shows current username or "Set username" CTA
  - [x] Tap → opens dialog with text field
  - [x] Real-time availability checking via `checkUsername()` as user types (debounced)
  - [x] Validation feedback: available (green check), taken (red x), invalid format, reserved
  - [x] Save calls `apiClient.setUsername(username)`
  - [x] Show 30-day cooldown warning if username was previously set

- [x] Task 6: Fetch and display profile data (AC: #1, #3)
  - [x] On screen init, call `apiClient.getMe()` to fetch current user data
  - [x] Parse response into local state (name, email, picture, username, createdAt)
  - [x] Show shimmer/loading state while fetching
  - [x] Handle error state (failed to load profile)
  - [x] Data persists across navigating away and back (within session)

- [x] Review Follow-ups Round 2 (AI)
  - [x] [AI-Review][MEDIUM] `hasUsernameChanged` — now checks `_usernameChangedAt!.isAfter(DateTime.now().subtract(const Duration(days: 30)))` so only shows warning during active cooldown
  - [x] [AI-Review][MEDIUM] Name dialog — added `barrierDismissible: false` and `PopScope(canPop: !isSaving)` for consistent save protection
  - [x] [AI-Review][MEDIUM] Username dialog — replaced unconditional `barrierDismissible: false` with `PopScope(canPop: !isSaving)` for finer control
  - [x] [AI-Review][LOW] `UpdateProfileRequest` — removed dead schema class from `schemas/user.py`
  - [x] [AI-Review][LOW] `validate_name` — now strips before length check (`len(v.strip()) > 100`)

- [x] Review Follow-ups (AI)
  - [x] [AI-Review][HIGH] `UpdateMe` endpoint has zero name validation — added `.strip()`, empty-after-strip rejection, `max_length=100` via field_validator, and 3 new tests (whitespace-only, empty string, too-long)
  - [x] [AI-Review][MEDIUM] Username dialog debounce timer — added `context.mounted` check before the `await _apiClient.checkUsername()` call
  - [x] [AI-Review][MEDIUM] Username dialog — set `barrierDismissible: false` to prevent dismissal during save
  - [x] [AI-Review][MEDIUM] `app/pubspec.lock` — added to File List
  - [x] [AI-Review][LOW] Auto-generated test report files — added `reports/` to `.gitignore`
  - [x] [AI-Review][LOW] `UserResponse` schema — added `username`, `username_changed_at`, `pending_invitation_count` fields

- [x] Task 7: Write tests (AC: #1-4)
  - [x] Widget test: profile screen renders user info (name, email, avatar)
  - [x] Widget test: edit name dialog appears on tap
  - [x] Widget test: username section renders with edit capability
  - [x] Widget test: logout button exists and is functional
  - [x] Widget test: loading state shows shimmer
  - [x] Widget test: error state displays correctly
  - [x] Backend test: `PUT /v1/users/me` updates name and returns updated user

## Dev Notes

### Critical Context: This Is a Brownfield Project

**Backend is MOSTLY BUILT.** The existing codebase has:
- `GET /v1/users/me` endpoint returning full user data including pending_invitation_count
- `PUT /v1/users/me/username` with full validation (3-20 chars, format, reserved words, 30-day cooldown)
- `GET /v1/users/check-username/{username}` for real-time availability checking
- `GET /v1/users/search` for user search with friendship status
- Push notification token management endpoints
- Notification preferences endpoints (get/update)
- User model with all required fields (name, email, picture, username, etc.)

**What ACTUALLY needs to be built:**
1. `PUT /v1/users/me` backend endpoint (update profile — only name for now)
2. Replace placeholder `ProfileScreen` with real UI
3. Add API client methods for profile operations
4. Write tests

**DO NOT** rewrite `get_me.py`, `set_username.py`, `check_username.py`, or the user model. They work.

### Existing Profile Screen (PLACEHOLDER)

The current `ProfileScreen` at `app/lib/features/profile/profile_screen.dart` is a placeholder:
```dart
// Current state — just shows "Profile coming soon" with a logout button
```
This needs a complete replacement, but the logout logic should be preserved.

### Backend Endpoint Pattern (MANDATORY)

Follow the existing `Endpoint` class pattern. Example from `set_username.py`:
```python
class SetUsername(Endpoint):
    class Params(BaseModel):
        username: str
    class Response(BaseModel):
        success: bool
        username: str
        message: str
    def execute(self, params: "SetUsername.Params"):
        # Business logic here
        return self.success(...)
```

### GetMe Response Shape

The `GET /v1/users/me` response already includes everything needed:
```python
{
    "id": str,
    "email": str | None,
    "name": str | None,
    "username": str | None,
    "picture": str | None,
    "has_completed_onboarding": bool,
    "default_recipe_book_id": str | None,
    "created_at": datetime,
    "username_changed_at": datetime | None,
    "pending_invitation_count": int
}
```

### Username Validation Rules (from `set_username.py`)

- 3-20 characters
- Must start with a letter
- Only lowercase letters, numbers, underscores
- Case-insensitive uniqueness
- Reserved words: admin, support, palateful, profile, settings, help, etc.
- 30-day cooldown between changes (checked via `username_changed_at`)

### Architecture Compliance

- **Backend pattern**: `Endpoint` class with `Params`/`Response` inner classes, `self.success()` for responses
- **Frontend state**: LoginScreen uses `setState` (not Riverpod) — acceptable for now per Story 1.1/1.2 pattern. Architecture says Riverpod but current screens use setState. Follow existing pattern.
- **Theme**: Use `Theme.of(context).colorScheme.*` and `textTheme.*` — NOT hardcoded `AppColors.*`
- **Navigation**: Profile is already wired as a tab in `app_router.dart` via `StatefulShellBranch`
- **DI**: Use `getIt<ApiClient>()` and `getIt<AuthService>()` — same as LoginScreen
- **API client**: Add methods to existing `api_client.dart` — same pattern as `getMe()` and `completeOnboarding()`

### File Structure

**Files to CREATE:**
- `services/api/src/api/v1/user/update_me.py` — new endpoint for updating profile

**Files to MODIFY:**
- `app/lib/features/profile/profile_screen.dart` — replace placeholder with full profile UI
- `app/lib/core/services/api_client.dart` — add `updateProfile()`, `setUsername()`, `checkUsername()` methods
- `services/api/src/schemas/user.py` — add `UpdateProfileRequest` schema
- `services/api/src/routers/v1/user_router.py` — add `PUT /v1/users/me` route
- `app/test/login_screen_test.dart` or new `app/test/profile_screen_test.dart` — profile tests

**Files to NOT TOUCH:**
- `services/api/src/api/v1/user/get_me.py` — works as-is
- `services/api/src/api/v1/user/set_username.py` — works as-is
- `services/api/src/api/v1/user/check_username.py` — works as-is
- `services/api/src/api/v1/user/push_tokens.py` — notification prefs are a future story
- `libraries/utils/utils/models/user.py` — model has all needed fields
- `app/lib/core/router/app_router.dart` — profile route already configured
- `app/lib/core/theme/` — theme files work as-is

### Testing Requirements

- Widget test: profile screen renders user info sections
- Widget test: edit interactions (name dialog, username)
- Widget test: loading/error states
- Widget test: logout button
- Backend test: `PUT /v1/users/me` updates name correctly
- Manual: edit name → close app → reopen → name persists
- Manual: set username → verify availability checking works
- Run existing tests: `cd app && flutter test` — no regressions

### Library/Framework Requirements

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| cached_network_image | (add if not present) | Display Auth0 profile picture | Disk-cached network images for avatar |

Check if `cached_network_image` is already in `pubspec.yaml`. If not, add it. If the profile picture URL is null, show a fallback icon.

### Previous Story Intelligence (Story 1.2)

From Story 1.2 implementation:
- **`mounted` checks**: Always add `if (!mounted) return;` after any async call before `setState` or `context.go()`
- **Loading state management**: Set `_isLoading = true` before async, reset to false in finally/catch
- **Error handling**: Wrap async calls in try/catch, show errors in themed `Container` with `colorScheme.errorContainer`
- **Widget tests without DI**: Cannot instantiate screens that depend on `getIt<AuthService>()` in tests. Test UI patterns directly with equivalent widget trees.
- **`GoogleFonts.config.allowRuntimeFetching = false`** needed in test `setUp()`
- **Icons**: Use platform-appropriate icons. Don't use `Icons.g_mobiledata` for Google (use styled text/custom widget instead)
- **Review findings pattern**: 3 rounds of review caught: missing mounted checks, missing loading guards, dead code, icon mismatches, web-only bugs. Be thorough on first pass.
- **Account linking**: Auth0 Post Login Action handles duplicate emails across providers. Backend now accepts nullable email.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.3] — User story and acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture] — Riverpod, go_router, feature-first structure
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns] — Endpoint class pattern, naming conventions
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — Profile tab: "Settings, account, import, preferences"
- [Source: services/api/src/api/v1/user/get_me.py] — GetMe endpoint returning full user data
- [Source: services/api/src/api/v1/user/set_username.py] — Username validation and 30-day cooldown logic
- [Source: services/api/src/api/v1/user/check_username.py] — Real-time username availability check
- [Source: services/api/src/routers/v1/user_router.py] — Existing user routes
- [Source: services/api/src/schemas/user.py] — UserResponse, OnboardingRequest schemas
- [Source: app/lib/features/profile/profile_screen.dart] — Current placeholder profile screen
- [Source: app/lib/core/services/api_client.dart] — API client with getMe(), completeOnboarding()
- [Source: app/lib/core/services/auth_service.dart] — Auth service with logout()
- [Source: _bmad-output/implementation-artifacts/1-2-sign-in-with-google-and-apple.md] — Previous story learnings

## QA Checklist

### Prerequisites
- [ ] Run `cd app && flutter pub get`
- [ ] Run `cd app && flutter test` — all tests should pass
- [ ] Backend running (`docker compose up`)

### Profile Display (AC #1)
- [ ] Navigate to Profile tab
- [ ] See profile picture (circle avatar from Auth0)
- [ ] See display name
- [ ] See email address
- [ ] See "Member since" date
- [ ] If no profile picture, see fallback icon

### Edit Name (AC #2)
- [ ] Tap name → edit dialog opens
- [ ] Current name pre-filled
- [ ] Change name → save → success feedback
- [ ] Loading state during save
- [ ] Error state on failure
- [ ] Empty name validation

### Username (AC #2)
- [ ] See current username or "Set username" prompt
- [ ] Tap → dialog with text field
- [ ] Type → real-time availability feedback (debounced)
- [ ] Invalid format → error message
- [ ] Taken → error message
- [ ] Available → green check
- [ ] Save → success

### Persistence (AC #3)
- [ ] Edit name → navigate away → come back → name persists
- [ ] Edit name → close app → reopen → name persists

### Design System (AC #4)
- [ ] Cream/chocolate palette matches rest of app
- [ ] Playfair Display headings
- [ ] Theme-aware colors (no hardcoded colors)
- [ ] Consistent with login screen and home screen styling

### Regression
- [ ] Logout still works
- [ ] All existing tests pass
- [ ] Login flow unaffected
- [ ] Other tabs (Home, Books, Cart, Calendar) still work

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- Task 1: Added `updateProfile()`, `setUsername()`, `checkUsername()` methods to `api_client.dart` following existing pattern
- Task 2: Created `UpdateMe` endpoint following `Endpoint` class pattern with `Params(name: str | None)` and `Response(success, name, message)`. Added `UpdateProfileRequest` schema. Wired `PUT /v1/users/me` route. Only name field is updatable.
- Task 3: Replaced placeholder `ProfileScreen` with full `StatefulWidget` implementation. Profile picture uses `CachedNetworkImage` with fallback icon. Displays name, email, member since date. Edit Profile section with tappable name/username tiles. Logout button preserved. All colors via `Theme.of(context)`, headings via `GoogleFonts.playfairDisplay`.
- Task 4: Name edit dialog with pre-filled text, empty validation, save/cancel, loading spinner, error display. Updates local state on success.
- Task 5: Username edit dialog with debounced availability checking (500ms), validation feedback icons (check/cancel), 30-day cooldown warning, `@` prefix display. Save disabled until availability confirmed.
- Task 6: `_fetchProfile()` called on `initState`, parses `getMe()` response into local state. Shimmer loading state. Error state with retry button. `mounted` checks after all async calls.
- Task 7: 10 widget tests for profile UI patterns (name/email/avatar display, edit name dialog, username section, logout button, loading shimmer, error state, section headings). 3 backend tests for `PUT /v1/users/me` (update name, null name, empty body). All 35 Flutter tests pass. All 125 backend tests pass.
- Added `cached_network_image: ^3.4.1` dependency to `pubspec.yaml`
- **Review Follow-ups:** Added name validation (strip, empty check, max_length=100) to UpdateMe endpoint with 3 new tests. Fixed username dialog mounted check before API call. Set barrierDismissible: false on username dialog. Added reports/ to .gitignore. Synced UserResponse schema with actual GET /v1/users/me response fields.

### File List

**Created:**
- `services/api/src/api/v1/user/update_me.py` — UpdateMe endpoint
- `app/test/profile_screen_test.dart` — 10 widget tests for profile screen

**Modified:**
- `app/lib/features/profile/profile_screen.dart` — Full profile screen (replaced placeholder)
- `app/lib/core/services/api_client.dart` — Added updateProfile, setUsername, checkUsername methods
- `app/pubspec.yaml` — Added cached_network_image dependency
- `app/pubspec.lock` — Updated lock file (cached_network_image + transitive deps)
- `services/api/src/schemas/user.py` — Added UpdateProfileRequest schema; added username, username_changed_at, pending_invitation_count to UserResponse
- `services/api/src/routers/v1/user_router.py` — Added PUT /v1/users/me route, imported UpdateMe
- `services/api/src/api/v1/user/__init__.py` — Added UpdateMe export
- `services/api/tests/test_user.py` — Added TestUpdateMe class (6 tests)
- `.gitignore` — Added reports/ directory
