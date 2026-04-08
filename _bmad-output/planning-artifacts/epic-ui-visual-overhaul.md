# Epic: UI/Visual Polish & Theme System Overhaul

## Overview

Comprehensive overhaul of Palateful's visual layer — fixing contrast accessibility, building a proper theme system with dark/light mode support, adding font personalization, and streamlining the sharing UX. This epic addresses investigations #01–#04 and brings the app's visual quality and usability up to a polished, production-grade standard.

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Theme Infrastructure — Dark/Light Mode Toggle & ThemeExtension | 3–4 hours | None (foundational) |
| 2 | Color Palette & Contrast Accessibility Fixes | 1–2 days | Story 1 (ThemeExtension) |
| 3 | Screen-by-Screen Theme Migration | 2–3 days | Stories 1 & 2 |
| 4 | Typography Personalization (Libre Baskerville + Inter / Sora) | 4–6 hours | Story 1 (font preference state) |
| 5 | Sharing UX Overhaul | 2–3 days | None (independent) |

**Total estimated effort: 6–9 days**

---

## Story 1: Theme Infrastructure — Dark/Light Mode Toggle & ThemeExtension

As a user,
I want to control my app's appearance (System / Light / Dark) from my profile,
so that the app respects my preference and looks correct in both modes.

**Acceptance Criteria:**

1. **Given** the user opens the Profile screen,
   **When** they look at the settings section,
   **Then** they see an "Appearance" option with System (default) / Light / Dark choices.

2. **Given** the user selects "Dark",
   **When** the selection is saved,
   **Then** the entire app immediately switches to dark mode and the preference persists across restarts.

3. **Given** the user selects "System",
   **When** the device is in dark mode,
   **Then** the app follows the device setting.

4. **Given** the app starts for the first time,
   **When** no preference has been set,
   **Then** the app defaults to System mode.

5. **Given** the ThemeExtension is created,
   **When** any screen accesses `context.appColors`,
   **Then** it receives the correct semantic color set for the current theme mode.

**Key files:**
- Create: `app/lib/providers/theme_mode_provider.dart`
- Create: `app/lib/core/theme/palateful_colors_extension.dart`
- Modify: `app/lib/main.dart` (wire provider to MaterialApp themeMode)
- Modify: `app/lib/core/theme/app_theme.dart` (add ThemeExtension to both themes)
- Modify: `app/lib/features/profile/profile_screen.dart` (add Appearance toggle)

---

## Story 2: Color Palette & Contrast Accessibility Fixes

As a user,
I want all text, icons, and interactive elements to be clearly visible,
so that I can read and use the app comfortably in both light and dark modes.

**Acceptance Criteria:**

1. **Given** any text on a background,
   **When** checked with WCAG 2.1 guidelines,
   **Then** it meets at least AA contrast ratio (4.5:1 for body text, 3:1 for large text).

2. **Given** the `textTertiary` color is updated,
   **When** viewing hint text, timestamps, metadata across all screens,
   **Then** the text is clearly readable on cream/beige backgrounds.

3. **Given** success/warning/info buttons,
   **When** viewed in both light and dark mode,
   **Then** button text has at least 4.5:1 contrast against the button background.

4. **Given** dark mode is active,
   **When** viewing dialog content, labels, and body text,
   **Then** all text meets AA contrast on chocolate backgrounds.

5. **Given** the codebase,
   **When** searching for raw `Colors.white`, `Colors.black`, `Colors.red`, `Colors.grey`,
   **Then** zero instances exist — all replaced with semantic theme-aware colors.

**Key changes:**
- `app_colors.dart`: `textTertiary` #9C8E84 → #7A6E64, add `terracottaDark`, fix warning/success/info dark variants
- `app_theme.dart`: Fix dark theme `contentTextStyle`, `bodySmall`, `labelMedium`, `onPrimary`, `onSecondary`
- `buttons.dart`: Fix SuccessButton foreground to white
- All files with raw `Colors.*`: Replace with semantic alternatives

---

## Story 3: Screen-by-Screen Theme Migration

As a user,
I want every screen to look correct in both light and dark mode,
so that there are no broken or unreadable screens regardless of my theme preference.

**Acceptance Criteria:**

1. **Given** any screen in the app,
   **When** the theme mode is toggled between light and dark,
   **Then** all text, backgrounds, icons, and borders use appropriate theme-aware colors.

2. **Given** the 21 files with hardcoded `AppColors.*` references,
   **When** all references are migrated,
   **Then** zero direct `AppColors.textPrimary`, `AppColors.cream`, `AppColors.beige`, etc. references remain in feature files.

3. **Given** Cook Mode,
   **When** the app is in light mode,
   **Then** Cook Mode still displays in its intentional dark theme via `Theme()` override.

4. **Given** all screens,
   **When** tested in both modes on a real device,
   **Then** no screen shows cream text on white backgrounds or dark text on dark backgrounds.

**Migration mapping:**
| AppColors constant | Theme replacement |
|---|---|
| `textPrimary` | `colorScheme.onSurface` |
| `textSecondary` | `colorScheme.onSurfaceVariant` |
| `cream` / `warmWhite` | `colorScheme.surface` |
| `beige` | `colorScheme.surfaceContainerHighest` |
| `chocolate` | `colorScheme.primary` |
| `hazelnut` | `colorScheme.secondary` |
| `border` | `colorScheme.outline` |
| `divider` | `colorScheme.outlineVariant` |

**Priority order:**
1. `recipe_card.dart` (17 refs — visible on home screen)
2. `calendar_screen.dart` (23 refs — main tab)
3. `shopping_list_screen.dart` + cart widgets (~70 refs — entire shopping flow)
4. Shared buttons: `PillButton`, `CircleIconButton`, `DangerButton`, `SuccessButton`
5. `sort_chips.dart`, `meal_filter_bar.dart`
6. Remaining screens
7. `cook_mode_screen.dart` — wrap in `Theme(data: AppTheme.dark, child: ...)`

---

## Story 4: Typography Personalization (Libre Baskerville + Inter / Sora)

As a user,
I want to choose my preferred font style for the app,
so that I can personalize the reading experience to my taste.

**Acceptance Criteria:**

1. **Given** the Profile screen,
   **When** the user opens Appearance settings,
   **Then** they see a "Font Style" option with two choices:
   - **Classic** — Libre Baskerville (headings) + Inter (body)
   - **Modern** — Sora (headings + body)

2. **Given** the user selects a font style,
   **When** the selection is saved,
   **Then** the entire app immediately reflects the chosen fonts and the preference persists.

3. **Given** the app starts for the first time,
   **When** no font preference has been set,
   **Then** the app defaults to "Classic" (Libre Baskerville + Inter).

4. **Given** either font option,
   **When** viewing recipe titles, ingredient lists, step instructions, section headers,
   **Then** text is readable, properly sized, and aesthetically consistent.

5. **Given** the codebase,
   **When** searching for direct `GoogleFonts.playfairDisplay()` calls,
   **Then** zero instances remain — all replaced with `Theme.of(context).textTheme.*` references.

**Key changes:**
- Modify `app/lib/providers/theme_mode_provider.dart` → extend to include font preference
- Modify `app/lib/core/theme/app_theme.dart` → create TextTheme builders for both pairings
- Modify `app/lib/features/profile/profile_screen.dart` → add Font Style toggle
- Add `google_fonts` entries or bundle font assets in `pubspec.yaml`
- Refactor 6 screens with direct `GoogleFonts.playfairDisplay()` calls to use theme

**Font details:**
- **Classic**: `GoogleFonts.libreBaskerville()` (display/headline/title) + `GoogleFonts.inter()` (body/label)
- **Modern**: `GoogleFonts.sora()` for all text levels (weight differentiation only)

---

## Story 5: Sharing UX Overhaul

As a user,
I want to share recipes, recipe books, and shopping lists with minimal taps using native iOS sharing,
so that sharing feels quick, natural, and works across any messaging app or social platform.

**Acceptance Criteria:**

1. **Given** a recipe detail screen,
   **When** the user looks at the AppBar,
   **Then** they see a share icon as a primary action (not buried in overflow menu).

2. **Given** the user taps the share icon on a recipe,
   **When** the share action fires,
   **Then** a link is generated and the iOS native share sheet opens immediately (1 tap total).

3. **Given** a recipe book detail screen,
   **When** the user is an owner or editor,
   **Then** they see a share icon in the AppBar that opens the iOS share sheet with an invite link (2 taps total vs current 5-6).

4. **Given** a shopping list,
   **When** the user taps share,
   **Then** a deep link is generated and shared via iOS share sheet (replacing the manual 6-char code dialog).

5. **Given** any `Share.share()` call,
   **When** running on iPad,
   **Then** it includes `sharePositionOrigin` to prevent crashes.

6. **Given** the codebase,
   **When** reviewing sharing logic,
   **Then** a unified `ShareService` handles all share operations consistently.

**Key changes:**
- `recipe_detail_screen.dart`: Add share IconButton to AppBar actions, merge two share flows into one, remove `_ShareLinkSheet`
- `recipe_book_detail_screen.dart`: Add share IconButton for owners/editors
- `shopping_list_screen.dart`: Replace code-based sharing with deep link + share sheet
- Create `app/lib/services/share_service.dart` for unified sharing logic
- Fix all `Share.share()` calls with `sharePositionOrigin` for iPad safety
