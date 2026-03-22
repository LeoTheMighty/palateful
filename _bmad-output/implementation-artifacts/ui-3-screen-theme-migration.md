# Story UI.3: Screen-by-Screen Theme Migration

Status: complete

## Story

As a user,
I want every screen to look correct in both light and dark mode,
so that there are no broken or unreadable screens regardless of my theme preference.

## Acceptance Criteria

1. Zero direct `AppColors.textPrimary`, `AppColors.cream`, `AppColors.beige`, `AppColors.chocolate`, `AppColors.hazelnut` references remain in feature files
2. All 21 feature files with hardcoded colors are migrated to `Theme.of(context).colorScheme` or `context.appColors`
3. Cook Mode retains its intentional dark appearance via `Theme()` widget override
4. Every screen tested visually in both light and dark mode — no broken colors
5. All 339+ `AppColors.*` references in feature files replaced with theme-aware equivalents

## Tasks / Subtasks

Migration mapping:
| AppColors constant | Theme replacement |
|---|---|
| `textPrimary` | `colorScheme.onSurface` |
| `textSecondary` | `colorScheme.onSurfaceVariant` |
| `textTertiary` | `context.appColors.textTertiary` |
| `cream` / `warmWhite` | `colorScheme.surface` |
| `beige` | `colorScheme.surfaceContainerHighest` |
| `beige-accent` | `colorScheme.surfaceContainerHigh` |
| `chocolate` | `colorScheme.primary` |
| `chocolateLight` | `colorScheme.primaryContainer` |
| `hazelnut` | `colorScheme.secondary` |
| `hazelnutLight` | `colorScheme.secondaryContainer` |
| `terracotta` | `colorScheme.tertiary` |
| `border` | `colorScheme.outline` |
| `divider` | `colorScheme.outlineVariant` |
| `sage` / success colors | `context.appColors.success` |

- [x] Task 1: Migrate high-visibility home screen widgets (AC: #1, #4)
  - [x] `app/lib/features/home/widgets/recipe_card.dart` (17 refs)
  - [x] `app/lib/features/home/home_screen.dart`
  - [x] Test both modes on home screen

- [x] Task 2: Migrate calendar screen (AC: #1, #4)
  - [x] `app/lib/features/calendar/calendar_screen.dart` (23 refs)
  - [x] `app/lib/features/calendar/plan_meal_sheet.dart`
  - [x] Test both modes on calendar tab

- [x] Task 3: Migrate shopping flow (AC: #1, #4)
  - [x] `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`
  - [x] `app/lib/features/shopping_cart/widgets/shopping_list_item_tile.dart`
  - [x] `app/lib/features/shopping_cart/widgets/floating_cart_widget.dart`
  - [x] `app/lib/features/shopping_cart/widgets/urgency_badge.dart`
  - [x] Test both modes across shopping flow

- [x] Task 4: Migrate shared widgets (AC: #1, #5)
  - [x] `app/lib/shared/widgets/buttons.dart` (PillButton, CircleIconButton, DangerButton, SuccessButton)
  - [x] `app/lib/shared/widgets/sort_chips.dart`
  - [x] `app/lib/shared/widgets/meal_filter_bar.dart`
  - [x] Any other shared widgets with hardcoded colors

- [x] Task 5: Migrate recipe screens (AC: #1, #4)
  - [x] `app/lib/features/recipes/recipe_detail_screen.dart`
  - [x] `app/lib/features/recipes/recipe_version_diff_screen.dart`
  - [x] `app/lib/features/recipes/add_recipe/` screens
  - [x] `app/lib/features/recipe_books/recipe_book_detail_screen.dart`

- [x] Task 6: Migrate remaining screens (AC: #1, #2)
  - [x] Any remaining feature files with `AppColors.*` references
  - [x] Grep to verify: `grep -r "AppColors\." app/lib/features/` returns zero results

- [x] Task 7: Cook Mode intentional dark override (AC: #3)
  - [x] `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
  - [x] Wrap screen tree with `Theme(data: AppTheme.dark.copyWith(...), child: ...)`
  - [x] Remove direct `AppColors.*` references, use local dark theme instead
  - [x] Verify Cook Mode looks identical in both app theme modes

- [x] Task 8: Full visual QA pass (AC: #4)
  - [x] Test every tab in light mode
  - [x] Test every tab in dark mode
  - [x] Test Cook Mode in both modes
  - [x] Screenshot comparison for any regressions

## Dev Notes

- This is the largest story in the epic — consider splitting into sub-PRs by task
- Work top-down: home → calendar → shopping → shared → recipes → remaining → cook mode
- After each file, hot reload and verify both modes before moving on
- AppColors constants can remain defined for reference in `app_colors.dart` and in `app_theme.dart` theme definitions — the goal is to eliminate their use in *feature files*
- Depends on Stories 1 (ThemeExtension) and 2 (corrected color values)

### References

- [Investigation: 03-dark-light-mode-consistency.md]
- [Investigation: 02-color-contrast-accessibility.md — Phase 3]
