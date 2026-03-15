# Story 1.4: Onboarding Flow

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a first-time user,
I want to be introduced to the app's key features and prompted to take a first action,
so that I know what Palateful can do and get started quickly.

## Acceptance Criteria

1. Given I have just signed in for the first time, when the app detects I have not completed onboarding, then I see an onboarding flow introducing recipe import, recipe books, and cooking mode
2. And I am prompted to choose a first action: import recipes, create a recipe, or explore
3. And the onboarding can be skipped and does not appear on subsequent launches
4. And the flow uses Playfair Display headings and warm editorial imagery (themed icons/illustrations)

## Tasks / Subtasks

- [x] Task 1: Upgrade welcome screen to design system standards (AC: #1, #4)
  - [x] Replace all hardcoded `AppColors.*` references with `Theme.of(context).colorScheme.*` and `textTheme.*`
  - [x] Use `GoogleFonts.playfairDisplay` for heading "Welcome to Palateful!"
  - [x] Add brief value proposition subtitle: "Your recipes, all in one place"
  - [x] Add 3 feature highlight cards below the name input: Import (upload_file icon), Organize (menu_book icon), Cook (restaurant icon) — each with a short one-line description
  - [x] Replace `CircularProgressIndicator(color: AppColors.chocolate)` with `CircularProgressIndicator(color: Theme.of(context).colorScheme.primary)`
  - [x] Replace error container `AppColors.errorLight`/`AppColors.errorDark` with `colorScheme.errorContainer`/`colorScheme.onErrorContainer`
  - [x] Add `if (!mounted) return;` check after `await _apiClient.getMe()` before `setState`

- [x] Task 2: Upgrade start screen to design system standards (AC: #2, #4)
  - [x] Replace all hardcoded `AppColors.*` references with `Theme.of(context).colorScheme.*` and `textTheme.*`
  - [x] Use `GoogleFonts.playfairDisplay` for heading "How would you like to start?"
  - [x] Replace `AppBar` back button `AppColors.textPrimary` with theme-aware icon color
  - [x] Replace error container with themed `colorScheme.errorContainer`/`colorScheme.onErrorContainer`
  - [x] Replace loading indicator `AppColors.chocolate` with `colorScheme.primary`
  - [x] `_StartMethodCard`: replace `AppColors.cardBackground`, `AppColors.cardBorder`, `AppColors.beige`, `AppColors.chocolate`, `AppColors.textPrimary`, `AppColors.textSecondary`, `AppColors.textTertiary` with theme-aware colors (`colorScheme.surfaceContainerLow`, `colorScheme.outline`, `colorScheme.primaryContainer`, `colorScheme.primary`, `colorScheme.onSurface`, `colorScheme.onSurfaceVariant`, `colorScheme.outline`)
  - [x] Add `if (!mounted) return;` checks after `await _apiClient.completeOnboarding()` before `setState` and `context.go()`
  - [x] Update auth service with `defaultRecipeBookId` from response on successful onboarding completion

- [x] Task 3: Add backend name validation to CompleteOnboarding endpoint (AC: #1)
  - [x] Add `.strip()` and empty-after-strip validation for the `name` field (consistent with `UpdateMe` endpoint from Story 1.3)
  - [x] Add `max_length=100` validation via Pydantic field_validator
  - [x] Add guard against double-completion: if `user.has_completed_onboarding` is already True, return early with existing user data
  - [x] Return `username` and `username_changed_at` in the response `UserResponse` (consistent with Story 1.3 schema sync)

- [x] Task 4: Write Flutter widget tests (AC: #1-4)
  - [x] Widget test: welcome screen renders heading, name input, continue button
  - [x] Widget test: welcome screen shows feature highlight cards
  - [x] Widget test: start screen renders 3 start method cards (Browse, Import, Scratch)
  - [x] Widget test: start method cards have correct titles and icons
  - [x] Widget test: loading state shows progress indicator
  - [x] Widget test: error state renders in themed container
  - [x] `GoogleFonts.config.allowRuntimeFetching = false` in test `setUp()`

- [x] Task 5: Write backend tests for CompleteOnboarding (AC: #1, #3)
  - [x] Test: successful onboarding creates recipe book and marks user as onboarded
  - [x] Test: empty name is rejected (400)
  - [x] Test: whitespace-only name is rejected (400)
  - [x] Test: name over 100 characters is rejected (422)
  - [x] Test: already-onboarded user returns existing data without creating duplicate recipe book

## Dev Notes

### Critical Context: This Is a Brownfield Project

**Both screens already exist and the backend endpoint works.** The existing codebase has:
- `OnboardingWelcomeScreen` at `app/lib/features/onboarding/onboarding_welcome_screen.dart` — functional but uses hardcoded `AppColors.*` colors, no Playfair Display, no feature introduction
- `OnboardingStartScreen` at `app/lib/features/onboarding/onboarding_start_screen.dart` — functional but uses hardcoded `AppColors.*` colors, no Playfair Display
- `CompleteOnboarding` endpoint at `services/api/src/api/v1/user/complete_onboarding.py` — functional but no name validation or double-completion guard
- Router redirect logic in `app/lib/core/router/app_router.dart` — fully functional, gates onboarding via `hasCompletedOnboarding`
- `AuthService` has `updateOnboardingState()`, `markOnboardingComplete()` — fully functional
- `ApiClient` has `completeOnboarding(name, startMethod)` — fully functional
- `OnboardingRequest` and `OnboardingResponse` schemas exist in `services/api/src/schemas/user.py`

**What ACTUALLY needs to be done:**
1. Upgrade both screens from hardcoded `AppColors.*` → theme-aware `Theme.of(context).*`
2. Add Playfair Display headings
3. Add feature introduction cards to welcome screen
4. Add missing `mounted` checks after async calls
5. Add backend name validation (matching Story 1.3 standards)
6. Add double-completion guard
7. Fix start screen to pass `defaultRecipeBookId` back to auth service
8. Write tests

**DO NOT** rewrite the router, auth service, API client methods, or schemas. They work.

### Existing Screen Issues (Fix List)

**Welcome Screen (`onboarding_welcome_screen.dart`):**
- Line 87: `CircularProgressIndicator(color: AppColors.chocolate)` → use `colorScheme.primary`
- Lines 99-103: `Icon(Icons.restaurant_menu, color: AppColors.chocolate)` → use `colorScheme.primary`
- Lines 107-110: Heading uses `Theme.of(context).textTheme.headlineLarge` but with hardcoded `AppColors.textPrimary` → use `colorScheme.onSurface` and wrap in `GoogleFonts.playfairDisplay`
- Lines 116-118: Subtitle hardcodes `AppColors.textSecondary` → use `colorScheme.onSurfaceVariant`
- Lines 124-131: Error container hardcodes `AppColors.errorLight`/`AppColors.errorDark` → use `colorScheme.errorContainer`/`colorScheme.onErrorContainer`
- Lines 138-140: "What should we call you?" hardcodes `AppColors.textPrimary`
- Line 50-52: `setState` after async with no `mounted` check
- Missing: feature introduction cards (recipe import, recipe books, cooking mode)
- Missing: value proposition subtitle

**Start Screen (`onboarding_start_screen.dart`):**
- Line 70: Back button uses `AppColors.textPrimary` → use `colorScheme.onSurface`
- Lines 82-85: Heading hardcodes `AppColors.textPrimary`
- Lines 90-93: Subtitle hardcodes `AppColors.textSecondary`
- Lines 99-106: Error container hardcodes `AppColors.errorLight`/`AppColors.errorDark`
- Line 117: Loading indicator hardcodes `AppColors.chocolate`
- Lines 172-216: `_StartMethodCard` uses 7 different `AppColors.*` references
- Lines 43-47: `mounted` check exists for `context.go()` but `setState` at lines 50-53 has no `mounted` check
- Missing: after successful onboarding, `defaultRecipeBookId` from response is not passed to `_authService.updateOnboardingState()`

**Backend (`complete_onboarding.py`):**
- No name validation — should `.strip()`, reject empty, enforce max_length=100
- No guard against double-completion — a user who somehow hits the endpoint twice would create a duplicate recipe book
- `UserResponse` construction missing `username` and `username_changed_at` fields (inconsistent with Story 1.3 schema sync)

### Architecture Compliance

- **Frontend state**: Both screens use `setState` — keep this pattern per Story 1.1/1.2/1.3 convention
- **Theme**: Replace ALL `AppColors.*` → `Theme.of(context).colorScheme.*` and `textTheme.*`
- **Typography**: `GoogleFonts.playfairDisplay` for headings (same as profile screen and other screens)
- **Error handling**: Themed error containers using `colorScheme.errorContainer`
- **`mounted` checks**: Required after all async calls before `setState` or `context.*`
- **Backend pattern**: `Endpoint` class — already followed by `CompleteOnboarding`
- **DI**: `getIt<ApiClient>()` and `getIt<AuthService>()` — already in use

### Feature Introduction Design

Per UX spec: "Onboarding is 2-3 screens max — no tutorial carousel." The welcome screen should add brief feature cards:

```
[📥 Import]   "Bring recipes from anywhere — URLs, photos, or files"
[📖 Organize]  "Recipe books keep your collection sorted your way"
[👨‍🍳 Cook]     "Hands-free cooking mode with step-by-step guidance"
```

These should be compact informational cards (not actionable), positioned between the name input and the Continue button. Use themed colors and Material icons. Keep it brief — the user's primary action here is confirming their name.

### File Structure

**Files to MODIFY:**
- `app/lib/features/onboarding/onboarding_welcome_screen.dart` — theme upgrade, add feature cards, fix mounted check
- `app/lib/features/onboarding/onboarding_start_screen.dart` — theme upgrade, fix mounted checks, pass defaultRecipeBookId
- `services/api/src/api/v1/user/complete_onboarding.py` — add name validation and double-completion guard

**Files to CREATE:**
- `app/test/onboarding_screen_test.dart` — widget tests for both onboarding screens

**Files to NOT TOUCH:**
- `app/lib/core/router/app_router.dart` — redirect logic works as-is
- `app/lib/core/services/auth_service.dart` — has all needed methods
- `app/lib/core/services/api_client.dart` — has `completeOnboarding()` method
- `services/api/src/schemas/user.py` — schemas work as-is
- `services/api/src/routers/v1/user_router.py` — route already wired
- `app/lib/shared/widgets/buttons.dart` — `PrimaryButton` and `ScaleTapButton` work as-is

### Testing Requirements

- Widget test: welcome screen renders heading and name field
- Widget test: welcome screen shows feature highlight cards (import, organize, cook)
- Widget test: start screen renders 3 option cards
- Widget test: loading/error states
- Backend test: successful onboarding
- Backend test: name validation (empty, whitespace, too long)
- Backend test: double-completion guard
- Run existing tests: `cd app && flutter test` — no regressions
- Run backend tests: `npx nx run api:test` — no regressions

### Library/Framework Requirements

No new libraries needed. All dependencies are already installed:
- `google_fonts` — for Playfair Display headings
- `go_router` — routing and navigation
- `shimmer` — if needed for loading states

### Previous Story Intelligence (Story 1.3)

From Story 1.3 implementation:
- **`mounted` checks**: Always add `if (!mounted) return;` after any async call before `setState` or `context.go()`
- **Loading state management**: Set `_isLoading = true` before async, reset to false in finally/catch
- **Error handling**: Wrap async calls in try/catch, show errors in themed `Container` with `colorScheme.errorContainer`
- **Widget tests without DI**: Cannot instantiate screens that depend on `getIt<AuthService>()` in tests. Test UI patterns directly with equivalent widget trees.
- **`GoogleFonts.config.allowRuntimeFetching = false`** needed in test `setUp()`
- **Name validation**: `.strip()` before checking, reject empty-after-strip, enforce `max_length=100` via `field_validator`
- **Theme compliance**: All colors via `Theme.of(context).colorScheme.*`, headings via `GoogleFonts.playfairDisplay`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.4] — User story and acceptance criteria
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Journey 5] — Onboarding flow: 2-3 screens max, three starting paths
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Patterns] — Endpoint class pattern, naming conventions
- [Source: _bmad-output/planning-artifacts/architecture.md#Anti-Patterns to Avoid] — No hardcoded colors, use theme system
- [Source: app/lib/features/onboarding/onboarding_welcome_screen.dart] — Current welcome screen (needs upgrade)
- [Source: app/lib/features/onboarding/onboarding_start_screen.dart] — Current start screen (needs upgrade)
- [Source: services/api/src/api/v1/user/complete_onboarding.py] — CompleteOnboarding endpoint (needs validation)
- [Source: services/api/src/schemas/user.py] — OnboardingRequest, OnboardingResponse, UserResponse schemas
- [Source: app/lib/core/router/app_router.dart] — Router with onboarding redirect logic
- [Source: app/lib/core/services/auth_service.dart] — AuthService with onboarding state management
- [Source: _bmad-output/implementation-artifacts/1-3-user-profile-management.md] — Previous story learnings

## QA Checklist

### Prerequisites
- [ ] Run `cd app && flutter pub get`
- [ ] Run `cd app && flutter test` — all tests should pass
- [ ] Backend running (`docker compose up`)

### Welcome Screen (AC #1, #4)
- [ ] First-time user is redirected to /onboarding/welcome
- [ ] Heading "Welcome to Palateful!" in Playfair Display
- [ ] Value proposition subtitle visible
- [ ] Name field pre-filled from OAuth provider name
- [ ] 3 feature highlight cards visible (Import, Organize, Cook)
- [ ] All colors are theme-aware (check both light and dark mode)
- [ ] Error state displays in themed container
- [ ] Loading state shows themed progress indicator

### Start Screen (AC #2, #4)
- [ ] Continue from welcome → start screen opens
- [ ] Heading "How would you like to start?" in Playfair Display
- [ ] 3 start method cards: Browse, Import, Scratch
- [ ] Cards use themed colors (no hardcoded AppColors)
- [ ] Back button navigates back to welcome
- [ ] Loading state during onboarding completion
- [ ] Error state in themed container

### Onboarding Completion (AC #3)
- [ ] Select any start method → onboarding completes
- [ ] User redirected to home screen
- [ ] "My Recipes" recipe book created
- [ ] Re-launching app → goes straight to home (no onboarding)
- [ ] Name persists after onboarding completion

### Backend Validation
- [ ] Empty name rejected (400)
- [ ] Whitespace-only name rejected (400)
- [ ] Name over 100 chars rejected (422)
- [ ] Double-completing onboarding returns existing data

### Design System (AC #4)
- [ ] Cream/chocolate palette in light mode
- [ ] Warm dark mode renders correctly
- [ ] Playfair Display headings on both screens
- [ ] Consistent with login, profile, and home screen styling

### Regression
- [ ] All existing Flutter tests pass
- [ ] All existing backend tests pass
- [ ] Login flow unaffected
- [ ] Profile screen unaffected
- [ ] Bottom nav tabs still work

## Review Action Items

- [x] [AI-Review][HIGH] `onboarding_screen_test.dart`: Added 3 new tests: `_continue()` empty-name validation with error display and error-clearing on input change, OAuth name pre-fill, and start method card tap triggering selection callback. Total: 9 tests.
- [x] [AI-Review][MEDIUM] `onboarding_start_screen.dart:48`: Fixed `defaultRecipeBookId` to fall back to `data?['user']?['default_recipe_book_id']` when `recipe_book` field is null (double-completion guard path).
- [x] [AI-Review][LOW] `onboarding_start_screen.dart`: Added `setState(() { _isLoading = false; })` before `context.go('/')` on success path.
- [x] [AI-Review][LOW] `onboarding_welcome_screen.dart`: Added `setState(() { _isLoading = false; })` before `return;` in the already-onboarded early-return path.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- Task 1: Replaced all hardcoded `AppColors.*` with `Theme.of(context).colorScheme.*` and `textTheme.*`. Added `GoogleFonts.playfairDisplay` heading, value proposition subtitle "Your recipes, all in one place", and 3 feature highlight cards (`_FeatureCard` widget) for Import, Organize, Cook. Added `if (!mounted) return;` after both async calls. Removed `app_colors.dart` import entirely.
- Task 2: Same theme migration for start screen. Replaced all 7+ `AppColors.*` references in `_StartMethodCard`. Added `if (!mounted) return;` after `completeOnboarding()` API call. Changed from `markOnboardingComplete()` to `updateOnboardingState(hasCompletedOnboarding: true, defaultRecipeBookId: ...)` to pass the recipe book ID from the response. Removed `app_colors.dart` import. Added `google_fonts` import.
- Task 3: Added `field_validator` for name `max_length=100` on `OnboardingRequest` schema. Added `.strip()` + empty check in endpoint `execute()`. Added double-completion guard returning existing user data without creating duplicate recipe book. Added `username` and `username_changed_at` to `UserResponse` construction.
- Task 4: Created 6 Flutter widget tests covering welcome screen (heading, name input, continue button), feature highlight cards (3 icons + titles + descriptions), start method cards (3 options with icons and chevrons), loading state, error state. Used `GoogleFonts.config.allowRuntimeFetching = false` in setUp.
- Task 5: Created 5 backend tests for `CompleteOnboarding`: success (verifies recipe book creation, user marked onboarded), empty name (400), whitespace name (400), too-long name (422), already-onboarded guard (no duplicate recipe book). All 133 backend tests pass. All 41 Flutter tests pass.

### File List

**Created:**
- `app/test/onboarding_screen_test.dart` — 6 widget tests for onboarding screens

**Modified:**
- `app/lib/features/onboarding/onboarding_welcome_screen.dart` — Theme upgrade, Playfair Display heading, feature highlight cards, mounted checks
- `app/lib/features/onboarding/onboarding_start_screen.dart` — Theme upgrade, Playfair Display heading, mounted checks, defaultRecipeBookId passback
- `services/api/src/api/v1/user/complete_onboarding.py` — Name validation, double-completion guard, UserResponse field sync
- `services/api/src/schemas/user.py` — Added field_validator for name on OnboardingRequest
- `services/api/tests/test_user.py` — Added TestCompleteOnboarding class (5 tests)
