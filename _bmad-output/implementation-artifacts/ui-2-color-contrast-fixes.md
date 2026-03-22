# Story UI.2: Color Palette & Contrast Accessibility Fixes

Status: complete

## Story

As a user,
I want all text, icons, and interactive elements to be clearly visible,
so that I can read and use the app comfortably in both light and dark modes.

## Acceptance Criteria

1. All text meets WCAG 2.1 AA contrast ratio (4.5:1 body, 3:1 large text) in both modes
2. `textTertiary` updated from #9C8E84 to #7A6E64 (~4.5:1 on cream)
3. Success/warning/info button text has ≥4.5:1 contrast against button background
4. Dark mode dialog, label, and body text is clearly readable on chocolate backgrounds
5. Zero raw `Colors.white`, `Colors.black`, `Colors.red`, `Colors.grey` remain in codebase
6. PalatefulColors ThemeExtension populated with all semantic colors (from Story 1)

## Tasks / Subtasks

- [x] Task 1: Fix critical color constants (AC: #2)
  - [x] `app/lib/core/theme/app_colors.dart`: Change `textTertiary` from `Color(0xFF9C8E84)` to `Color(0xFF7A6E64)`
  - [x] Verify impact across ~10 screens that use textTertiary

- [x] Task 2: Fix button contrast (AC: #3)
  - [x] `app/lib/shared/widgets/buttons.dart`: SuccessButton foreground → `Colors.white` or `AppColors.warmWhite`
  - [x] Verify all button variants have proper foreground/background contrast

- [x] Task 3: Fix dark theme colors (AC: #4)
  - [x] `app/lib/core/theme/app_theme.dart`:
    - Dark theme dialog `contentTextStyle`: `hazelnutLight` → `warmIvory` or `#F5ECD7`
    - Dark `bodySmall`, `labelMedium`, `labelSmall`: `hazelnutLight` → lighter value (~`#C8B89A`)
    - Dark `ColorScheme.onPrimary` and `onSecondary`: `chocolate` → `Colors.white` or `warmIvory`

- [x] Task 4: Fix semantic "dark" variant colors (AC: #1)
  - [x] `app/lib/core/theme/app_colors.dart`:
    - `warningDark`: `#B08D3E` → `#8A6F2E`
    - `successDark`: `#6B8A60` → `#4F6E42`
    - `infoDark`: `#5A6B7A` → `#4A5B6A`
    - Add `terracottaDark`: `#9A6C42` for text usage on light backgrounds
  - [x] Update light `ColorScheme.onSecondary` and `onError`: `cream` → `#FFFFFF`

- [x] Task 5: Eliminate raw Material colors (AC: #5)
  - [x] Search and replace all `Colors.red` → `AppColors.favorite` or `colorScheme.error`
  - [x] Replace `Colors.grey` → `AppColors.textDisabled` or `colorScheme.onSurfaceVariant`
  - [x] Replace `Colors.white` → `colorScheme.surface` or `colorScheme.onPrimary`
  - [x] Replace `Colors.black` → `colorScheme.onSurface`
  - [x] Replace `Colors.green`/`Colors.amber` → semantic diff colors in AppColors
  - [x] Files to check: `recipe_card.dart`, `recipe_detail_screen.dart`, `recipe_version_diff_screen.dart`, `recipe_book_detail_screen.dart`, and others

- [x] Task 6: Populate PalatefulColors ThemeExtension values (AC: #6)
  - [x] Fill in light and dark PalatefulColors instances with all the corrected values
  - [x] Ensure all semantic slots have proper contrast in both modes

## Dev Notes

- **Biggest quick win:** Changing `textTertiary` fixes ~10 screens in one line
- Test contrast with: https://webaim.org/resources/contrastchecker/
- Depends on Story 1 for ThemeExtension infrastructure
- After this story, the color *values* are correct; Story 3 migrates *usage* to theme-aware access

### References

- [Investigation: 02-color-contrast-accessibility.md]
- [WCAG 2.1 Contrast Requirements](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
