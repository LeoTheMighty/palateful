# Investigation: Color/Contrast Accessibility Audit

**Date:** 2026-03-22
**Status:** Investigation Complete
**Priority:** High -- Directly impacts usability for all users, especially those with low vision

---

## Executive Summary

The Palateful Flutter app uses a warm cream/chocolate color palette defined centrally in `AppColors` and applied through `AppTheme`. While the palette is aesthetically cohesive, a systematic review reveals **multiple contrast violations** against WCAG 2.1 guidelines, particularly in:

1. **Tertiary/hint text** on cream backgrounds (ratio ~2.8:1, fails AA)
2. **Hazelnut-colored icons** on beige/cream surfaces (ratio ~3.3:1, fails AA for non-text)
3. **Sage green success buttons** with cream text (ratio ~2.7:1, fails AA)
4. **Secondary text** at small sizes on light backgrounds (borderline AA)
5. **Dark theme hardcoded light-mode colors** -- Many feature screens use `AppColors.textPrimary`, `AppColors.textSecondary`, etc. directly instead of theme-aware colors, making them invisible in dark mode
6. **Inline `Colors.white` / `Colors.black`** usage scattered across ~15+ files bypasses the theme system entirely

The investigation catalogues every color constant, every theme color mapping, every inline color usage, and identifies 23 specific problem areas with proposed fixes.

---

## Current State Analysis

### 1. Central Color Definitions (`app/lib/core/theme/app_colors.dart`)

| Constant | Hex Value | Luminance | Usage |
|----------|-----------|-----------|-------|
| **PRIMARY PALETTE** | | | |
| `cream` | `#FAF7F2` | 0.93 | Main background |
| `creamLight` | `#FFFDF9` | 0.97 | Card surfaces |
| `beige` | `#F5EFE6` | 0.87 | Subtle backgrounds |
| `beigeAccent` | `#E8DFD0` | 0.75 | Borders, dividers |
| `warmWhite` | `#FEFCF9` | 0.97 | Elevated surfaces |
| `warmIvory` | `#F5ECD7` | 0.84 | Dark mode primary text |
| **SECONDARY PALETTE** | | | |
| `chocolate` | `#4A3728` | 0.05 | Primary accent, buttons |
| `chocolateLight` | `#5D4A3A` | 0.08 | Hover states, dark mode cards |
| `chocolateDark` | `#3A2A1E` | 0.03 | Pressed states |
| `hazelnut` | `#8B7355` | 0.19 | Secondary accent |
| `hazelnutLight` | `#A89076` | 0.29 | Light hazelnut accents |
| `hazelnutDark` | `#6B5642` | 0.11 | Dark hazelnut text |
| **ACCENT COLORS** | | | |
| `terracotta` | `#BE8A60` | 0.27 | Highlights |
| `sage` | `#8FA882` | 0.37 | Success states |
| `coral` | `#CB8B73` | 0.30 | Warnings |
| `dustyRose` | `#B86B6B` | 0.18 | Errors |
| **NEUTRAL / TEXT** | | | |
| `textPrimary` | `#2D2420` | 0.02 | Primary text |
| `textSecondary` | `#6B5D54` | 0.12 | Secondary text |
| `textTertiary` | `#9C8E84` | 0.29 | Tertiary/hint text |
| `textDisabled` | `#BEB5AC` | 0.47 | Disabled text |
| `divider` | `#E5DED5` | 0.74 | Divider color |
| `border` | `#D9D0C5` | 0.64 | Border color |
| `shadow` | `#1A4A3728` | n/a | Shadow (10% opacity) |
| **SEMANTIC COLORS** | | | |
| `success` / `sage` | `#8FA882` | 0.37 | Success |
| `successLight` | `#EDF4EB` | 0.90 | Success background |
| `successDark` | `#6B8A60` | 0.22 | Success on light bg |
| `warning` | `#D4A853` | 0.38 | Warning |
| `warningLight` | `#FDF6E7` | 0.93 | Warning background |
| `warningDark` | `#B08D3E` | 0.27 | Warning text |
| `error` / `dustyRose` | `#B86B6B` | 0.18 | Error |
| `errorLight` | `#F9EEEE` | 0.89 | Error background |
| `errorDark` | `#944D4D` | 0.11 | Error text |
| `info` | `#7A8B9A` | 0.25 | Info |
| `infoLight` | `#EEF2F5` | 0.89 | Info background |
| `infoDark` | `#5A6B7A` | 0.15 | Info text |

### 2. Calculated Contrast Ratios (Key Pairings)

Using the WCAG relative luminance formula: `CR = (L1 + 0.05) / (L2 + 0.05)`

| Foreground | Background | Contrast Ratio | WCAG AA (4.5:1) | WCAG AA Large (3:1) | Status |
|-----------|-----------|---------------|-----------------|---------------------|--------|
| `textPrimary` (#2D2420) | `cream` (#FAF7F2) | **14.0:1** | PASS | PASS | Good |
| `textSecondary` (#6B5D54) | `cream` (#FAF7F2) | **5.8:1** | PASS | PASS | Good |
| `textTertiary` (#9C8E84) | `cream` (#FAF7F2) | **2.9:1** | **FAIL** | **FAIL** | PROBLEM |
| `textDisabled` (#BEB5AC) | `cream` (#FAF7F2) | **1.8:1** | **FAIL** | **FAIL** | Expected (disabled) |
| `hazelnut` (#8B7355) | `cream` (#FAF7F2) | **4.0:1** | **FAIL** | PASS | Borderline |
| `hazelnut` (#8B7355) | `beige` (#F5EFE6) | **3.5:1** | **FAIL** | PASS | Borderline |
| `hazelnut` (#8B7355) | `creamLight` (#FFFDF9) | **4.2:1** | **FAIL** | PASS | Borderline |
| `chocolate` (#4A3728) | `cream` (#FAF7F2) | **9.3:1** | PASS | PASS | Good |
| `cream` (#FAF7F2) | `chocolate` (#4A3728) | **9.3:1** | PASS | PASS | Good |
| `cream` (#FAF7F2) | `sage` (#8FA882) | **2.4:1** | **FAIL** | **FAIL** | PROBLEM |
| `cream` (#FAF7F2) | `dustyRose` (#B86B6B) | **3.8:1** | **FAIL** | PASS | Borderline |
| `terracotta` (#BE8A60) | `cream` (#FAF7F2) | **3.0:1** | **FAIL** | PASS | Borderline |
| `terracotta` (#BE8A60) | `chocolate` (#4A3728) | **3.1:1** | **FAIL** | PASS | Borderline |
| `warmIvory` (#F5ECD7) | `chocolate` (#4A3728) | **8.5:1** | PASS | PASS | Good |
| `warmIvory` (#F5ECD7) | `chocolateLight` (#5D4A3A) | **6.3:1** | PASS | PASS | Good |
| `hazelnutLight` (#A89076) | `chocolate` (#4A3728) | **3.0:1** | **FAIL** | PASS | Borderline |
| `hazelnutLight` (#A89076) | `chocolateLight` (#5D4A3A) | **2.3:1** | **FAIL** | **FAIL** | PROBLEM |
| `textSecondary` (#6B5D54) | `beige` (#F5EFE6) | **5.0:1** | PASS | PASS | Good |
| `textTertiary` (#9C8E84) | `beige` (#F5EFE6) | **2.5:1** | **FAIL** | **FAIL** | PROBLEM |
| `warningDark` (#B08D3E) | `warningLight` (#FDF6E7) | **3.2:1** | **FAIL** | PASS | Borderline |
| `errorDark` (#944D4D) | `errorLight` (#F9EEEE) | **5.0:1** | PASS | PASS | Good |
| `infoDark` (#5A6B7A) | `infoLight` (#EEF2F5) | **4.1:1** | **FAIL** | PASS | Borderline |
| `successDark` (#6B8A60) | `successLight` (#EDF4EB) | **3.3:1** | **FAIL** | PASS | Borderline |
| `white` (#FFFFFF) | `chocolate` (#4A3728) | **10.1:1** | PASS | PASS | Good |

### 3. Theme Configurations (`app/lib/core/theme/app_theme.dart`)

**Light Theme Color Scheme:**
- `primary` = chocolate, `onPrimary` = cream (9.3:1 -- PASS)
- `primaryContainer` = chocolateLight, `onPrimaryContainer` = cream (7.0:1 -- PASS)
- `secondary` = hazelnut, `onSecondary` = cream (4.0:1 -- **FAIL AA**)
- `secondaryContainer` = hazelnutLight, `onSecondaryContainer` = textPrimary (12.2:1 -- PASS)
- `surface` = cream, `onSurface` = textPrimary (14.0:1 -- PASS)
- `error` = dustyRose, `onError` = cream (3.8:1 -- **FAIL AA**)

**Dark Theme Color Scheme:**
- `primary` = terracotta, `onPrimary` = chocolate (3.1:1 -- **FAIL AA**)
- `primaryContainer` = chocolateLight, `onPrimaryContainer` = warmIvory (6.3:1 -- PASS)
- `secondary` = hazelnutLight, `onSecondary` = chocolate (3.0:1 -- **FAIL AA**)
- `surface` = chocolate, `onSurface` = warmIvory (8.5:1 -- PASS)
- `error` = coral, `onError` = chocolate (3.4:1 -- **FAIL AA**)

**Component Themes with Issues:**

| Component | Issue | Ratio |
|-----------|-------|-------|
| Chip (light) - selected label on `chocolate` | Uses `secondaryLabelStyle` with `cream` -- PASS | 9.3:1 |
| Chip (light) - unselected label on `beige` | Uses `textPrimary` -- PASS | 12.0:1 |
| ListTile - `iconColor: hazelnut` | On cream/white card background | ~4.0:1 (borderline) |
| Nav bar - inactive `textTertiary` | On `warmWhite` background | ~2.8:1 (**FAIL**) |
| Tab bar - unselected `textTertiary` | On cream background | ~2.8:1 (**FAIL**) |
| Input hint - `textTertiary` | On `warmWhite` input background | ~2.8:1 (**FAIL**) |
| Input prefix/suffix icons - `textTertiary` | On `warmWhite` input background | ~2.8:1 (**FAIL**) |
| Switch track (selected) - 50% opacity chocolate | On cream background | Very low |
| Dark elevated button - `chocolate` on `terracotta` | Dark text on medium bg | ~3.1:1 (**FAIL AA**) |
| Dark outlined button - `hazelnutLight` on transparent/chocolate | Light text on dark bg | ~3.0:1 (**FAIL AA**) |
| Dark body small / label small/medium - `hazelnutLight` on `chocolate` | | ~3.0:1 (**FAIL AA**) |
| Dark dialog content - `hazelnutLight` on `chocolateLight` | | ~2.3:1 (**FAIL**) |

### 4. Inline Color Usage in Feature Files (Non-Theme Colors)

These are hardcoded color values found in feature screens that bypass the theme system:

**`Colors.white` usage (16+ instances):**
- `shopping_list_item_tile.dart:79` -- check icon on sage background
- `floating_cart_widget.dart:280` -- badge text on chocolate/warning
- `member_presence.dart:83,101,114,121` -- avatar borders and text
- `calendar_screen.dart:267,467` -- date text on chocolate, button text
- `plan_meal_sheet.dart:264,268,287,299` -- meal type chips, button text
- `batch_import_status_widget.dart:218` -- icon on success bg
- `batch_job_result_sheet.dart:100` -- button text
- `photo_capture_screen.dart:645,660,700,714` -- overlay text, button text
- `shopping_list_screen.dart:470,501,598` -- delete icon, add button icon

**`Colors.black` / `Colors.black54` usage:**
- `recipe_card.dart:75` -- `Colors.black.withValues(alpha: 0.3)` favorite button backdrop
- `home_screen.dart:646` -- `Colors.black.withValues(alpha: 0.7)` gradient overlay
- `photo_capture_screen.dart:642,655` -- `Colors.black54` close button overlay
- `login_screen.dart:214` -- Apple sign-in button background

**`Colors.red` usage:**
- `recipe_card.dart:81` -- favorite icon when active
- `recipe_detail_screen.dart:598` -- favorite icon when active
- `home_screen.dart:529` -- `Colors.red.shade400` favorite icon

**`Colors.grey` usage:**
- `recipe_detail_screen.dart:589` -- broken image error icon
- `recipe_book_detail_screen.dart:562` -- WebSocket status indicator (`Colors.green` / `Colors.grey`)
- `public_recipe_screen.dart:111` -- broken image icon

**`Colors.green` / `Colors.amber` usage:**
- `recipe_version_diff_screen.dart:99,103,113,117` -- diff highlighting (green bg, amber bg, green.shade800, amber.shade900)
- `recipe_book_detail_screen.dart:562` -- `Colors.green` WS indicator

**Platform-specific raw colors (login_screen.dart):**
- `Color(0xFF4285F4)` -- Google blue
- `Color(0xFF1F1F1F)` -- Google text
- `Color(0xFFDADCE0)` -- Google border
- `Colors.white` -- Google button bg
- `Colors.black` -- Apple button bg
- `Colors.white` -- Apple text/icon

### 5. Dark Mode Compatibility Issues

Many feature files use `AppColors.textPrimary`, `AppColors.cream`, `AppColors.beige`, etc. directly instead of `Theme.of(context).colorScheme.onSurface`, `colorScheme.surface`, etc. This means these colors are light-mode-only and will produce **very poor contrast or invisible text in dark mode**.

**Files with hardcoded light-mode AppColors (not theme-aware):**
- `recipe_card.dart` -- `AppColors.textPrimary`, `textTertiary`, `textSecondary`, `beige`, `hazelnut` throughout
- `sort_chips.dart` -- `AppColors.chocolate`, `AppColors.textTertiary`
- `meal_filter_bar.dart` -- `AppColors.cream`, `AppColors.chocolate`, `AppColors.beige`, `AppColors.textPrimary`
- `calendar_screen.dart` -- All colors hardcoded as AppColors light variants
- `shopping_list_screen.dart` -- `AppColors.cream`, `AppColors.chocolate`, `AppColors.textPrimary` throughout
- `plan_meal_sheet.dart` -- All colors hardcoded
- `batch_import_status_widget.dart` -- All colors hardcoded
- `batch_job_result_sheet.dart` -- All colors hardcoded
- `floating_cart_widget.dart` -- All colors hardcoded
- `shopping_list_item_tile.dart` -- All colors hardcoded
- `urgency_badge.dart` -- All colors hardcoded
- `step_navigator.dart` -- All colors hardcoded
- `ingredient_strip.dart` -- All colors hardcoded
- `photo_capture_screen.dart` -- All colors hardcoded
- `add_recipe_sheet.dart` -- All colors hardcoded
- `file_import_screen.dart` -- All colors hardcoded
- `celebration_overlay.dart` -- All colors hardcoded

**Files that ARE theme-aware (good examples):**
- `empty_state.dart` -- Uses `Theme.of(context).colorScheme` and `textTheme`
- `message_bubble.dart` -- Uses `colorScheme` throughout
- `recipe_result_card.dart` -- Uses `colorScheme` throughout
- `onboarding_welcome_screen.dart` -- Uses `colorScheme` and `textTheme`
- `onboarding_start_screen.dart` -- Uses `colorScheme`

---

## WCAG Standards Overview

### WCAG 2.1 Contrast Requirements

| Level | Normal Text (<18pt / <14pt bold) | Large Text (>=18pt / >=14pt bold) | Non-text (icons, borders) |
|-------|----------------------------------|-----------------------------------|--------------------------|
| **AA** | 4.5:1 minimum | 3:1 minimum | 3:1 minimum |
| **AAA** | 7:1 minimum | 4.5:1 minimum | Not defined |

**Recommended target for Palateful:** WCAG AA minimum (4.5:1 for body text, 3:1 for large text and UI components). AAA for primary content text.

### Key WCAG 2.1 Success Criteria

- **1.4.3 Contrast (Minimum)** -- Level AA: 4.5:1 for normal text, 3:1 for large text
- **1.4.6 Contrast (Enhanced)** -- Level AAA: 7:1 for normal text, 4.5:1 for large text
- **1.4.11 Non-text Contrast** -- Level AA: 3:1 for UI components and graphical objects
- **1.4.1 Use of Color** -- Color must not be the only means of conveying information

### Material Design 3 Guidance

Material Design 3 recommends:
- Using the `ColorScheme` system consistently (all `on*` colors should meet 4.5:1 against their paired surface)
- Dynamic color tokens rather than hardcoded values
- Always testing against both light and dark themes

---

## Identified Problem Areas

### CRITICAL (Contrast Ratio < 3:1)

**P1. `textTertiary` on cream/beige backgrounds (~2.8:1)**
- **Files:** `sort_chips.dart`, `recipe_card.dart`, `calendar_screen.dart`, `shopping_list_screen.dart`, `floating_cart_widget.dart`, `urgency_badge.dart`, `ingredient_strip.dart`, `step_navigator.dart`, `photo_capture_screen.dart`, `batch_import_status_widget.dart`
- **Impact:** Hint text, secondary metadata, recipe count, timestamps are all hard to read
- **Fix:** Darken `textTertiary` from `#9C8E84` to approximately `#7A6E64` (target 4.5:1 on cream)

**P2. `cream` text on `sage` green success buttons (~2.4:1)**
- **Files:** `buttons.dart` (SuccessButton), `celebration_overlay.dart`
- **Impact:** Success button text is nearly unreadable
- **Fix:** Use white (`#FFFFFF`) instead of cream, or darken sage to `#6B8A5E`; alternatively use dark text on sage

**P3. Dark theme dialog content: `hazelnutLight` on `chocolateLight` (~2.3:1)**
- **Files:** `app_theme.dart` dark dialog `contentTextStyle`
- **Impact:** Dialog body text in dark mode is very difficult to read
- **Fix:** Use `warmIvory` instead of `hazelnutLight` for dialog content text

**P4. Dark theme `hazelnutLight` body/label text on `chocolate` (~3.0:1)**
- **Files:** `app_theme.dart` dark `bodySmall`, `labelMedium`, `labelSmall`
- **Impact:** Small body text and labels in dark mode barely visible
- **Fix:** Increase lightness -- use a lighter variant or `warmIvory` for body small

**P5. Navigation bar inactive icons/labels: `textTertiary` on `warmWhite` (~2.8:1)**
- **Files:** `app_theme.dart` light `navigationBarTheme`
- **Impact:** Unselected navigation items hard to see
- **Fix:** Use `textSecondary` or a darker value for inactive nav items

### HIGH (Contrast Ratio 3:1 - 4.5:1, fails AA for normal text)

**P6. `hazelnut` icons on cream/white backgrounds (~4.0:1)**
- **Files:** `recipe_card.dart`, `calendar_screen.dart`, `ingredient_strip.dart`, `photo_capture_screen.dart`, `file_import_screen.dart`, `app_theme.dart` (ListTile iconColor)
- **Impact:** Decorative icons are borderline; functional icons fail AA
- **Fix:** For functional icons, darken to `hazelnutDark` (`#6B5642`, ~6.0:1); decorative icons are acceptable at 3:1

**P7. `hazelnut` text as outlined button foreground on cream (~4.0:1)**
- **Files:** `app_theme.dart` light `outlinedButtonTheme`
- **Impact:** Secondary button text slightly hard to read at small sizes
- **Fix:** Use `hazelnutDark` for button text

**P8. `cream` text on `dustyRose` error (~3.8:1)**
- **Files:** `app_theme.dart` light ColorScheme `onError`
- **Impact:** Error state text might be hard to read
- **Fix:** Use white or darken `dustyRose`

**P9. Dark theme `onPrimary`: `chocolate` on `terracotta` (~3.1:1)**
- **Files:** `app_theme.dart` dark ColorScheme, dark elevated button
- **Impact:** Primary button text in dark mode is hard to read
- **Fix:** Use `chocolateDark` or white text on terracotta

**P10. Dark theme `onSecondary`: `chocolate` on `hazelnutLight` (~3.0:1)**
- **Files:** `app_theme.dart` dark ColorScheme
- **Impact:** Secondary component text in dark mode
- **Fix:** Use `chocolateDark` for better contrast

**P11. `terracotta` text on cream background (~3.0:1)**
- **Files:** `file_import_screen.dart` (coming soon banner), `app_theme.dart` (snackbar action)
- **Impact:** Terracotta-colored text/links hard to read on light backgrounds
- **Fix:** Darken terracotta for text use to approximately `#9A6C42`

**P12. Tab bar unselected labels: `textTertiary` on cream (~2.8:1)**
- **Files:** `app_theme.dart` light `tabBarTheme`
- **Impact:** Unselected tabs hard to distinguish
- **Fix:** Use `textSecondary`

**P13. `warningDark` on `warningLight` (~3.2:1)**
- **Files:** `urgency_badge.dart`, `shopping_list_screen.dart`
- **Impact:** Warning badge text borderline
- **Fix:** Darken `warningDark` to approximately `#8A6F2E`

**P14. `successDark` on `successLight` (~3.3:1)**
- **Files:** `urgency_badge.dart`
- **Impact:** "Soon" urgency badge text borderline
- **Fix:** Darken `successDark` to approximately `#4F6E42`

**P15. `infoDark` on `infoLight` (~4.1:1)**
- **Files:** `urgency_badge.dart`
- **Impact:** "Today" urgency badge text borderline
- **Fix:** Darken `infoDark` slightly to approximately `#4A5B6A`

### MEDIUM (Dark mode hardcoded color issues)

**P16. Recipe card entirely hardcoded for light mode**
- **File:** `recipe_card.dart`
- **Impact:** In dark mode, light-mode text colors on dark background create poor or zero contrast
- **Fix:** Migrate to `Theme.of(context).colorScheme` references

**P17. Calendar screen entirely hardcoded for light mode**
- **File:** `calendar_screen.dart`
- **Impact:** Calendar grid, date text, meal event cards all use light-mode colors
- **Fix:** Migrate to theme-aware colors

**P18. Shopping cart widgets hardcoded for light mode**
- **Files:** `shopping_list_screen.dart`, `shopping_list_item_tile.dart`, `floating_cart_widget.dart`, `urgency_badge.dart`, `celebration_overlay.dart`, `member_presence.dart`
- **Impact:** Entire shopping flow potentially unusable in dark mode
- **Fix:** Migrate to theme-aware colors

**P19. Cook mode widgets hardcoded (mixed)**
- **Files:** `step_navigator.dart`, `ingredient_strip.dart` -- use hardcoded AppColors
- **Note:** `cook_mode_screen.dart` and `cook_mode_chat_sheet.dart` intentionally use dark chocolate theme (may be correct for immersive cook mode, but still uses hardcoded values)

**P20. Sort chips and meal filter bar hardcoded**
- **Files:** `sort_chips.dart`, `meal_filter_bar.dart`
- **Fix:** Migrate to theme-aware colors

### LOW

**P21. Raw `Colors.red` for favorites**
- **Files:** `recipe_card.dart`, `recipe_detail_screen.dart`, `home_screen.dart`
- **Impact:** Red on dark/varied backgrounds; not using semantic color
- **Fix:** Consider defining `AppColors.favorite` constant

**P22. `Colors.grey` for broken image icons**
- **Files:** `recipe_detail_screen.dart`, `public_recipe_screen.dart`
- **Impact:** Minor -- error state placeholder
- **Fix:** Use `AppColors.textDisabled` or `colorScheme.onSurfaceVariant`

**P23. Version diff screen uses raw Material colors**
- **File:** `recipe_version_diff_screen.dart`
- **Impact:** `Colors.green`, `Colors.amber` and shades used directly
- **Fix:** Define semantic diff colors in AppColors

---

## Recommendations

### Phase 1: Fix Critical Contrast Failures (1-2 days)

1. **Adjust `textTertiary`** in `AppColors` from `#9C8E84` to `#7A6E64` (achieves ~4.5:1 on cream). This single change fixes P1, P5, P12 across the entire app since most components reference this constant.

2. **Fix success button contrast (P2):** Change `SuccessButton` to use `Colors.white` or `AppColors.warmWhite` instead of `AppColors.cream` as foreground, OR darken `sage` for button use.

3. **Fix dark theme text colors (P3, P4):** In `app_theme.dart` dark theme:
   - Dialog `contentTextStyle`: change from `hazelnutLight` to `warmIvory`
   - `bodySmall`, `labelMedium`, `labelSmall`: change from `hazelnutLight` to a lighter value (e.g., `#C8B89A`)

4. **Fix dark theme button contrast (P9, P10):** Change dark `onPrimary` and `onSecondary` to use white or `warmIvory` instead of `chocolate`.

### Phase 2: Fix High-Priority Issues (2-3 days)

5. **Adjust semantic "dark" colors** for badge text:
   - `warningDark`: `#B08D3E` -> `#8A6F2E`
   - `successDark`: `#6B8A60` -> `#4F6E42`
   - `infoDark`: `#5A6B7A` -> `#4A5B6A`

6. **Darken `hazelnut` for text use:** Where hazelnut is used as text color (not just icon), use `hazelnutDark` (`#6B5642`) instead.

7. **Fix `onSecondary` and `onError`** in light ColorScheme: Use `#FFFFFF` instead of `cream` for better contrast on hazelnut/dustyRose.

8. **Create `AppColors.terracottaDark`** for text usage (~`#9A6C42`) since terracotta itself is too light for body text on cream.

### Phase 3: Dark Mode Theme-Awareness Migration (3-5 days)

9. **Migrate all feature files** from hardcoded `AppColors.*` to `Theme.of(context).colorScheme.*` or `Theme.of(context).textTheme.*` references. Priority order:
   - `recipe_card.dart` (seen on every screen)
   - `meal_filter_bar.dart` and `sort_chips.dart` (home screen)
   - `calendar_screen.dart` (calendar tab)
   - Shopping cart widgets (shopping flow)
   - Remaining screens

10. **Create a mapping guide** for developers:
    - `AppColors.textPrimary` -> `colorScheme.onSurface`
    - `AppColors.textSecondary` -> `colorScheme.onSurfaceVariant`
    - `AppColors.cream` -> `colorScheme.surface`
    - `AppColors.beige` -> `colorScheme.surfaceContainerHighest`
    - `AppColors.chocolate` -> `colorScheme.primary`
    - `AppColors.hazelnut` -> `colorScheme.secondary`

### Phase 4: Enforcement and Testing (1-2 days)

11. Add a custom lint rule or code review checklist to prevent new hardcoded colors.
12. Set up automated contrast checking in CI.

---

## Proposed Color Audit Checklist

For each screen/component, verify:

- [ ] **All text** meets 4.5:1 against its background (normal text) or 3:1 (large text >=18pt/14pt bold)
- [ ] **All icons** that convey meaning meet 3:1 against their background
- [ ] **All interactive components** (buttons, inputs, chips, toggles) have 3:1 contrast for their boundaries
- [ ] **Focus indicators** are visible with 3:1 contrast
- [ ] **Selected/active states** maintain required contrast
- [ ] **Disabled states** are visually distinct (lower contrast is acceptable and expected)
- [ ] **Error, warning, success, info states** have readable text
- [ ] **Dark mode** rendering is tested and text is legible
- [ ] **No raw `Colors.*`** used (except platform-mandated like sign-in buttons)
- [ ] **Colors are theme-aware** (`Theme.of(context).*` not `AppColors.*` directly for surface/text colors)

### Screen-by-Screen Audit Status

| Screen | Light Mode | Dark Mode | Theme-Aware |
|--------|-----------|-----------|-------------|
| Home (recipe grid) | Needs audit | Needs audit | No (hardcoded) |
| Recipe Card | textTertiary FAIL | Broken (hardcoded) | No |
| Sort Chips | textTertiary FAIL | Broken (hardcoded) | No |
| Meal Filter Bar | OK | Broken (hardcoded) | No |
| Recipe Detail | Needs audit | Needs audit | Partial |
| Edit Recipe | Needs audit | Needs audit | Unknown |
| Add Recipe Sheet | OK | Broken (hardcoded) | No |
| URL Import | Needs audit | Needs audit | Unknown |
| Bulk URL Import | Needs audit | Needs audit | Unknown |
| File Import | terracotta text FAIL | Broken (hardcoded) | No |
| Photo Capture | textTertiary FAIL | Broken (hardcoded) | No |
| Share Import | Needs audit | Needs audit | Unknown |
| Import Review | Needs audit | Needs audit | Unknown |
| Recipe Wizard | Needs audit | Needs audit | Unknown |
| Cook Mode | Intentionally dark | N/A (dark-only) | Partial |
| Step Navigator | OK | May be broken | No (hardcoded) |
| Ingredient Strip | OK | Broken (hardcoded) | No |
| Cook Mode Chat | OK (dark BG) | N/A | Uses AppColors |
| Post-Cook Feedback | OK (dark BG) | N/A | Uses AppColors |
| Calendar | textTertiary FAIL | Broken (hardcoded) | No |
| Plan Meal Sheet | OK | Broken (hardcoded) | No |
| Search | Needs audit | Needs audit | Unknown |
| Chat | OK | OK | Yes (theme-aware) |
| Message Bubble | OK | OK | Yes (theme-aware) |
| Recipe Result Card | OK | OK | Yes (theme-aware) |
| Shopping List | textTertiary FAIL | Broken (hardcoded) | No |
| Shopping Item Tile | OK | Broken (hardcoded) | No |
| Floating Cart | textTertiary FAIL | Broken (hardcoded) | No |
| Urgency Badge | warningDark borderline | Broken (hardcoded) | No |
| Celebration Overlay | OK | Broken (hardcoded) | No |
| Member Presence | OK | Broken (hardcoded) | No |
| Cart Screen | Needs audit | Needs audit | Unknown |
| Recipe Books | Needs audit | Needs audit | Partial |
| Recipe Book Detail | Raw Colors.green | Needs audit | Partial |
| Recipe Book Members | Needs audit | Needs audit | Unknown |
| Archived Recipe Books | Needs audit | Needs audit | Unknown |
| Archived Recipes | Needs audit | Needs audit | Unknown |
| Public Recipe | Colors.grey | Needs audit | Unknown |
| Version History | Needs audit | Needs audit | Unknown |
| Version Diff | Raw Colors.green/amber | Needs audit | No |
| Invitations | Needs audit | Needs audit | Unknown |
| Invite Link Preview | Needs audit | Needs audit | Unknown |
| Profile | Colors.white shimmer | Needs audit | Partial |
| Notification Prefs | Needs audit | Needs audit | Unknown |
| Login | Platform colors OK | Needs audit | Partial |
| Onboarding Welcome | OK | Needs audit | Yes (theme-aware) |
| Onboarding Start | OK | Needs audit | Partial |
| Batch Import Status | OK | Broken (hardcoded) | No |
| Batch Job Result | OK | Broken (hardcoded) | No |
| Empty State | OK | OK | Yes (theme-aware) |
| Buttons (shared) | Success button FAIL | Uses AppColors | Partial |
| Shimmer Loading | OK | OK | Yes (checks brightness) |

---

## Technical Considerations

### How to Enforce Good Contrast Going Forward

1. **Lint Rules:** Create a custom Dart analyzer plugin or use `custom_lint` to flag:
   - Direct `Colors.*` usage (except in test files)
   - Direct `AppColors.*` usage for text/icon colors in widget `build()` methods (should use `Theme.of(context)`)
   - `Color(0x...)` literals in non-theme files

2. **Design Tokens Approach:** Consider restructuring `AppColors` into two layers:
   - **Primitive tokens:** Raw color values (what we have now)
   - **Semantic tokens:** Context-aware colors that reference primitives and change based on theme brightness
   ```dart
   // Instead of:
   color: AppColors.textTertiary  // Always light-mode value

   // Use:
   color: context.colors.textTertiary  // Resolves to correct value per theme
   ```

3. **Contrast Validation Utility:** Add a dev-only utility that overlays contrast ratios on screen:
   ```dart
   // Development tool
   static double contrastRatio(Color fg, Color bg) {
     final fgLuminance = fg.computeLuminance();
     final bgLuminance = bg.computeLuminance();
     final lighter = math.max(fgLuminance, bgLuminance);
     final darker = math.min(fgLuminance, bgLuminance);
     return (lighter + 0.05) / (darker + 0.05);
   }
   ```

4. **CI Integration:** Add a Flutter test that imports `AppColors` and validates all known foreground/background pairings meet minimum contrast ratios. This prevents regressions when colors are adjusted.

5. **Dark Mode Testing:** Add integration test screenshots for both light and dark mode on key screens.

---

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Fix critical contrast constants | 1-2 days | Low -- mostly constant value changes |
| Phase 2: Fix high-priority issues | 2-3 days | Low-Medium -- theme file changes + semantic color adjustments |
| Phase 3: Dark mode migration | 3-5 days | Medium -- touching ~20 feature files, needs QA per screen |
| Phase 4: Lint rules + CI | 1-2 days | Low -- tooling only |
| **Total** | **7-12 days** | |

### Quick Wins (< 1 hour each)
- Darken `textTertiary` in `AppColors` (fixes ~10 screens instantly)
- Fix dark theme `bodySmall` / `labelSmall` text color
- Fix dark theme dialog content text color
- Fix `SuccessButton` foreground color
- Fix light theme `onSecondary` and `onError`

### Dependencies
- No external dependencies
- Color changes should be reviewed with design/product for aesthetic approval
- Dark mode migration could be done incrementally screen-by-screen
