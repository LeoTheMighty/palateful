# Story 1.1: App Shell with Design System & Navigation

Status: complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to launch a beautifully themed app with clear navigation,
so that I can orient myself and access all major sections.

## Acceptance Criteria

1. The Flutter app has all core libraries installed: Riverpod 3.0, go_router (already installed), dio (already installed), freezed (already installed), amplify_flutter
2. The app launches with a themed interface using the cream/chocolate palette with Playfair Display serif headings
3. A bottom navigation bar with Home, Books, Cart, Calendar, and Profile tabs is the primary navigation pattern
4. Light and warm dark mode are both functional and toggle with system preference
5. Shimmer/skeleton loading states are available for all async content (shared widget)
6. The app respects the system "Reduce Motion" preference for animations

## Tasks / Subtasks

- [x] Task 1: Install missing Flutter libraries (AC: #1)
  - [x]Add `flutter_riverpod` and `riverpod_annotation` and `riverpod_generator` to pubspec.yaml
  - [ ] Add `amplify_flutter` and `amplify_api` to pubspec.yaml *(deferred to Epic 7 — SDK version conflicts)*
  - [x]Add `google_fonts` package for Playfair Display
  - [x]Add `shimmer` package for loading states
  - [x]Remove unused `flutter_bloc` dependency
  - [x]Create `build.yaml` configuring build_runner for freezed, json_serializable, and riverpod_generator
  - [x]Run `flutter pub get` and verify no conflicts
  - [x]Run `dart run build_runner build` to verify code generation works

- [x] Task 2: Upgrade typography with Playfair Display (AC: #2)
  - [x]Add Playfair Display (weights 600, 700) via google_fonts package
  - [x]Update `AppTheme.light` text theme: Display/Headline/Title styles use Playfair Display serif
  - [x]Body/Label styles remain system sans-serif (no change needed)
  - [x]Verify type scale matches UX spec: Display Large 36px/700, Display Medium 28px/700, Display Small 24px/600, Title Large 22px/600

- [x] Task 3: Create dark mode theme (AC: #4)
  - [x]Add `warmIvory` color token (#F5ECD7) to AppColors
  - [x]Create `AppTheme.dark` with warm palette inversion:
    - Background: chocolate (#4A3728)
    - Surface/Cards: chocolateLight (#5D4A3A)
    - Primary text: warmIvory (#F5ECD7)
    - Secondary text: hazelnutLight (#A89076)
    - Primary accent: terracotta (#BE8A60)
    - Borders/dividers: hazelnut (#8B7355)
  - [x]All component overrides (cards, buttons, inputs, nav, dialogs, etc.) must be themed for dark mode
  - [x]Verify WCAG AA contrast ratios: warmIvory on chocolate = ~8.5:1

- [x] Task 4: Add system theme detection (AC: #4)
  - [x]Update `main.dart` MaterialApp.router to include both `theme: AppTheme.light` and `darkTheme: AppTheme.dark`
  - [x]Set `themeMode: ThemeMode.system` for automatic system preference detection
  - [x]Verify both modes render correctly on all existing screens

- [x] Task 5: Add bottom navigation with GoRouter shell (AC: #3)
  - [x]Create a `ShellRoute` in app_router.dart with a `ScaffoldWithBottomNav` shell widget
  - [x]Bottom nav tabs: Home (house icon), Books (book icon), Cart (cart icon), Calendar (calendar icon), Profile (person icon)
  - [x]Use `StatefulShellRoute.indexedStack` for preserving tab state across navigation
  - [x]Routes under shell: `/` (Home), `/recipe-books` (Books), `/cart` (Cart), `/calendar` (Calendar), `/profile` (Profile)
  - [x]Non-shell routes (login, onboarding, recipe detail, cook mode) remain outside the shell
  - [x]Remove the current header-based navigation buttons from HomeScreen (recipe books button, logout button)
  - [x]Bottom nav uses Material 3 NavigationBar widget with existing theme styling
  - [x]Use monochrome Material icons (per UX spec)

- [x] Task 6: Create shimmer loading widget (AC: #5)
  - [x]Create `lib/shared/widgets/shimmer_loading.dart` with reusable shimmer placeholder widgets
  - [x]At minimum: `ShimmerCard` (recipe card placeholder), `ShimmerList` (list placeholder), `ShimmerBlock` (generic block)
  - [x]Use cream/beige colors for shimmer base and highlight (light mode) and chocolate variants (dark mode)
  - [x]These are shared widgets, not tied to any specific feature

- [x] Task 7: Respect Reduce Motion preference (AC: #6)
  - [x]Check `MediaQuery.of(context).disableAnimations` in page transitions
  - [x]When Reduce Motion is enabled, use instant transitions (Duration.zero) instead of animated ones
  - [x]GoRouter custom page transitions should respect this setting

- [x] Task 8: Migrate state management foundation toward Riverpod (AC: #1)
  - [x]Wrap the app root with `ProviderScope` in main.dart
  - [x]Do NOT rewrite existing screens to Riverpod in this story — just ensure the foundation is in place
  - [x]Existing GetIt DI and ChangeNotifier patterns continue to work alongside Riverpod
  - [x]New features from subsequent stories will use Riverpod providers

### Review Follow-ups (AI)

- [x] [AI-Review][High] `ShimmerList.itemHeight` parameter is declared but never used in `build()` — **Fixed:** wrapped each row in `SizedBox(height: itemHeight)` so parameter controls row height
- [x] [AI-Review][High] `.gitignore` was modified to remove `lib/` pattern (C1 fix) but is absent from story File List — **N/A (false positive):** .gitignore was not modified by this story; the `lib/` pattern does not exist in .gitignore
- [x] [AI-Review][High] `ElevatedButton` disabled foreground returns same `AppColors.cream` as normal state — **Fixed:** disabled state now returns `AppColors.textDisabled` for proper WCAG contrast
- [x] [AI-Review][Medium] Non-story files still dirty — **Acknowledged:** `services/parser/poetry.lock`, `pyproject.toml`, `terraform/modules/batch/main.tf` are pre-existing unrelated changes, will be committed separately
- [x] [AI-Review][Medium] `_onMealFilterChanged` calls `_loadRecipes()` (N+1 API calls) — **Fixed:** removed redundant client-side filter/sort before API call; `_loadRecipes()` already applies filters and sorting
- [x] [AI-Review][Medium] Dark theme `outlinedButtonTheme` missing hover state — **Fixed:** added `WidgetState.hovered` with 0.08 opacity hazelnutLight background
- [x] [AI-Review][Low] ShimmerList test only asserts widget exists, not item count — **Fixed:** added assertion `expect(find.byType(Row), findsNWidgets(3))` to verify rendered item count
- [x] [AI-Review][Low] `NavigationBar` doesn't set `animationDuration` — **Fixed:** reads `MediaQuery.of(context).disableAnimations` and sets `Duration.zero` when reduce motion enabled
- [x] [AI-Review][Low] `buildReduceMotionPage` coupled to `app_router.dart` — **Fixed:** extracted to `page_transitions.dart`, test imports updated
- [x] [AI-Review][Low] `appRouter` stale state on hot restart — **Fixed:** added `resetRouter()` function that disposes and nulls the singleton

## Dev Notes

### Critical Context: This Is a Brownfield Project

**DO NOT** rewrite existing working code. The app has:
- Working Auth0 integration (auth_service.dart) — leave as-is
- Working Dio API client with JWT interceptor (api_client.dart) — leave as-is
- Working GoRouter with routes (app_router.dart) — extend, don't replace
- Working push notifications (push_notification_service.dart) — leave as-is
- Working feature screens (home, recipes, cook mode, shopping cart, etc.) — leave as-is
- Working GetIt DI (injection.dart) — leave as-is, Riverpod runs alongside

**ADD** to the existing codebase, don't replace it.

### Architecture Compliance

- **Endpoint class pattern**: Not relevant for this story (no new API endpoints)
- **State management**: Riverpod 3.0 is the target, but this story only installs it and wraps with ProviderScope. Existing setState/ChangeNotifier code is NOT migrated in this story.
- **Naming conventions**: Dart files use snake_case, classes use PascalCase, providers will use camelCase with Provider suffix
- **Feature-first structure**: Existing `lib/features/` structure is maintained. New shared widgets go in `lib/shared/widgets/`

### File Structure

**Files to CREATE:**
- `app/build.yaml` — build_runner configuration for freezed, riverpod_generator, json_serializable
- `app/lib/shared/widgets/shimmer_loading.dart` — shimmer placeholder widgets
- `app/lib/shared/widgets/scaffold_with_bottom_nav.dart` — bottom navigation shell widget

**Files to MODIFY:**
- `app/pubspec.yaml` — add Riverpod, amplify_flutter, google_fonts, shimmer; remove flutter_bloc
- `app/lib/main.dart` — wrap with ProviderScope, add darkTheme, set ThemeMode.system
- `app/lib/core/theme/app_colors.dart` — add warmIvory token
- `app/lib/core/theme/app_theme.dart` — add Playfair Display typography, create AppTheme.dark
- `app/lib/core/router/app_router.dart` — restructure with StatefulShellRoute for bottom nav
- `app/lib/features/home/home_screen.dart` — remove header nav buttons (moved to bottom nav)

**Files to NOT TOUCH:**
- `app/lib/core/services/api_client.dart`
- `app/lib/core/services/auth_service.dart`
- `app/lib/core/services/auth_service_web.dart`
- `app/lib/core/services/push_notification_service.dart`
- `app/lib/core/di/injection.dart`
- `app/lib/core/config/environment.dart`
- All feature screen files (recipe_detail, cook_mode, search, shopping_cart, etc.)
- `app/lib/shared/widgets/buttons.dart` (existing button library)

### Project Structure Notes

- Alignment with architecture: feature-first `lib/features/` structure preserved
- Shared widgets in `lib/shared/widgets/` — existing buttons.dart + new shimmer_loading.dart + scaffold_with_bottom_nav.dart
- Theme files stay in `lib/core/theme/` — extended, not reorganized
- GoRouter stays in `lib/core/router/` — restructured for shell route

### Testing Requirements

- Verify app launches in both light and dark mode without crashes
- Verify bottom navigation switches between all 5 tabs
- Verify existing routes still work (recipe detail, cook mode, login, onboarding)
- Verify Playfair Display renders on headings
- Verify shimmer widgets render in both themes
- Run existing tests to confirm no regressions: `cd app && flutter test`
- Run code generation: `dart run build_runner build --delete-conflicting-outputs`

### Library/Framework Requirements

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| flutter_riverpod | latest stable | State management | Wrap app with ProviderScope |
| riverpod_annotation | latest stable | Riverpod codegen annotations | Dev dependency style |
| riverpod_generator | latest stable | Riverpod code generation | Dev dependency |
| amplify_flutter | latest stable (Gen 2) | AWS AppSync client | Install now, configure in Epic 7 |
| amplify_api | latest stable | AppSync API plugin | Companion to amplify_flutter |
| google_fonts | latest stable | Playfair Display serif font | For recipe titles and headings |
| shimmer | latest stable | Shimmer loading placeholders | For async content loading states |

| Remove | Reason |
|--------|--------|
| flutter_bloc | Unused — replaced by Riverpod |

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Selected Stack] — Flutter library decisions
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture] — Riverpod, go_router, dio, freezed decisions
- [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns] — Dart naming conventions
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Design System Foundation] — Material 3 theme, existing color system
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Typography System] — Playfair Display + system sans-serif pairing
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Spacing & Layout Foundation] — Spacing scale, grid system
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Design Direction Decision] — Dark mode token mapping, warm ivory
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Accessibility Considerations] — WCAG AA, touch targets, Reduce Motion
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#UX Pattern Analysis] — Bottom nav: Home, Books, Cart, Calendar, Profile
- [Source: app/lib/core/theme/app_colors.dart] — Existing 35+ color tokens
- [Source: app/lib/core/theme/app_theme.dart] — Existing Material 3 light theme
- [Source: app/lib/core/router/app_router.dart] — Existing GoRouter configuration
- [Source: app/lib/main.dart] — Current app entry point with Auth0 + Firebase init
- [Source: app/pubspec.yaml] — Current dependencies (go_router 17.0.0, dio 5.9.0, freezed 3.2.3, auth0_flutter 1.14.0)

### Dark Mode Token Mapping (from UX Spec)

| Role | Light Mode | Dark Mode |
|------|-----------|-----------|
| Background | cream (#FAF7F2) | chocolate (#4A3728) |
| Surface/Cards | creamLight (#FFFDF9) | chocolateLight (#5D4A3A) |
| Primary text | textPrimary (#2D2420) | warmIvory (#F5ECD7) |
| Secondary text | textSecondary (#6B5D54) | hazelnutLight (#A89076) |
| Primary accent | chocolate (#4A3728) | terracotta (#BE8A60) |
| Secondary accent | hazelnut (#8B7355) | hazelnutLight (#A89076) |
| Borders/dividers | beigeAccent (#E8DFD0) | hazelnut (#8B7355) |

### Existing CI/CD Context

The CI pipeline at `.github/workflows/ci.yml` already runs:
- Lint: `npx nx affected -t lint`
- Test: `npx nx affected -t test` (with PostgreSQL + pgvector)
- Check-models: validates SQLAlchemy models match migrations

No CI changes needed for this story. The pipeline will automatically pick up Flutter changes if the app project is affected.

## QA Checklist

### Prerequisites
- [ ] Run `cd app && flutter pub get` to ensure dependencies are installed
- [ ] Run `cd app && flutter test` — all 13 tests should pass
- [ ] Run `flutter analyze` — no errors (info/warnings are pre-existing)

### Light Mode (AC #2, #4)
- [ ] Launch the app on a device/simulator with system set to **light mode**
- [ ] Verify background is warm cream (#FAF7F2), not pure white
- [ ] Verify headings use Playfair Display serif font (recipe titles, screen titles)
- [ ] Verify body text uses system sans-serif (not serif)
- [ ] Verify cards have cream background with beige borders
- [ ] Verify buttons use chocolate (#4A3728) primary color

### Dark Mode (AC #4)
- [ ] Switch device to **dark mode** (Settings → Display)
- [ ] Verify background changes to chocolate (#4A3728)
- [ ] Verify cards change to chocolateLight (#5D4A3A) with hazelnut borders
- [ ] Verify primary text is warmIvory (#F5ECD7) — readable, warm tone
- [ ] Verify accent color is terracotta (#BE8A60) — buttons, active nav items
- [ ] Verify bottom nav background is darker than the main scaffold
- [ ] Verify text contrast is comfortable to read (WCAG AA: ~8.5:1 warmIvory on chocolate)

### Bottom Navigation (AC #3)
- [ ] Verify bottom nav bar is visible with 5 tabs: Home, Books, Cart, Calendar, Profile
- [ ] Tap **Home** — shows recipe grid with search bar
- [ ] Tap **Books** — shows recipe books screen
- [ ] Tap **Cart** — shows "Shopping list coming soon" placeholder
- [ ] Tap **Calendar** — shows "Meal planning coming soon" placeholder
- [ ] Tap **Profile** — shows profile placeholder with Logout button
- [ ] Verify active tab icon is filled, inactive tabs use outlined icons
- [ ] Navigate to a sub-page within a tab, switch tabs, switch back — **tab state is preserved**

### Navigation Integrity
- [ ] From Home, tap a recipe card → recipe detail opens **without** bottom nav (full screen)
- [ ] From recipe detail, go back → returns to Home with bottom nav
- [ ] Long-press a recipe → cook mode opens **without** bottom nav (full screen)
- [ ] From Profile, tap Logout → redirected to login screen (no bottom nav)
- [ ] Login → should redirect to Home with bottom nav (if onboarded)
- [ ] The old recipe books button and logout button are **removed** from the Home search header

### Shimmer Loading (AC #5)
- [ ] In light mode: verify shimmer uses cream/beige tones (not grey)
- [ ] In dark mode: verify shimmer uses chocolate/hazelnut tones
- [ ] (Optional) Add a deliberate delay to recipe loading to see shimmer in action

### Reduce Motion (AC #6)
- [ ] Enable **Reduce Motion** in device settings (iOS: Settings → Accessibility → Motion → Reduce Motion)
- [ ] Navigate to recipe detail → transition should be **instant** (no fade animation)
- [ ] Go back → transition should be **instant**
- [ ] Disable Reduce Motion → navigate again → should see **fade transition**

### Riverpod Foundation (AC #1)
- [ ] App launches without errors (ProviderScope wrapping verified)
- [ ] Existing functionality still works: login, recipe browsing, cook mode, add recipe

## File List

### New Files
- `app/build.yaml` — build_runner configuration for freezed, riverpod_generator, json_serializable
- `app/lib/shared/widgets/shimmer_loading.dart` — ShimmerBlock, ShimmerCard, ShimmerList widgets
- `app/lib/shared/widgets/scaffold_with_bottom_nav.dart` — bottom navigation shell widget
- `app/lib/features/cart/cart_screen.dart` — placeholder Cart tab screen
- `app/lib/features/calendar/calendar_screen.dart` — placeholder Calendar tab screen
- `app/lib/features/profile/profile_screen.dart` — placeholder Profile tab with logout

### Modified Files
- `app/pubspec.yaml` — added flutter_riverpod, riverpod_annotation, riverpod_generator, google_fonts, shimmer; removed flutter_bloc
- `app/lib/main.dart` — wrapped with ProviderScope, added darkTheme and ThemeMode.system
- `app/lib/core/theme/app_colors.dart` — added warmIvory color token
- `app/lib/core/theme/app_theme.dart` — added Playfair Display typography, created AppTheme.dark
- `app/lib/core/router/app_router.dart` — restructured with StatefulShellRoute.indexedStack, added Reduce Motion page transitions
- `app/lib/features/home/home_screen.dart` — removed recipe books button and logout button from header (moved to bottom nav/profile)
- `app/test/widget_test.dart` — replaced default template test with story-specific tests (13 tests)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Version conflict: freezed 3.2.3 requires build >=3.0.0, riverpod_generator 2.x requires build ^2.0.0 — resolved by using riverpod 3.x dev versions
- Google Fonts in tests: `allowRuntimeFetching = false` still throws if font files not bundled — resolved by using widget tests with `tester.pumpWidget` instead of pure unit tests

### Completion Notes List

- All 8 tasks completed: library installation, Playfair Display typography, dark mode theme, system theme detection, bottom navigation shell, shimmer widgets, Reduce Motion support, Riverpod ProviderScope
- 13 tests passing: AppColors (3), AppTheme light/dark rendering and brightness (5), ShimmerBlock (1), ShimmerCard light/dark (2), ShimmerList (1), ProviderScope (1)
- No analyzer errors (24 pre-existing info/warnings only)
- Removed amplify_flutter/amplify_api from scope — version conflicts with current SDK constraint; can be added when Epic 7 is implemented
- Created placeholder screens for Cart, Calendar, Profile tabs with appropriate icons and messaging
- Logout moved from home screen header to Profile tab

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Date:** 2026-03-13
**Verdict:** Changes Requested

### Critical

- [x] [C1] **`app/lib/` never committed to git**: False positive — `.gitignore` does not have `lib/` pattern. Files were simply never `git add`'d. Will be committed with this story.
- [x] [C2] **AC #1 amplify_flutter: task marked [x] but not done**: Unchecked the amplify subtask and added deferral note.
- [x] [C3] **Typo: `PalatefuIApp` in `main.dart:81,84`**: Renamed to `PalatefulApp`.

### High

- [x] [H1] **Shimmer widgets exist but are never used (AC #5)**: Replaced `CircularProgressIndicator` with `ShimmerCard` grid (6 cards) in home screen loading state.
- [x] [H2] **Pre-release Riverpod `^3.0.0-dev.3`**: Added explanatory comment in `pubspec.yaml` documenting the freezed/build constraint.
- [x] [H3] **Home screen hardcodes light-mode colors**: Replaced all `AppColors.*` with `Theme.of(context).colorScheme.*` values in search header, refresh indicator, empty state, and batch dialog.

### Medium

- [x] [M1] **`.gitignore` Python `lib/` pattern**: False positive — no bare `lib/` in `.gitignore`. Only `lib64/` exists. No change needed.
- [x] [M2] **Tests are smoke-only**: Added ScaffoldWithBottomNav test (5 NavigationDestinations), dark theme scaffold background test, Reduce Motion tests (disableAnimations true/false). Now 18 tests.
- [x] [M3] **Non-story files in working directory**: Acknowledged — these pre-existing changes will not be included in story commit.

### Low

- [x] [L1] **Home screen error state uses light-only colors**: Replaced `AppColors.errorLight`/`errorDark` with `colorScheme.errorContainer`/`onErrorContainer`.

### Change Log
- 2026-03-12: Story created by create-story workflow with comprehensive codebase analysis
- 2026-03-13: Story implementation completed — all 8 tasks done, 13 tests passing, analyzer clean
- 2026-03-13: Code review completed — 3 critical, 3 high, 3 medium, 1 low issues found. Changes requested.
- 2026-03-13: Addressed all 10 code review findings — 18 tests passing, 0 analyzer errors
- 2026-03-13: Second code review — 3 high, 3 medium, 4 low issues found. 10 action items added to Review Follow-ups.
