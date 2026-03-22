# Story UI.4: Typography Personalization (Libre Baskerville + Inter / Sora)

Status: complete

## Story

As a user,
I want to choose between two font styles — Classic or Modern,
so that I can personalize the app's reading experience to my taste.

## Acceptance Criteria

1. Profile Appearance section includes "Font Style" with two options:
   - **Classic** — Libre Baskerville (headings) + Inter (body) — *default*
   - **Modern** — Sora (all text, weight differentiation)
2. Selecting a font style immediately updates the entire app
3. Font preference persists across restarts via SharedPreferences
4. Both font options render correctly in recipe titles, ingredient lists, step instructions, section headers, navigation labels
5. Zero direct `GoogleFonts.playfairDisplay()` calls remain — all screens use `Theme.of(context).textTheme.*`
6. Fonts work correctly in both light and dark mode

## Tasks / Subtasks

- [x] Task 1: Add font preference state (AC: #2, #3)
  - [x] Extend theme provider in `app/lib/providers/theme_mode_provider.dart` to include `fontStyle` (enum: `classic`, `modern`)
  - [x] Persist to SharedPreferences key `font_style`
  - [x] Default to `classic`
  - [x] Expose as `fontStyleProvider`

- [x] Task 2: Create TextTheme builders for both pairings (AC: #1, #4)
  - [x] Modify `app/lib/core/theme/app_theme.dart`
  - [x] Create `_classicTextTheme()`:
    - Display/Headline/TitleLarge: `GoogleFonts.libreBaskerville()`
    - TitleMedium/Small, Body, Label: `GoogleFonts.inter()`
  - [x] Create `_modernTextTheme()`:
    - All levels: `GoogleFonts.sora()` with weight differentiation
    - Display: weight 700, Headline: 600, Title: 600, Body: 400, Label: 500
  - [x] Wire `fontStyle` preference into `AppTheme.light` and `AppTheme.dark` getters

- [x] Task 3: Add Font Style toggle to Profile (AC: #1)
  - [x] Modify `app/lib/features/profile/profile_screen.dart`
  - [x] Add "Font Style" option in the Appearance section (below theme toggle from Story 1)
  - [x] Show preview text in each font so user can see before selecting
  - [x] Options with labels: "Classic (Serif)" and "Modern (Sans-Serif)"

- [x] Task 4: Refactor direct GoogleFonts.playfairDisplay() calls (AC: #5)
  - [x] `app/lib/features/home/home_screen.dart` → use `Theme.of(context).textTheme.displayLarge` or equivalent
  - [x] `app/lib/features/cart/cart_screen.dart` → same
  - [x] `app/lib/features/onboarding/onboarding_welcome_screen.dart` → same
  - [x] `app/lib/features/onboarding/onboarding_start_screen.dart` → same
  - [x] `app/lib/features/profile/profile_screen.dart` → same
  - [x] `app/lib/features/profile/notification_preferences_screen.dart` → same
  - [x] Grep to verify: `grep -r "playfairDisplay" app/lib/` returns zero results

- [x] Task 5: Update pubspec.yaml (AC: #4)
  - [x] Ensure `google_fonts` package is listed in dependencies
  - [x] Consider bundling font files for offline/first-load reliability:
    - Download Libre Baskerville (regular, bold, italic)
    - Download Inter (400, 500, 600, 700)
    - Download Sora (400, 500, 600, 700)
    - Add to `fonts:` section in pubspec.yaml
  - [x] If bundling, update TextTheme builders to use asset fonts

- [x] Task 6: Visual QA (AC: #4, #6)
  - [x] Test Classic font in light mode across all screens
  - [x] Test Classic font in dark mode across all screens
  - [x] Test Modern font in light mode across all screens
  - [x] Test Modern font in dark mode across all screens
  - [x] Verify Cook Mode text is readable with both fonts

## Dev Notes

- Libre Baskerville is a web-optimized Baskerville — timeless and trustworthy, excellent readability
- Inter is considered the best UI typeface available — tabular numbers, case-sensitive forms
- Sora is geometric with excellent readability at all sizes — single-family weight differentiation approach
- Playfair Display is being fully replaced — no backward compatibility needed
- The `google_fonts` package handles runtime font loading but consider bundling for better UX
- Font comparison preview is available at: `_bmad-output/planning-artifacts/investigations/font-comparison.html` (pairings #5 and #9)

### References

- [Investigation: 04-typography-font-evaluation.md]
- [Font Comparison HTML: font-comparison.html — Pairings 5 (Libre Baskerville + Inter) and 9 (Sora)]
