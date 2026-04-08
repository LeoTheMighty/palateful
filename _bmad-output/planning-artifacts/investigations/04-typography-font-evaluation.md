# Investigation 04: Typography & Font Evaluation

**Date:** 2026-03-22
**Status:** Complete
**Trigger:** User pain point — current font choices feel uncertain; desire to evaluate alternatives systematically

---

## Executive Summary

Palateful currently uses **Playfair Display** (Google Fonts) for display, headline, and titleLarge text styles, with the **system sans-serif** for all body, label, and smaller title text. While this creates a clear hierarchy, Playfair Display has some drawbacks for a kitchen/recipe app: its high-contrast thick-thin strokes can feel rigid on mobile, it renders heavy at smaller sizes, and the system sans-serif body text — while safe — provides no brand personality.

This investigation analyzes the current setup, researches typography best practices for food/recipe apps, and presents **9 alternative font pairings** alongside the current fonts in an interactive HTML comparison file. The top recommendation is **DM Serif Display + DM Sans** — a matched type family with organic warmth that excels at recipe content readability.

---

## Current State Analysis

### Font Configuration

**File:** `app/lib/core/theme/app_theme.dart`

| Text Style Level | Font | Weight | Size | Usage Context |
|---|---|---|---|---|
| displayLarge | Playfair Display | 700 | 36px | Hero/splash text |
| displayMedium | Playfair Display | 700 | 28px | Large section headers |
| displaySmall | Playfair Display | 600 | 24px | Section headers |
| headlineLarge | Playfair Display | 700 | 32px | Screen titles |
| headlineMedium | Playfair Display | 600 | 28px | Onboarding headers |
| headlineSmall | Playfair Display | 600 | 24px | Recipe titles on cards |
| titleLarge | Playfair Display | 600 | 22px | "Ingredients", "Steps" section headers |
| titleMedium | System sans-serif | 600 | 16px | Card subtitles, dialog titles |
| titleSmall | System sans-serif | 600 | 14px | Small headers |
| bodyLarge | System sans-serif | 400 | 16px | Recipe instructions, descriptions |
| bodyMedium | System sans-serif | 400 | 14px | Ingredient text, notes |
| bodySmall | System sans-serif | 400 | 12px | Timestamps, metadata |
| labelLarge | System sans-serif | 600 | 14px | Button text |
| labelMedium | System sans-serif | 500 | 12px | Chip labels, secondary labels |
| labelSmall | System sans-serif | 500 | 11px | Tiny metadata |

### How Fonts Are Applied

- **Theme-level:** The `TextTheme` in `app_theme.dart` defines all styles for both light and dark modes. Dark mode uses identical fonts with `warmIvory` (#F5ECD7) color instead of `textPrimary` (#2D2420).
- **Direct `GoogleFonts.playfairDisplay()` calls:** Found in 6 additional files beyond the theme — `home_screen.dart`, `cart_screen.dart`, `onboarding_welcome_screen.dart`, `onboarding_start_screen.dart`, `profile_screen.dart`, and `notification_preferences_screen.dart`. These override the theme textStyle with explicit Playfair Display calls.
- **Cook mode screen:** Uses hard-coded `TextStyle` with no font family specified (falls back to system default). Step text is rendered at 24px for readability while cooking.
- **No bundled font assets:** All fonts come from the `google_fonts` package (v6.2.1), which downloads and caches fonts at runtime.
- **AppBar title:** Uses `fontFamily: 'System'` explicitly in both light and dark themes.

### Current Issues

1. **Playfair Display's high contrast** (thick vs. thin strokes) can cause rendering issues at smaller sizes on lower-density screens and can look heavy/rigid compared to more organic serif options.
2. **System sans-serif for body text** is readable but generic — it provides no brand differentiation and varies across Android/iOS (SF Pro vs. Roboto).
3. **Inconsistent font application:** Some screens call `GoogleFonts.playfairDisplay()` directly instead of using the theme's textTheme, which means a font change requires updating both the theme and individual screen files.
4. **No optical sizing optimization:** Playfair Display was not designed with optical sizing in mind. Modern variable fonts (Fraunces, Source Serif 4) adjust letterforms based on size for better readability.
5. **Runtime font loading:** Using `google_fonts` means fonts download on first use. A bundled approach (font assets in pubspec.yaml) would eliminate the initial loading flash.

---

## Research Findings

### What Works for Recipe/Food Apps

**Readability is paramount.** Recipe apps have a unique constraint: users read instructions step-by-step while cooking, often with wet or messy hands, at arm's length, and in varying lighting. This demands:

- **Body text at 15-16px minimum** with generous line height (1.5-1.7x)
- **Clear distinction between ingredient quantities and names** (weight contrast or color)
- **Step numbers that are instantly scannable** (not lost in the text flow)
- **Forgiving x-height** — fonts with taller lowercase letters are easier to scan

**Personality through headings, reliability in body.** The best recipe apps use an expressive heading font to establish brand personality (warmth, craft, trust) while keeping body text in a highly readable, neutral typeface.

**Warm > Clinical.** For food content, typefaces with slightly organic, calligraphic, or humanist qualities outperform geometric or monoline designs. Subtle curves and stroke variation subconsciously signal "handmade" and "artisanal."

### Competitive Landscape

| App | Heading Font | Body Font | Approach |
|---|---|---|---|
| **Paprika** | System serif | System sans | Conservative, system-native |
| **Mela** | Custom geometric sans | Same family | Clean, modern, single-family |
| **Crouton** | Bold sans-serif | Light sans-serif | Minimal, weight-only contrast |
| **Pestle** | Serif (similar to Georgia) | System sans | Traditional editorial |
| **NYT Cooking** | Custom Cheltenham derivative | Franklin Gothic | Classic editorial pairing |
| **Bon Appetit** | Custom serif | Trade Gothic | Magazine-grade pairing |
| **Yummly** | Bold sans-serif | Regular sans-serif | App-native, modern |

**Key takeaway:** Premium recipe experiences (NYT Cooking, Bon Appetit) lean editorial with serif headings. Modern app-first experiences (Mela, Yummly) go all-sans. Palateful's warm cream/chocolate palette aligns naturally with the editorial approach.

### Font Pairing Theory Applied to Food

1. **Matched superfamilies** (DM Serif + DM Sans, Source Serif + Source Sans) offer guaranteed harmony because they share metrics and design DNA.
2. **Contrast principle:** Heading and body should differ in classification (serif vs. sans) OR in weight/width, but not in overall "feel." Both should be warm or both cool.
3. **x-height matching:** Pairings where the serif and sans have similar x-heights look more unified. DM Serif Display and DM Sans have near-identical x-heights.
4. **Variable fonts** are increasingly preferred because they reduce file size (one file for all weights) and enable optical sizing.

### Accessibility Considerations

- **WCAG AA** requires 4.5:1 contrast ratio for normal text, 3:1 for large text. Palateful's text colors on cream background pass for all current sizes.
- **Dyslexia-friendly characteristics:** Open letterforms (e.g., DM Sans, Source Sans), distinguishable l/I/1 characters, consistent spacing.
- **Low vision:** Avoid ultra-thin weights for body text. Minimum 400 weight for body, 600+ for headings.
- **Dynamic Type / Accessibility scaling:** All font choices should scale gracefully. Avoid fonts that collapse at 2x scaling.

---

## Recommended Font Pairings

### Tier 1: Strong Recommendations

#### 1. DM Serif Display + DM Sans
**Top pick.** Both fonts come from Colophon Foundry's DM type system. DM Serif Display has softer, more organic curves than Playfair Display — it feels warmer and more approachable. DM Sans is one of the best reading sans-serifs available: clean, open letterforms with excellent x-height. The matched metrics mean headings and body feel like they belong together.

*Why for Palateful:* The organic warmth aligns perfectly with the cream/chocolate/hazelnut color palette. It feels like a cookbook you'd actually want to cook from.

#### 2. Lora + Source Sans 3
**Runner-up.** Lora's subtle calligraphic influence gives headings an artisanal quality without being decorative. Source Sans 3 (Adobe) is a workhorse — designed for extended reading with excellent hinting and rendering. This pairing is a staple of food blogs and digital cookbook layouts.

*Why for Palateful:* If you want a font with slightly more personality than DM Serif Display, Lora's brushstroke-inspired curves are distinctly "food."

#### 3. Fraunces + Plus Jakarta Sans
**Most distinctive.** Fraunces is a variable "old-style" serif with a deliberately wonky, handcrafted character. It's playful and modern while still being a proper serif. Plus Jakarta Sans has soft geometric shapes that complement the irregularity. This pairing screams "premium artisan" and would give Palateful a very distinctive identity.

*Why for Palateful:* If you want Palateful to feel less "traditional cookbook" and more "modern food brand," this is the pick. The variable font includes optical sizing so it looks refined at any size.

### Tier 2: Solid Alternatives

#### 4. Bitter + Nunito Sans
**Most practical.** Bitter was literally designed for comfortable screen reading — it's a slab-serif that excels on mobile. Nunito Sans has rounded terminals that feel friendly. This is a "kitchen-first" choice: less elegant but more utilitarian.

#### 5. Crimson Pro + Outfit
**Lightest touch.** Crimson Pro is a delicate, lighter serif that wouldn't change the overall "feel" much from Playfair but would solve the heaviness problem. Outfit is a clean modern geometric. Good if you want refinement without drama.

### Tier 3: Departures

#### 6. Bricolage Grotesque + DM Sans
**All sans-serif.** If you want to move away from serif headings entirely, Bricolage Grotesque has enough personality in its variable optical sizing to carry the heading role without a serif. Feels modern and app-native.

#### 7. Sora (single family)
**Minimalist.** Using one geometric sans across everything, relying on weight contrast alone. Clean, modern, but loses the editorial warmth that the current design has.

---

## Font Comparison Guide

An interactive HTML file has been created at:

**`_bmad-output/planning-artifacts/investigations/font-comparison.html`**

Open this file in a browser to see all 10 options (current + 9 alternatives) rendering identical recipe content (Honey-Glazed Salmon with Roasted Vegetables). The file includes:

- **Dark mode toggle** to evaluate both light and dark themes
- **Jump navigation** to quickly hop between pairings
- **Summary comparison table** at the bottom with readability/recipe-fit ratings
- **Full recipe content** for each pairing: title, description, metadata strip, ingredient list with quantities, numbered steps, and a cook's note
- Uses Palateful's actual color palette (cream, chocolate, hazelnut, terracotta)

---

## Implementation Considerations

### Required Changes

1. **`app/lib/core/theme/app_theme.dart`** — Update `TextTheme` in both `light` and `dark` getters. Replace `GoogleFonts.playfairDisplay()` calls with the chosen heading font, and optionally replace system sans-serif with a named body font.

2. **Direct `GoogleFonts` calls in screens** — 6 files call `GoogleFonts.playfairDisplay()` directly and must be updated:
   - `app/lib/features/home/home_screen.dart`
   - `app/lib/features/cart/cart_screen.dart`
   - `app/lib/features/onboarding/onboarding_welcome_screen.dart`
   - `app/lib/features/onboarding/onboarding_start_screen.dart`
   - `app/lib/features/profile/profile_screen.dart`
   - `app/lib/features/profile/notification_preferences_screen.dart`

3. **Consider bundling fonts** — For production, switching from `google_fonts` runtime download to bundled assets (in `pubspec.yaml` `fonts:` section) eliminates the first-load font flash. Download the `.ttf`/`.woff2` files and place in `app/fonts/`.

4. **pubspec.yaml** — If bundling: add font family declarations. If keeping `google_fonts`: no pubspec changes needed (the package supports all recommended fonts).

### Risk Factors

- **Font file size:** Each Google Font weight is ~20-40KB. Bundling 2 families at 4 weights each adds ~160-320KB to the app binary. Negligible for a modern app.
- **Platform rendering differences:** Some serifs render slightly differently on iOS (Core Text) vs. Android (FreeType). Test on both. DM Serif Display and Lora render consistently across platforms.
- **Existing hardcoded styles:** Cook mode screen uses hardcoded `TextStyle` without font family — these will inherit from the theme's `DefaultTextStyle`, which may or may not apply the chosen body font depending on widget tree. Should be tested.

---

## Estimated Complexity

**Theme update only (keep google_fonts):** 2-3 hours
- Update `app_theme.dart` text theme
- Update 6 screen files with direct GoogleFonts calls
- Visual QA across key screens (home, recipe detail, cook mode, onboarding, profile)

**Theme update + bundle fonts as assets:** 4-5 hours
- Above + download font files, configure pubspec.yaml, test offline behavior

**Theme update + refactor all direct GoogleFonts calls to use theme textTheme:** 5-7 hours
- Above + replace all 27 direct `GoogleFonts.playfairDisplay()` calls with `Theme.of(context).textTheme.*` references, ensuring future font changes only require updating the theme file.
