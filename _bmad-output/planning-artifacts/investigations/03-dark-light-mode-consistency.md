# Investigation: Dark Mode / Light Mode Consistency

**Date:** 2026-03-22
**Status:** Complete
**Severity:** Medium-High (user-facing visual inconsistency across the entire app)

---

## Executive Summary

The Palateful Flutter app has a **well-structured theme foundation** with both light and dark `ThemeData` definitions and `ThemeMode.system` set in `MaterialApp.router`. However, the app suffers from **pervasive hardcoded color usage** that bypasses the theme system, making dark mode visually broken or inconsistent on roughly half of all screens. There are **339 direct `AppColors.*` references across 21 feature files** that do not adapt to dark mode, while only **32 files use `Theme.of(context)`** correctly. Additionally, there is **no in-app theme toggle** and **no persistence of theme preference** -- the app solely follows the device system setting with no user override.

The core problem is architectural: `AppColors` is a static class of light-mode-optimized constants. Any widget that references `AppColors.textPrimary` (a dark brown `#2D2420`) will show dark-on-dark text in dark mode. The dark theme in `app_theme.dart` is comprehensive at the widget-theme level, but screens that bypass `Theme.of(context)` in favor of `AppColors.*` constants completely ignore it.

---

## Current State Analysis

### Theme Infrastructure

**File:** `/Users/leonidbelyi/personal/palateful/app/lib/core/theme/app_theme.dart`

The app defines two complete `ThemeData` objects:
- `AppTheme.light` -- cream/chocolate warm palette (~625 lines)
- `AppTheme.dark` -- warm dark mode with chocolate backgrounds and terracotta accents (~570 lines)

Both themes configure: ColorScheme, AppBar, Cards, Elevated/Outlined/Text buttons, FAB, IconButton, InputDecoration, Chips, ListTile, Divider, Dialog, BottomSheet, SnackBar, ProgressIndicator, Switch, Checkbox, Radio, NavigationBar, TabBar, and full TextTheme (Playfair Display headers, system body).

**File:** `/Users/leonidbelyi/personal/palateful/app/lib/main.dart` (line 196-204)

```dart
return MaterialApp.router(
  title: 'Palateful',
  theme: AppTheme.light,
  darkTheme: AppTheme.dark,
  themeMode: ThemeMode.system,  // follows device setting
  routerConfig: appRouter,
);
```

This is correct -- the app declares both themes and follows the system preference. However, `ThemeMode.system` is hardcoded with no way for the user to override it.

**File:** `/Users/leonidbelyi/personal/palateful/app/lib/core/theme/app_colors.dart`

This is a **static constant class** with ~50 named colors. All values are optimized for light mode (e.g., `textPrimary = Color(0xFF2D2420)` is a dark brown). The only dark-mode-aware color is `warmIvory`, which is explicitly noted as "for dark mode primary text." The class has no concept of light vs. dark variants for any other color.

### Theme Propagation Pattern

The app uses two conflicting patterns for color access:

1. **Theme-aware (correct):** `Theme.of(context).colorScheme.primary`, `textTheme.bodyLarge` -- 790 occurrences across 32 files
2. **Static/hardcoded (breaks dark mode):** `AppColors.textPrimary`, `AppColors.beige`, `Colors.white` -- 339 `AppColors` occurrences across 21 files, plus additional `Colors.*` usages

### State Management for Theme

**There is none.** No `ThemeProvider`, no `Riverpod` provider for theme state, no `SharedPreferences` persistence, no settings toggle. The `themeMode` is a compile-time constant `ThemeMode.system`.

---

## Screen-by-Screen Theme Audit

### Screens Using Theme Correctly (theme-aware)

These screens primarily use `Theme.of(context).colorScheme` and `textTheme`:

| Screen | File | Notes |
|--------|------|-------|
| Login | `features/auth/login_screen.dart` | Mostly theme-aware; Google/Apple button colors are intentionally brand-specific (acceptable) |
| Onboarding Welcome | `features/onboarding/onboarding_welcome_screen.dart` | Fully theme-aware via `colorScheme` and `textTheme` |
| Onboarding Start | `features/onboarding/onboarding_start_screen.dart` | Fully theme-aware |
| Profile | `features/profile/profile_screen.dart` | Mostly theme-aware; shimmer loading uses `Colors.white` (minor issue, lines 496-502) |
| Chat | `features/chat/chat_screen.dart` | Fully theme-aware |
| Message Bubble | `features/chat/widgets/message_bubble.dart` | Fully theme-aware via `colorScheme` |
| Empty State | `shared/widgets/empty_state.dart` | Fully theme-aware |
| Search | `features/search/search_screen.dart` | Mostly theme-aware |
| Invitations | `features/invitations/invitations_screen.dart` | Theme-aware |
| Notification Preferences | `features/profile/notification_preferences_screen.dart` | Theme-aware |
| Recipe Books | `features/recipe_books/recipe_books_screen.dart` | Theme-aware |

### Screens With Significant Dark Mode Issues (hardcoded AppColors)

| Screen | File | `AppColors` Count | Key Issues |
|--------|------|-------------------|------------|
| **Calendar** | `features/calendar/calendar_screen.dart` | 23 | Hardcoded `AppColors.cream` as scaffold/appbar background, `AppColors.textPrimary` for text, `AppColors.warmWhite`/`AppColors.warmIvory` for day containers, `Colors.white` for today badge text. Entire screen will look wrong in dark mode. |
| **Recipe Card** | `features/home/widgets/recipe_card.dart` | 17 | `AppColors.textPrimary`, `AppColors.textTertiary`, `AppColors.hazelnut`, `AppColors.beige` throughout. `Colors.red`/`Colors.white` for favorite heart overlay. Cards will show light-mode colors on dark backgrounds. |
| **Cook Mode** | `features/recipes/cook_mode/cook_mode_screen.dart` | 52 | Intentionally dark-themed (chocolate background). Uses `AppColors.chocolate`, `AppColors.warmIvory`, `AppColors.chocolateDark` extensively. This is designed to always be dark, which is acceptable for a cooking UI but creates a jarring transition from other screens. |
| **Shopping List** | `features/shopping_cart/screens/shopping_list_screen.dart` | 22 | Uses `AppColors.*` for backgrounds, text colors, borders. |
| **Shopping List Item Tile** | `features/shopping_cart/widgets/shopping_list_item_tile.dart` | 11 | `AppColors.textPrimary`, `AppColors.textSecondary`, `AppColors.border`, `Colors.white` for checkmark. |
| **Celebration Overlay** | `features/shopping_cart/widgets/celebration_overlay.dart` | 18 | `AppColors.warmWhite`, `AppColors.textPrimary`, `Colors.white`. |
| **Floating Cart Widget** | `features/shopping_cart/widgets/floating_cart_widget.dart` | 13 | `AppColors.cardBackground`, `AppColors.textPrimary`, `Colors.white`. |
| **Member Presence** | `features/shopping_cart/widgets/member_presence.dart` | 12 | `Colors.white` for borders/text, `AppColors.beige`. |
| **Urgency Badge** | `features/shopping_cart/widgets/urgency_badge.dart` | 12 | Uses light-mode semantic colors: `AppColors.errorLight`, `AppColors.warningLight`, `AppColors.infoLight`, etc. |
| **Plan Meal Sheet** | `features/calendar/widgets/plan_meal_sheet.dart` | 14 | `AppColors.chocolate`, `AppColors.beige`, `AppColors.textPrimary`, `Colors.white`. |
| **Sort Chips** | `features/home/widgets/sort_chips.dart` | 3 | `AppColors.chocolate`, `AppColors.textTertiary`. |
| **Meal Filter Bar** | `features/home/widgets/meal_filter_bar.dart` | 2 | Hardcoded `AppColors` for filter states. |
| **Batch Import Status** | `features/home/widgets/batch_import_status_widget.dart` | 15 | `AppColors.beige`, `AppColors.textPrimary`, `Colors.white`. |
| **Step Navigator** | `features/recipes/cook_mode/widgets/step_navigator.dart` | 24 | `AppColors.warmWhite`, `AppColors.cream`, `AppColors.beige`. Part of cook mode's always-dark design. |
| **Ingredient Strip** | `features/recipes/cook_mode/widgets/ingredient_strip.dart` | 12 | Part of cook mode. |
| **Post Cook Feedback** | `features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart` | 13 | Part of cook mode. |
| **Cook Mode Chat** | `features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` | 23 | Part of cook mode. |
| **Batch Job Result Sheet** | `features/home/widgets/batch_job_result_sheet.dart` | 9 | Hardcoded light colors. |
| **Add Recipe Sheet** | `features/recipes/add_recipe/add_recipe_sheet.dart` | 6 | Minor hardcoded colors. |
| **File Import** | `features/recipes/add_recipe/file_import_screen.dart` | 10 | Hardcoded colors. |
| **Photo Capture** | `features/recipes/add_recipe/photo_capture_screen.dart` | 28 | Heavily hardcoded for camera UI. |

### Shared Widgets With Issues

| Widget | File | Issue |
|--------|------|-------|
| **PrimaryButton** | `shared/widgets/buttons.dart` | Loading spinner uses `AppColors.cream` -- fine for light, wrong for dark |
| **SecondaryButton** | `shared/widgets/buttons.dart` | Loading spinner uses `AppColors.hazelnut` -- acceptable |
| **SoftButton** | `shared/widgets/buttons.dart` | Default color `AppColors.chocolate`, background opacity calc uses `AppColors.withOpacity` |
| **CircleIconButton** | `shared/widgets/buttons.dart` | Default icon color `AppColors.textPrimary` (dark brown), splash uses `AppColors` |
| **PillButton** | `shared/widgets/buttons.dart` | `AppColors.chocolate`/`AppColors.beige`/`AppColors.cream`/`AppColors.textPrimary` throughout |
| **DangerButton** | `shared/widgets/buttons.dart` | `AppColors.error`/`AppColors.cream` -- light-mode optimized |
| **SuccessButton** | `shared/widgets/buttons.dart` | `AppColors.success`/`AppColors.cream` -- light-mode optimized |
| **ShimmerLoading** | `shared/widgets/shimmer_loading.dart` | Already dark-mode-aware (checks `Theme.of(context).brightness`) -- a good example |

### Screens With Minor Issues

| Screen | File | Issue |
|--------|------|-------|
| Recipe Detail | `features/recipes/recipe_detail_screen.dart` | `Colors.grey` for broken image icon, `Colors.red` for favorite heart |
| Public Recipe | `features/recipes/public_recipe_screen.dart` | `Colors.grey` for broken image |
| Version Diff | `features/recipes/recipe_version_diff_screen.dart` | `Colors.green`, `Colors.amber` for diff highlighting -- should use theme-aware semantic colors |
| Recipe Book Detail | `features/recipe_books/recipe_book_detail_screen.dart` | `Colors.green`/`Colors.grey` for WebSocket status indicator |

---

## Research Findings: Flutter Theming Best Practices

### 1. Single Source of Truth via ColorScheme

Flutter Material 3 best practice is to derive all colors from `Theme.of(context).colorScheme`. The `ColorScheme` provides semantic color slots (primary, secondary, surface, error, etc.) that automatically switch between light and dark variants when the theme changes.

**Anti-pattern (current state):**
```dart
color: AppColors.textPrimary  // Always dark brown, ignores theme
```

**Best practice:**
```dart
color: Theme.of(context).colorScheme.onSurface  // Adapts to theme
```

### 2. Extension Methods for Custom Semantic Colors

For colors that don't map to standard Material slots (urgency colors, cooking-specific colors, brand accent colors), Flutter recommends using `ThemeExtension<T>`:

```dart
class AppColorExtension extends ThemeExtension<AppColorExtension> {
  final Color urgentBg;
  final Color urgentText;
  // ... etc

  @override
  ThemeExtension<AppColorExtension> copyWith({...}) => ...;

  @override
  ThemeExtension<AppColorExtension> lerp(...) => ...;
}
```

This integrates with `ThemeData.extensions` and provides type-safe access via `Theme.of(context).extension<AppColorExtension>()`.

### 3. Theme Mode Management

The recommended approach combines:
- **System default**: Follow device settings by default
- **User override**: Allow explicit light/dark/system choice in settings
- **Persistence**: Store preference in `SharedPreferences` (or similar)
- **State management**: Use Riverpod (already in the project) to manage `ThemeMode`

Example architecture:
```dart
final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier();
});
```

### 4. Cook Mode as a Deliberate Exception

A "dark cooking mode" is a valid UX pattern (reduces eye strain in kitchen environments). This should be implemented as an intentional theme override within the cook mode screen, not as hardcoded colors. The correct approach uses `Theme(data: ..., child: ...)` wrapper to locally override the theme for the cook mode subtree.

---

## Gap Analysis

### Gap 1: No Theme State Management
- **Current:** `ThemeMode.system` is hardcoded in `MaterialApp.router`
- **Expected:** A Riverpod-managed `ThemeMode` that can be overridden by the user
- **Impact:** Users cannot choose light/dark mode independent of device setting

### Gap 2: No Theme Toggle in Settings
- **Current:** Profile screen has no theme/appearance section
- **Expected:** A "Theme" or "Appearance" option in Profile settings with System/Light/Dark choices
- **Impact:** Users have no control; the pain point in the bug report

### Gap 3: No Theme Preference Persistence
- **Current:** No `SharedPreferences` storage for theme choice
- **Expected:** Theme preference survives app restart
- **Impact:** Even if a toggle were added, it would reset on restart

### Gap 4: Pervasive Hardcoded Colors (339 occurrences)
- **Current:** 21 feature files reference `AppColors.*` directly instead of `Theme.of(context)`
- **Expected:** All color references go through the theme system
- **Impact:** Dark mode shows light-colored text on dark backgrounds (unreadable), light-colored containers that clash, etc.

### Gap 5: Static Color Palette Not Theme-Aware
- **Current:** `AppColors` is a single set of constants optimized for light mode
- **Expected:** Either (a) all colors accessed via `ColorScheme`/`ThemeExtension`, or (b) `AppColors` provides `light`/`dark` variants
- **Impact:** Foundation problem that causes Gap 4

### Gap 6: No Custom ThemeExtension for App-Specific Colors
- **Current:** Semantic colors (urgency levels, diff highlighting, cooking states) are hardcoded
- **Expected:** `ThemeExtension` with light/dark variants for all custom semantic colors
- **Impact:** Diff screen, urgency badges, celebration overlay, etc. look wrong in dark mode

### Gap 7: Shared Button Widgets Use Static Colors
- **Current:** `PrimaryButton`, `PillButton`, `DangerButton`, etc. reference `AppColors.*`
- **Expected:** Buttons derive colors from `Theme.of(context)` or use default Material theme styling
- **Impact:** Every screen using shared buttons has theme inconsistency

---

## Recommendations

### Phase 1: Theme State Management (Foundation)

1. **Create a `ThemeModeProvider`** using Riverpod `StateNotifierProvider`
   - Default to `ThemeMode.system`
   - Support `ThemeMode.light`, `ThemeMode.dark`, `ThemeMode.system`
   - Persist choice to `SharedPreferences` on change
   - Load saved preference on app startup

2. **Wire provider into `MaterialApp.router`**
   - Replace hardcoded `themeMode: ThemeMode.system` with `themeMode: ref.watch(themeModeProvider)`
   - Wrap `PalatefulApp` with `ConsumerWidget` (it already uses `ProviderScope`)

3. **Add theme toggle to Profile screen**
   - Add an "Appearance" section between "Settings" and "Account"
   - Three options: System (default), Light, Dark
   - Use a segmented control or radio list

### Phase 2: Create ThemeExtension for Custom Colors

1. **Define `PalatefulColors extends ThemeExtension<PalatefulColors>`** with:
   - Text hierarchy: `textPrimary`, `textSecondary`, `textTertiary`, `textDisabled`
   - Backgrounds: `cardBackground`, `inputBackground`, `navBackground`
   - Semantic: `success`/`successLight`, `warning`/`warningLight`, `error`/`errorLight`, `info`/`infoLight`
   - Urgency: `urgentBg`, `urgentText`, etc.
   - Diff: `addedBg`, `removedBg`, `changedBg`, `addedText`, `removedText`, `changedText`

2. **Add light and dark instances** to `AppTheme.light.extensions` and `AppTheme.dark.extensions`

3. **Create a helper** (e.g., `context.appColors`) for convenient access

### Phase 3: Migrate Screens to Theme-Aware Colors

Priority order (by user visibility and severity):

1. **Calendar Screen** -- fully visible main tab, completely broken in dark mode
2. **Recipe Card** -- shown on home screen, high visibility
3. **Shopping List Screen + Item Tile** -- main tab content
4. **Floating Cart Widget** -- overlay visible on multiple screens
5. **Plan Meal Sheet** -- frequently used bottom sheet
6. **Shared Buttons** (`PillButton`, `CircleIconButton`, `DangerButton`, `SuccessButton`)
7. **Sort Chips + Meal Filter Bar** -- home screen controls
8. **Batch Import Status** -- contextual widget
9. **Celebration Overlay + Member Presence** -- shopping cart sub-widgets
10. **Urgency Badge** -- shopping cart detail
11. **Version Diff Screen** -- lower frequency usage
12. **Add Recipe flows** (sheet, file import, photo capture)

For each screen:
- Replace `AppColors.textPrimary` with `colorScheme.onSurface`
- Replace `AppColors.textSecondary` with `colorScheme.onSurfaceVariant`
- Replace `AppColors.cream` / `AppColors.warmWhite` with `colorScheme.surface`
- Replace `AppColors.beige` with `colorScheme.surfaceContainerHighest`
- Replace `AppColors.chocolate` with `colorScheme.primary`
- Replace `AppColors.border` / `AppColors.divider` with `colorScheme.outline` / `colorScheme.outlineVariant`
- Replace `Colors.white` with `colorScheme.surface` or `colorScheme.onPrimary`
- Replace `Colors.red` (favorite) with `colorScheme.error` or a dedicated semantic color

### Phase 4: Cook Mode as Intentional Override

- Wrap cook mode screen tree with `Theme(data: AppTheme.dark.copyWith(...), child: ...)` to force dark theme regardless of app setting
- This preserves the always-dark cooking UX while making it architecturally clean
- Remove direct `AppColors.*` references and use the local dark theme instead

---

## Technical Considerations

1. **Riverpod is already a dependency** -- no new packages needed for state management.
2. **SharedPreferences is already a dependency** (used by `RecipeCacheService`) -- no new packages needed for persistence.
3. **ThemeExtension requires `lerp` implementation** for smooth theme transitions. Material Color values can use `Color.lerp`.
4. **Migration can be incremental** -- screens can be updated one at a time without breaking anything. The `ThemeMode` provider and profile toggle can ship first, then screen migrations follow.
5. **AppColors can be kept** as a reference palette, but widgets should not reference it directly. Instead, the palette feeds into `ColorScheme` and `ThemeExtension` definitions.
6. **Testing consideration:** Dark mode screenshots should be added to any visual regression testing. The `ShimmerLoading` widget already demonstrates the correct pattern (`Theme.of(context).brightness == Brightness.dark`).

---

## Estimated Complexity

| Phase | Effort | Dependencies |
|-------|--------|-------------|
| Phase 1: Theme State Management + Profile Toggle | **Small** (1-2 hours) | None |
| Phase 2: ThemeExtension Definition | **Small-Medium** (2-3 hours) | Phase 1 |
| Phase 3: Migrate All Screens | **Medium-Large** (6-10 hours) | Phase 2 |
| Phase 4: Cook Mode Override | **Small** (1 hour) | Phase 2 |

**Total estimated effort: 10-16 hours**

Phase 1 alone would resolve the user's complaint about not having a global config / device settings toggle. Phases 2-4 resolve the visual inconsistencies.

---

## Key Files Referenced

- `/Users/leonidbelyi/personal/palateful/app/lib/main.dart` -- MaterialApp theme configuration
- `/Users/leonidbelyi/personal/palateful/app/lib/core/theme/app_theme.dart` -- Light and dark ThemeData definitions
- `/Users/leonidbelyi/personal/palateful/app/lib/core/theme/app_colors.dart` -- Static color constants (light-mode only)
- `/Users/leonidbelyi/personal/palateful/app/lib/core/theme/theme.dart` -- Barrel export
- `/Users/leonidbelyi/personal/palateful/app/lib/shared/widgets/buttons.dart` -- Shared button widgets with hardcoded AppColors
- `/Users/leonidbelyi/personal/palateful/app/lib/shared/widgets/shimmer_loading.dart` -- Good example of theme-aware widget
- `/Users/leonidbelyi/personal/palateful/app/lib/features/calendar/calendar_screen.dart` -- Worst offender (23 hardcoded AppColors)
- `/Users/leonidbelyi/personal/palateful/app/lib/features/home/widgets/recipe_card.dart` -- High-visibility hardcoded colors
- `/Users/leonidbelyi/personal/palateful/app/lib/features/profile/profile_screen.dart` -- Missing theme toggle in settings
- `/Users/leonidbelyi/personal/palateful/app/lib/features/recipes/cook_mode/cook_mode_screen.dart` -- Intentionally dark, but should use Theme override
