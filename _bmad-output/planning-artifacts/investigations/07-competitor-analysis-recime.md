# 07 - Competitor Analysis: Recime & Recipe App Landscape

> **Date:** March 2026
> **Focus:** Recime deep dive + competitive landscape for recipe management apps
> **Goal:** Identify what Recime does best (especially import flow), map the competitive feature landscape, and extract actionable recommendations for Palateful.

---

## Executive Summary

Recime has emerged as the most popular recipe management app (1M+ Google Play downloads, 4.81-star iOS rating from 200K+ reviews) by solving one problem exceptionally well: **getting recipes from where people actually find them (social media, screenshots, websites) into a clean, organized format with minimal friction**. Their import flow is the gold standard -- one-tap share sheet import from TikTok, Instagram, YouTube, Pinterest, and any website, plus camera/screenshot OCR import. This is the feature that drives their growth.

However, Recime has meaningful weaknesses: a basic shopping list that does not merge duplicates, a meal planner disconnected from the shopping list, limited sorting/filtering, no pantry tracking, and no collaborative household features. These gaps represent significant opportunities for Palateful.

The competitive landscape is fragmented by platform and use case:
- **Pestle** leads in video-to-text AI transcription and hands-free cooking (voice commands)
- **Crouton** won the 2024 Apple Design Award for its face-gesture cooking navigation
- **Mela** is the design benchmark for Apple-native elegance (one-time purchase, iCloud sync)
- **Paprika** remains the power user's choice with deep features including pantry tracking
- **CopyMeThat** is the cross-platform budget option
- **Whisk/Samsung Food** leads in smart shopping list merging and grocery retailer integration

**Palateful's differentiation opportunity:** No competitor combines pantry-aware recipe suggestions, household collaboration (shared recipe books, shared shopping lists), AI-powered ingredient intelligence, and a great import flow in one app. This is Palateful's lane.

---

## Recime Deep Dive

### Company & Traction

- **Downloads:** 1M+ on Google Play, prominent on iOS App Store
- **Rating:** 4.81 stars from 200K+ iOS reviews; 4.7 stars from 31.8K+ Google Play reviews
- **Funding:** $500K pre-Seed (reported by Startup Daily)
- **Pricing:** Free tier (5 imports/week, recipes are public) | Premium at $59.99/year (unlimited imports, nutrition, private recipes)
- **Platforms:** iOS, Android

### Feature Set

| Feature | Implementation | Quality |
|---------|---------------|---------|
| URL import (websites) | Share sheet + in-app browser | Excellent |
| Social media import (TikTok, Instagram, YouTube, Pinterest, Facebook) | AI-powered extraction from video captions/audio | Excellent |
| Photo/screenshot import | Camera + camera roll, multi-image support | Very Good |
| Text paste import | Clipboard paste with auto-parsing | Good |
| Cross-app import | Paprika, Notes, Google Docs, Notion, Evernote | Good |
| Cookbook organization | Custom cookbooks, tags, meal type/cuisine/diet filters | Good |
| Meal planning | Weekly calendar, breakfast/lunch/dinner slots | Basic |
| Shopping list | Categorized by aisle (Produce, Dairy, Pantry) | Basic |
| Nutrition calculation | Calories, protein, carbs, fats per recipe | Good (Premium) |
| Serving scaler | Adjust serving size, auto-recalculate ingredients | Good |
| Unit conversion | Metric/Imperial toggle | Good |
| Cook mode | Screen-always-on, step-by-step, one-tap timers | Good |
| Recipe sharing | Email, SMS, WhatsApp, Messenger, AirDrop | Basic |
| Cookbook collaboration | Invite others to collaborate on cookbooks | Basic |
| Pantry tracking | Not available | N/A |
| Household/family features | Shared account login only | Minimal |

### What Recime Does Best

**1. Import Flow (The Killer Feature)**
Recime's import experience is the reason people choose this app. The flow is:

1. **Share Sheet Integration (One Tap):** User sees a recipe on TikTok/Instagram/any browser, taps Share, taps Recime icon. Done. The recipe appears in their library within seconds. Users can pin Recime to the top of their share sheet for even faster access.

2. **Multi-Source AI Extraction:** The AI handles wildly inconsistent content -- TikTok captions with ingredients buried in hashtags, Instagram Reels with no text, YouTube cooking videos with narrated-only instructions. It extracts a structured recipe (title, ingredients list, method steps) from this chaos.

3. **Camera Import:** Tap +, choose Camera, snap a photo of a printed cookbook page or handwritten recipe card. Multi-image support means you can capture a recipe that spans multiple pages.

4. **Text Paste:** Copy any recipe text from anywhere (email, message, PDF), open Recime, tap +, paste. Auto-parsed into structured format.

5. **Cross-App Migration:** Direct import from Paprika, Apple Notes, Google Docs, Notion, Evernote -- reducing switching costs for users migrating from other tools.

**Why it works from a UX perspective:**
- Zero context switching -- import happens from wherever you found the recipe
- One-tap flow (share sheet) means capture is faster than bookmarking
- AI handles the messy parsing so the user never has to manually type ingredients
- Immediate gratification -- recipe appears formatted and ready
- Multiple fallback paths (URL, camera, paste, manual) cover every scenario

**2. Visual Design Language**
- High-impact food photography front and center
- Friendly, rounded typography ("chubby" fonts)
- Vibrant, warm color palette
- Recipe cards emphasize the photo above all else
- Clean, uncluttered layouts despite feature density

**3. Nutrition & Scaling**
- Auto-calculated macros (calories, protein, carbs, fat) for any recipe
- One-tap serving scaler that recalculates all ingredient quantities
- Unit conversion toggle (metric/imperial) -- useful for international users

### What Recime Does Poorly

**1. Shopping List Gaps**
- Does NOT merge duplicate ingredients across recipes (if two recipes need onions, you get two separate onion entries)
- Cannot customize or rename aisle categories
- Meal planner does NOT auto-connect to shopping list -- users must manually add recipes to their list
- No shared shopping lists for households

**2. Limited Organization & Discovery**
- No alphabetical sorting of recipes
- No sort by newest/oldest
- Limited filtering options (users have repeatedly requested this)
- No recipe rating/favorites system visible in reviews
- Search is basic text match only

**3. No Pantry Tracking**
- Cannot track what ingredients you have at home
- No "what can I make?" suggestions based on pantry
- No expiration tracking
- This is a major gap for a kitchen management app

**4. Weak Collaboration**
- No household concept -- sharing is just "log into the same account"
- No per-user preferences within a shared account
- No collaborative meal planning
- Recipe sharing is one-way (send via messaging apps)

**5. Performance & Stability**
- Import can take 10+ seconds with loading spinner (noticeable delay)
- Users report app crashes, especially after updates
- Some imports fail silently or with unhelpful error messages

**6. Aggressive Monetization**
- Free tier limited to 5 imports/week AND all free recipes are public (privacy concern)
- $59.99/year is on the higher end of recipe app pricing
- Users report feeling "tricked" by hitting limits without upfront warning

---

## Recime Import Flow Analysis (Detailed Breakdown)

### Flow 1: Share Sheet Import (Primary Flow)

```
User browses TikTok/Instagram/Safari
    |
    v
Taps "Share" on content
    |
    v
Taps Recime icon in share sheet (pinned to top if configured)
    |
    v
[10-15 second processing]
AI extracts recipe from:
  - Video captions (TikTok/Instagram)
  - Audio transcription (video content)
  - Webpage structured data (JSON-LD, schema.org)
  - Webpage scraping (fallback)
    |
    v
Recipe appears in library:
  - Title
  - Ingredient list (structured)
  - Method steps (numbered)
  - Photo/thumbnail
  - Source link preserved
    |
    v
User can edit/refine if needed (optional)
```

**UX Strengths:**
- Friction is near zero -- user never leaves the source app
- AI handles 90%+ of the formatting work
- Source link preserved for reference
- Photo automatically captured

**UX Weaknesses:**
- 10-15 second wait with no progress feedback (just a spinner)
- No confidence indicator -- user does not know if AI struggled
- No inline correction flow -- must open recipe to edit
- Occasional silent failures with unhelpful error messages

### Flow 2: Camera/Photo Import

```
User opens Recime
    |
    v
Taps "+" button
    |
    v
Selects "Camera" option
    |
    v
Choose: Take Photo | Choose from Library
    |
    v
Can select MULTIPLE images (multi-page recipes)
    |
    v
AI OCR processes image(s)
    |
    v
Structured recipe appears for review
    |
    v
User edits/confirms and saves
```

**UX Strengths:**
- Multi-image support is thoughtful (cookbook recipes often span pages)
- Works on handwritten recipe cards (OCR + AI)
- Handles printed cookbooks, magazine cutouts, screenshots

**UX Weaknesses:**
- Limited to one photo per recipe on free plan
- OCR accuracy varies with handwriting quality
- No real-time preview of what the AI is extracting

### Flow 3: Text Paste Import

```
User copies recipe text from any source
    |
    v
Opens Recime, taps "+"
    |
    v
Selects "Paste Text"
    |
    v
Pastes clipboard content
    |
    v
AI parses into structured format
    |
    v
User reviews, edits, saves
```

### Flow 4: Cross-App Migration

```
User exports from Paprika/Notes/Notion/etc.
    |
    v
Opens Recime import
    |
    v
Selects source app
    |
    v
Bulk import with mapping
```

### What Makes the Import Flow "Super Hot"

1. **Meet users where they are:** The share sheet integration means users import from their natural browsing context. They do not have to copy a URL, switch apps, paste it, and wait. It is one tap.

2. **AI does the dirty work:** Recipe content online is wildly inconsistent -- TikTok captions, Instagram carousel text, blog posts buried in SEO fluff, handwritten cards. Recime's AI normalizes all of this into a clean format.

3. **Multiple input channels:** URL, camera, paste, cross-app migration -- every possible way a user might encounter a recipe is covered.

4. **Immediate utility:** The imported recipe is immediately usable -- you can cook from it, add it to a meal plan, or generate a shopping list right away.

5. **Low learning curve:** The "+" button with clear options (URL, Camera, Paste, Manual) is self-explanatory. No tutorial needed.

---

## Competitor Comparison Matrix

### Feature-by-Feature Comparison

| Feature | Recime | Pestle | Crouton | Mela | Paprika | CopyMeThat | Whisk/Samsung Food |
|---------|--------|--------|---------|------|---------|------------|-------------------|
| **IMPORT** | | | | | | | |
| URL/web import | Yes (share sheet) | Yes | Yes | Yes (live preview) | Yes (in-app browser) | Yes (Chrome ext.) | Yes |
| TikTok/Instagram video import | Yes (AI) | Yes (AI, on-device) | No | No | No | No | Yes |
| Photo/OCR import | Yes (multi-image) | Yes | Yes (AI) | Yes (text recognition) | No | No | Yes |
| Text paste import | Yes | Yes | No | Yes | Yes | Yes | Yes |
| Cross-app migration | Paprika, Notes, Notion | Paprika, Crouton, Mela | Paprika | Paprika | Various formats | No | No |
| Bulk import (CSV/spreadsheet) | No | No | No | No | Yes | No | No |
| **ORGANIZATION** | | | | | | | |
| Custom collections/cookbooks | Yes | Yes | Yes | Yes (folders) | Yes (categories) | Yes (collections) | Yes |
| Tags | Yes | Yes | Yes | Yes | Yes | No | No |
| Search | Basic text | Good | Good | Good | Advanced (multi-field) | Basic | Basic |
| Sort/filter options | Limited | Good | Good | Good | Excellent | Basic | Basic |
| **COOKING** | | | | | | | |
| Cook mode (step-by-step) | Yes (screen-on) | Yes (screen-on, large text) | Yes (screen-on) | Yes (large font) | Yes | No | No |
| Voice control | No | Yes (hands-free) | No | No | No | No | No |
| Face gesture navigation | No | No | Yes (blink/mouth) | No | No | No | No |
| In-recipe timers | Yes (one-tap) | Yes (auto-detect) | Yes (auto-detect) | Yes (Live Activities) | Yes | No | No |
| Serving scaler | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Unit conversion | Yes | No | No | No | Yes | No | Yes |
| **PLANNING** | | | | | | | |
| Meal planning calendar | Weekly | Yes | Weekly | Calendar.app integration | Yes | Weekly/monthly | 2-week |
| **SHOPPING** | | | | | | | |
| Shopping list | Basic (by aisle) | Basic | Reminders.app sync | Reminders.app sync | Yes (by aisle, merge) | Yes | Smart (merge + retail) |
| Duplicate merging | No | No | Via Reminders | Via Reminders | Yes | Yes | Yes |
| Grocery retailer integration | No | No | No | No | No | No | Yes (29 retailers) |
| Shared shopping list | No | No | Via Reminders sharing | Via Reminders sharing | Yes (sync) | No | Yes |
| **HOUSEHOLD** | | | | | | | |
| Pantry tracking | No | No | No | No | Yes (with expiry) | No | Yes (AI vision) |
| Multi-user household | Shared login only | No | No | No | Sync via cloud | No | Yes |
| Collaborative cookbooks | Basic | No | No | No | No | No | No |
| **NUTRITION** | | | | | | | |
| Auto nutrition calc | Yes (Premium) | Yes | No | No | No | No | Yes |
| **AI FEATURES** | | | | | | | |
| AI recipe extraction | Yes | Yes (on-device) | Yes | No | No | No | Yes |
| AI recipe generation | No | No | No | No | No | No | Yes |
| AI suggestions ("what to cook") | No | No | No | No | No | No | Yes |
| **PRICING** | | | | | | | |
| Free tier | 5/week, public | Limited saves | Free | Free (limited) | N/A | Free (ads) | Free (limited) |
| Paid price | $59.99/yr | Flexible (monthly/yearly/lifetime) | One-time ~$10 | One-time $5.99 | One-time ~$5/platform | $25 lifetime | $59.99/yr |
| **PLATFORMS** | | | | | | | |
| iOS | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Android | Yes | No | No | No | Yes | Yes | Yes |
| Web | No | No | No | No | Yes | Yes | Yes |
| macOS | No | Yes | Yes | Yes | Yes | No | Yes |

### Competitor Spotlights

#### Pestle -- Best for: Video recipe conversion + hands-free cooking
- **Standout:** On-device AI processes TikTok/Instagram videos in under 1 second (vs Recime's 10-15 seconds). Voice command cooking ("next step", "read ingredients", "set timer 10 minutes").
- **Weakness:** Apple-only. No Android or web. Limited community/sharing features.
- **Pricing:** Free tier + monthly/yearly/lifetime options (flexible).

#### Crouton -- Best for: Cooking experience design
- **Standout:** 2024 Apple Design Award winner. Face gesture navigation in cook mode -- wink right eye to advance, wink left to go back, open mouth to show ingredients. Auto-detected timers in recipe steps. Grocery list syncs with Apple Reminders (accessible even without Crouton installed).
- **Weakness:** Apple-only. No social media video import. Smaller user base.
- **Pricing:** One-time purchase (~$10).

#### Mela -- Best for: Apple design purists
- **Standout:** Live preview during web import (see exactly how recipe will look before saving). iCloud sync (no account needed). Calendar.app integration for meal planning. Reminders.app for grocery list. Timer with iOS Live Activities support. Most beautiful UI in the category.
- **Weakness:** Apple-only. No social media import. No AI features. No nutrition tracking.
- **Pricing:** One-time $5.99 per platform (best value in category).

#### Paprika -- Best for: Power users + pantry management
- **Standout:** The most feature-complete recipe manager. Pantry tracking with expiry dates and purchase tracking. Advanced search across multiple fields. Cross-platform (iOS, Android, Mac, Windows, web). In-app browser for recipe clipping. Bulk import from CSV/other apps.
- **Weakness:** Dated UI (feels like 2015). No social media import. No AI features. Separate purchase per platform. No modern collaboration.
- **Pricing:** One-time ~$5 per platform.

#### CopyMeThat -- Best for: Budget cross-platform
- **Standout:** Chrome extension for one-click web clipping. Create and publish your own physical cookbook from the app. Cross-platform (iOS, Android, web). Lifetime premium at $25.
- **Weakness:** Dated design. Ads in free tier. Limited import options. No cooking mode. No AI.
- **Pricing:** Free (with ads) | $25 lifetime.

#### Whisk/Samsung Food -- Best for: Smart shopping + AI features
- **Standout:** Shopping list intelligently merges duplicate ingredients from multiple recipes. Integration with 29 online grocery retailers for direct checkout. AI recipe generation from fridge photo. Pantry tracking with AI vision input.
- **Weakness:** Heavy Samsung branding. Complex UI. Expensive ($59.99/yr). Push toward Samsung ecosystem.
- **Pricing:** Free (limited) | $59.99/year.

---

## Key Takeaways for Palateful

### 1. Import Flow Is Table Stakes
Every serious recipe app in 2026 has some form of smart import. Palateful's existing import system design (in `RECIPE_IMPORT_SYSTEM.md`) is architecturally sound with its tiered extraction approach (JSON-LD > site scrapers > AI fallback). But the critical UX element is **share sheet integration** -- this is how Recime wins. Users must be able to import without leaving the app where they found the recipe.

### 2. Social Media Import Is the New Battleground
The most interesting recipes are no longer on food blogs with structured schema.org data. They are in TikTok videos, Instagram Reels, and YouTube Shorts. Pestle processes these on-device in under 1 second. Recime does it in 10-15 seconds via cloud AI. Palateful needs a strategy for video recipe extraction.

### 3. Cooking Mode Differentiation Is Wide Open
Crouton won an Apple Design Award with face gestures. Pestle has voice commands. Most others just keep the screen on. There is room to innovate here -- Palateful's cook mode design (ingredient strip + step navigation) is already strong, but adding hands-free interaction would be a differentiator.

### 4. Nobody Does Pantry + Recipes + Shopping Well Together
Paprika has pantry tracking but a dated UI and no AI. Whisk/Samsung Food has AI-powered pantry but is Samsung-heavy. Recime has great import but no pantry at all. **The app that seamlessly connects "what you have" to "what you can cook" to "what you need to buy" wins the kitchen management category.** This is Palateful's biggest opportunity.

### 5. Household Collaboration Is an Underserved Need
Nearly every competitor treats the app as a single-user tool. Recime's "sharing" is just logging into the same account. Paprika syncs across devices but has no user differentiation. **Palateful's invitation system and shared recipe books/pantries/shopping lists are a genuine competitive advantage** -- this is a feature families actively ask for in reviews of other apps.

### 6. Shopping List Intelligence Matters More Than Expected
Users consistently complain about shopping lists that do not merge duplicates, cannot be reordered, and are not connected to meal plans. Whisk's smart merging + retailer integration is the benchmark. Palateful should aim for at minimum: auto-merge duplicates, connect meal plan to shopping list, and allow shared lists.

### 7. Pricing Models Are Shifting
The market is split between:
- Subscription: Recime ($59.99/yr), Whisk ($59.99/yr)
- One-time: Mela ($5.99), Paprika (~$5), Crouton (~$10)
- Lifetime: CopyMeThat ($25), Pestle (option available)

Users in reviews express strong preference for one-time purchase or lifetime options. Subscription fatigue is real. Palateful should consider a lifetime purchase option alongside any subscription.

---

## Feature Adoption Recommendations

### Must Adopt (High Impact, Proven by Competitors)

| Feature | Source | Why | Effort |
|---------|--------|-----|--------|
| **Share sheet import (iOS)** | Recime | The #1 growth driver. One-tap import from any app is essential. Without this, Palateful starts at a disadvantage. | Medium -- requires iOS share extension |
| **Social media video import (TikTok, Instagram)** | Recime, Pestle | Where recipes live now. On-device processing (Pestle approach) is faster and cheaper than cloud AI. | High -- requires video/audio AI pipeline |
| **Photo/screenshot OCR import** | Recime, Crouton | Covers printed cookbooks, handwritten cards, screenshots. Palateful already has HunyuanOCR -- leverage it. | Medium -- extend existing OCR system |
| **Smart shopping list (duplicate merging)** | Paprika, Whisk | Top user complaint about Recime. Table stakes for a kitchen management app. | Medium -- ingredient matching logic |
| **Meal plan to shopping list auto-connection** | (Gap in all competitors) | Every competitor either does this poorly or not at all. Huge UX win. | Low-Medium -- UI + data flow |

### Should Adopt (Strong Differentiators)

| Feature | Source | Why | Effort |
|---------|--------|-----|--------|
| **Hands-free cook mode (voice or gestures)** | Pestle (voice), Crouton (face) | Messy hands in kitchen is a real problem. Voice commands are more practical than face gestures. | Medium-High |
| **Auto-detected timers in recipe steps** | Crouton, Mela, Pestle | AI scans recipe text for time mentions, offers one-tap timer buttons inline. Delightful and practical. | Low -- text parsing + timer UI |
| **Nutrition auto-calculation** | Recime, Whisk | Users want this. Ties into Palateful's ingredient database with nutrition data. | Medium -- leverage ingredient DB |
| **Live import preview** | Mela | See the recipe formatted before committing. Reduces "bad import" frustration. | Low-Medium |
| **Cross-app migration (Paprika, Crouton, Mela export files)** | Pestle, Recime | Reduces switching cost. Critical for user acquisition. | Medium -- format parsing |

### Consider Adopting (Nice to Have)

| Feature | Source | Why | Effort |
|---------|--------|-----|--------|
| **AI recipe generation from pantry** | Whisk | "Snap a photo of your fridge, get recipe ideas." Fun but gimmicky. | High |
| **Grocery retailer integration** | Whisk | Direct checkout from shopping list. Impressive but complex to maintain (29 retailer APIs). | Very High |
| **Face gesture navigation** | Crouton | Won Apple Design Award but niche. Voice is more practical. | High |
| **Physical cookbook creation** | CopyMeThat | Print your digital recipes as a physical book. Surprising delight feature. | High (third-party integration) |

### Skip (Not Worth It for Palateful)

| Feature | Why Skip |
|---------|----------|
| **In-app recipe browser (Paprika style)** | Share sheet import is better UX. An in-app browser is a dated pattern. |
| **Public recipe feed/discovery** | Palateful is about YOUR kitchen, not social discovery. Stay focused. |
| **Barcode scanning for pantry** | Cooklist does this but adoption is low. Manual entry + receipt scanning is more practical. |
| **Samsung/brand ecosystem integration** | Stay independent. Do not tie to hardware vendors. |

---

## Differentiation Opportunities (Where Palateful Can Be BETTER)

### 1. Pantry-Aware Intelligence (No Competitor Does This Well)

**The gap:** Recime, Pestle, Crouton, and Mela have zero pantry tracking. Paprika tracks pantry but does not connect it to recipe suggestions. Whisk has AI pantry but is Samsung-focused.

**Palateful's play:**
- Track pantry inventory (manual entry, shopping list auto-add, receipt OCR)
- "What can I cook tonight?" shows recipes ranked by pantry ingredient coverage
- "You're missing 2 ingredients" callout on recipe cards
- Expiration alerts trigger recipe suggestions ("Use your chicken thighs before Thursday")
- Shopping list only adds what you do not already have

**This is the killer feature that ties everything together.** It transforms Palateful from a recipe box into a kitchen management system.

### 2. True Household Collaboration (Everyone Else Is Single-User)

**The gap:** Every competitor is fundamentally a single-user app. "Sharing" means either sharing a login (Recime) or sending a recipe link (everyone).

**Palateful's play:**
- Shared recipe books with per-member permissions
- Shared shopping lists with real-time sync (check off items together at the store)
- Shared pantry (roommates, couples, families know what is in the kitchen)
- Per-user dietary preferences within a household
- Invitation system already designed -- this is a first-mover advantage

### 3. AI Suggestion Agent (Proactive, Not Reactive)

**The gap:** Whisk has basic "generate a recipe" AI. No competitor has a proactive suggestion agent that learns your habits.

**Palateful's play (from BIG_ROCKS.md):**
- "You have chicken thighs expiring tomorrow. Here are 3 quick recipes."
- "It is Sunday -- want to meal prep for the week?" based on calendar
- "Based on your pantry, you can make Pasta Carbonara tonight."
- Learns from cooking history, seasonal ingredients, household preferences

### 4. Import Flow That Beats Recime

**The gap:** Recime's import takes 10-15 seconds. Pestle does on-device video processing in <1 second.

**Palateful's play:**
- Share sheet extension with progress notification (not blocking spinner)
- Tiered extraction (JSON-LD > scrapers > AI) for fastest possible resolution
- Background processing with push notification: "Your recipe is ready!"
- Import confidence score with easy inline correction
- Batch import from spreadsheets (Paprika-level power, Recime-level ease)
- Photo import leveraging existing HunyuanOCR infrastructure

### 5. Cook Mode That Respects Kitchen Reality

**The gap:** Most cook modes are just "big text, screen stays on." Crouton's face gestures are clever but impractical (blinking sensitivity, mouth detection false positives). Pestle's voice commands are the best current approach.

**Palateful's play (from BIG_ROCKS.md):**
- Horizontal ingredient strip always visible (quick reference without scrolling)
- Step navigation with progress tracking + step completion checkmarks
- Voice commands: "Next step", "Previous step", "Read ingredients", "Set timer 10 minutes"
- Detected timers with one-tap start + concurrent timer support
- "Mark all done up to here" long-press gesture
- High contrast mode for kitchen lighting
- Keep screen awake automatically

### 6. Shopping List Intelligence

**The gap:** Recime does not merge duplicates. Paprika merges but has dated UI. Whisk merges and has retailer integration but is expensive and Samsung-branded.

**Palateful's play:**
- Auto-merge duplicate ingredients across recipes (leverage ingredient database + fuzzy matching)
- Auto-populate from meal plan (the connection Recime is missing)
- Subtract pantry items (only buy what you need)
- Shared list with real-time sync for household members
- Aisle organization with customizable categories
- "Check off" items that persist across sessions

---

## Priority Recommendations

### Phase 1: Foundation (Import + Cook Mode)
**Goal:** Match Recime's import quality, exceed with cooking experience

1. **iOS Share Extension** -- Enable one-tap import from any app via share sheet
2. **Photo import with HunyuanOCR** -- Leverage existing OCR infrastructure for camera/screenshot import
3. **URL import with tiered extraction** -- JSON-LD > scrapers > AI fallback (already designed)
4. **Cook mode with ingredient strip** -- Step-by-step with always-visible ingredients, auto-detected timers
5. **Text paste import** -- Simple but covers a common use case

### Phase 2: Intelligence (Shopping + Pantry)
**Goal:** Differentiate from every competitor with connected kitchen intelligence

6. **Smart shopping list** -- Duplicate merging, aisle categories, meal plan auto-connection
7. **Shared shopping list** -- Real-time sync for household members
8. **Pantry tracking** -- Manual entry + auto-add from shopping list completion
9. **"What can I cook?"** -- Recipe ranking by pantry ingredient coverage

### Phase 3: Social Media + AI
**Goal:** Compete with Recime/Pestle on modern recipe sources

10. **TikTok/Instagram video import** -- AI extraction from social media content
11. **AI suggestion agent** -- Proactive recipe suggestions based on pantry, calendar, preferences
12. **Nutrition auto-calculation** -- Leverage ingredient database with nutrition data

### Phase 4: Polish + Growth
**Goal:** Apple Design Award-worthy experience

13. **Voice commands in cook mode** -- Hands-free cooking navigation
14. **Cross-app migration** -- Import from Paprika, Crouton, Mela, etc.
15. **Batch/spreadsheet import** -- Power user feature for large collections
16. **Live import preview** -- See formatted recipe before saving

---

## Appendix: User Review Themes (Across All Competitors)

### What Users Love Most (across all apps)
1. "It just works" -- frictionless import that produces clean results
2. Cook mode that keeps screen on with big, readable text
3. Being able to consolidate recipes from many sources in one place
4. Automatic nutrition information
5. Serving size scaling
6. Simple, clean design that does not overwhelm

### What Users Complain About Most (across all apps)
1. Shopping lists that do not merge duplicates
2. Meal plans disconnected from shopping lists
3. Limited sorting and filtering options
4. No way to share recipes with family members collaboratively
5. Subscription pricing for what feels like a simple utility
6. Import failures with no clear error explanation
7. No pantry tracking to know what you already have
8. App crashes and performance issues

### Most Requested Features (across all reviews)
1. Shared/family recipe collections
2. Pantry tracking + "what can I make?" suggestions
3. Better shopping list intelligence
4. Dark mode (surprisingly common request)
5. More import sources (especially social media)
6. Recipe rating/favorites
7. Cooking history tracking
8. Voice control while cooking

---

*Sources: App Store reviews, Google Play reviews, Plan to Eat blog (Recime review), RecipeOne blog (app comparisons), MacStories (Pestle and Crouton reviews), TechCrunch (Pestle TikTok feature), Apple Developer (Design Awards), Startup Daily (Recime funding), Screensdesign (app showcase), Pluck Blog (app comparisons), Fulcra Design (app comparison), Flavor365 (app reviews), Drizzle Lemons (app testing), Forkee (honest comparison).*

---

## Addendum — 2026-04-25 — April Refresh + Palateful Parity Audit

> Refresh of the March investigation with: (a) latest 2026 review/pricing intel, (b) Palateful current-state parity audit, (c) free-forever positioning lock-in, (d) Recime mass-import feasibility check (RED → YELLOW pivot via Chrome extension).

### What Changed Since March

**1. Recime price drop (US cohorts).** Recime's help center (updated 2026-03-23) now lists the annual sub at **$39.99/yr** in some US cohorts; App Store IAP range is "$9.99–$59.99" suggesting A/B or grandfathered tiers. The "$59.99/yr" talking point is going stale — lead positioning instead with **5 imports/week** + **public-recipes-by-default** on the free tier. Source: [Recime help](https://recime.app/help/en/articles/11630592-how-much-does-the-recime-subscription-cost).

**2. Recime Q1 2026 = rebrand cycle, NOT feature cycle.** v5.0 (Feb 3) was a major brand redesign; v5.1.x – v5.2.x (Apr 7–16) are polish + bug fixes. **No new functional surfaces shipped since March.** The pantry / merge-duplicates / sort-options / public-recipes complaints are all still open and getting worse in 2026 reviews. Strategic opening for Palateful.

**3. NEW Recime complaints (last 90 days):**
- Backlash to the v5.0 rebrand ("Not a fan of the makeover — font, art and color choices have brought the app down" — TheMadCow, Feb 8).
- Search-within-cookbook is broken (works on home, fails inside a cookbook).
- "Even Pro users see ads" — surfacing in 2026 reviews; not in March investigation.
- Subscription-cancellation friction → JustUseApp aggregator scores Recime **4.1/100 on safety** based on 167K review NLP, weighted by billing complaints.
- Pinterest imports failing.

**4. NEW competitor: Recipe Notes.** Explicitly markets as "Free ReciMe Alternative" — unlimited imports, family sharing, no ads, $0. **Occupies the exact "free + unlimited" niche Palateful was eyeing.** Palateful's defensibility shifts from "we're free" to "we're free **AND pantry-aware AND household-native AND Meals-capable**." See [recipenotes.app/free-recime-alternative](https://recipenotes.app/free-recime-alternative).

**5. Other new entrants:**
- **Snapshot Recipes** — AI-first recipe generator (Apr 2026, hit #10 iOS Food & Drink); threat is on the AI-generation flank, not import flank.
- **Deglaze** — explicitly markets "save in 1–2 seconds vs Recime's 10s loading spinner" (4.9 App Store).
- **Flavorish, Recipe One, Preplo, Peel, Kich, Rejoy** — 2025/2026 entrants. Category is **crowding fast**.

**6. Apple+Gemini Siri (late 2026) — medium-term existential threat.** Apple's Siri+Gemini integration (CNBC Jan 12 2026, AppleInsider Apr 22) demoed "what can I make with what's in my fridge" — Apple is signaling pantry-aware cooking is a system-level capability they want to own. **Household + pantry + shared-list moats matter MORE now, not less.**

### Refreshed Pricing Landscape (April 2026)

| App | Apr 2026 price | Change vs. March |
|---|---|---|
| **Recime** | **$39.99/yr** US (some cohorts) — App Store range $9.99–$59.99 | **DROP from $59.99** in at least some cohorts |
| **Samsung Food (Whisk)** | $59.99/yr or $6.99/mo | No change |
| **Paprika 3** | $4.99 mobile, $29.99 desktop (one-time) | No change |
| **Mela** | ~$5.99 iOS one-time | No change |
| **Crouton** | 10 free recipes, then ~$15 one-time (was ~$10) | Slight uptick |
| **Pestle** | Free + monthly/yearly/lifetime | No change |
| **CopyMeThat** | $1/mo or yearly/lifetime; lifetime ~$65 | Shifted toward subscription |
| **Recipe Notes** *(new)* | **$0 — free forever, unlimited storage, family sharing, no ads** | NEW |

**Median annual:** ~$50/yr. **Cheapest paid:** Paprika $4.99 one-time. **Cheapest, period:** Recipe Notes $0.

### Palateful Parity Scorecard (2026-04-25)

**Must-Adopt (5/5 done):** iOS share extension (`epic-share-ios-extension`), Android share entrypoint (`epic-share-android-entrypoint`), photo/OCR import (HunyuanOCR, shipped 2026-01), meal-plan→shopping-list auto-connection (`mcal-5`, shipped 2026-04-18). Smart shopping list dedup is **intentionally cut** per `epic-ingredients-string-simplification` (2026-04-20) — Meal-grouping is the answer instead.

**Should-Adopt (3.6/5):**
- Voice cook mode: **DONE** (`11-6-hands-free-voice-input-in-cooking-mode`).
- Auto-detected timers: **IN-FLIGHT** (`epic-cook-mode-timers`; `cmt-1` done, `cmt-2..6` backlog, ~7-9 days remaining).
- Nutrition auto-calc: **NOT PLANNED** → addressed by `epic-nutrition-auto-calc` (this round).
- Live import preview: NOT PLANNED (low priority, deferred).
- Cross-app migration via uploaded export files: NOT PLANNED (deferred this round).

**Differentiation moats Palateful already has:** household collaboration with real-time sync, pantry foundation, Meals (multi-recipe compositions), recipe versioning + forking, MCP server (Claude integration), AI tool-calling agent.

### Critical Open Gaps Addressed in This Planning Round

1. **Social-media video import (TikTok/Instagram/YouTube)** — Recime's #1 growth driver. `epic-media-import` was deleted; partial backend (video file upload via share extension) landed but no frontend extraction routing. **→ `epic-social-video-import` (this round).**
2. **Pantry write-side hooks + "What can I cook?" ranking** — pantry CRUD + read shipped, but no auto-decrement on cook, no shopping→pantry hook, no "cook what you have" surface. **→ `epic-pantry-cook-with-what-you-have` (this round).**
3. **Free-forever positioning copy** — no user-visible marketing surface mentions pricing; ANDROID.md hedges with "v1 — no in-app purchases." **→ `epic-recime-positioning` (this round).**
4. **Nutrition auto-calc** — Recime Premium-gates this; users want it; no plans. **→ `epic-nutrition-auto-calc` (this round).**
5. **Recime mass-import (mid-planning addition).** User asked whether one-click migration from Recime is feasible. Feasibility check returned **YELLOW with a pivot**: original premise (free recipes are publicly scrapeable) was falsified — Recime recipes are private by default for both free AND Pro users; Recime TOS section 2.2(c) explicitly bans building competitive products against their service. **However**, a third-party Chrome extension ("ReciMe Recipe Exporter" by Jeff @ nealllc.com, updated 2026-04-14) proves the technical pattern: user logs in to recime.app in their own browser, extension uses their own session cookie to call Recime's internal web API, exfiltrates the user's full library to PDF. **Pivoted scope:** Palateful-branded Chrome extension that POSTs into Palateful's import endpoint instead. Sidesteps TOS scraper concern by mirroring Recime's GDPR data-portability promise. **→ `epic-recime-mass-import` (this round, Chrome extension MVP).**

### Five Positioning Hooks for "Palateful is Free" (Locked-in Copy)

1. **"Recime: $39.99–$59.99/yr or 5 imports per week. Palateful: unlimited everything, $0."**
2. **"They charge $59.99/yr to merge two onions on a shopping list — and they still don't. We do it free, in a Meal."**
3. **"Your household isn't one person. Your recipe app shouldn't be either. Real shared cookbooks, shared pantries, shared lists — free."**
4. **"Paprika tracks pantry. Recime imports from TikTok. Samsung Food has shared lists. Palateful does all three — free, in one app."**
5. **"Even Recime Pro users see ads in 2026. Palateful: no ads, no paywall, no five-imports-a-week limit. Ever."**

### Why "Free Forever" (Lock-In Decision — 2026-04-25)

User decision (2026-04-25): Palateful commits to **free forever** as a positioning hook, not "free for now." This closes off any future paywall pivot — monetization, if ever pursued, would have to be donations / one-time / non-paywall. The strength of "free forever" as a hook against Recime's $39.99–$59.99/yr — and against Recipe Notes (the sole free competitor) where Palateful's pantry/Meals/household stack is the differentiator — is materially stronger than hedged "free today" framing.

### Recime Mass-Import Feasibility Findings (Detailed)

**Verdict: RED for the original "scrape public recipes" idea. YELLOW with a Chrome-extension pivot.**

Key findings:
- **Recime web app exists** at `recime.app` (login modal at `/?loginModal=true`); described in their own help docs as "Available on desktop or laptop only" and "Still in beta." [web app help](https://recime.app/help/en/articles/11626084-can-i-access-recime-using-a-computer)
- **No public per-user profile pages, no public per-recipe URL pattern, no public discovery layer.** Recime explicitly states: "We do not offer any 'sharing' functionality within ReciMe and do not encourage sharing of recipes amongst individual users." [copyright/privacy article](https://recime.app/help/en/articles/11596213-recipe-saving-on-recime-and-copyright)
- **All recipes are private — free AND Pro alike.** Verbatim from Recime: *"When a user saves a recipe using ReciMe, it is automatically marked as Private. That means it is only visible to the individual user who saved it."* The free vs Pro distinction is import quota (5/week free), not privacy. **The original premise of the feature ("free-tier recipes are public") is falsified.**
- **TOS section 2.2(c)/(d) hostile to a Palateful-hosted scraper.** "no part of the Services may be copied, reproduced, distributed... in any form" + "you shall not access the Services in order to build a similar or competitive website, product, or service." A backend scraper is a clear violation. [terms](https://www.recime.app/terms-and-conditions)
- **GDPR data-portability clause grants users export rights.** Privacy policy: "your personal information in a structured, commonly used, machine-readable format" + "built-in functionality allowing users to download information stored in their accounts at no cost." [privacy](https://www.recime.app/privacy-policy)
- **Working precedent — third-party Chrome extension.** "ReciMe Recipe Exporter" by Jeff @ nealllc.com, last updated 2026-04-14, 1 user. Description: *"uses your existing ReciMe login session to read your recipes through the ReciMe API"* — currently dumps to PDF, but the underlying mechanism is exactly what Palateful would need. [extension](https://chromewebstore.google.com/detail/recime-recipe-exporter/nbmmcjlploegpicloeoknlgdblcbmoga)
- **No competitor has an "import from Recime" feature.** Recipe Notes (the most aggressive Recime-alternative marketer) only imports from Instagram/TikTok/Pinterest/Facebook/websites, not from Recime. Snapshot Recipes/Deglaze/Paprika/Mela/AnyList all silent. **The 4-year gap is itself the strongest negative signal — and the strongest opportunity.**

**Recommended path (locked-in 2026-04-25):** Build a Palateful-branded Chrome extension mirroring Jeff's pattern but POSTing into Palateful's import endpoint. The user is downloading their own data via their own session, exactly as the GDPR portability clause grants. Risk to flag at launch: even the extension is arguably TOS-iffy since Palateful is a competing service. Mitigation is framing + a 30-minute lawyer check before public Chrome Web Store launch. Not an epic blocker. See `epic-recime-mass-import.md` for full design.

### Bottom Line for Planning

- **Don't fight Recipe Notes on price** — they're $0 too. Win on capability stack at $0.
- **Close the social-video gap** — Recime is winning installs daily on this. Defensive move.
- **Open the pantry+household moat fully** — Apple+Gemini is coming for system-level pantry intel; ship the household-native version first.
- **Lock the free-forever copy** — strongest hook against Recime's billing-complaint-laden subscription.
- **Ship the Recime-import Chrome extension** — first-mover, works around TOS via user-side framing, leverages Recime's own GDPR portability promise. Strongest acquisition lever.
- **Skip cross-app migration parsers (Paprika/Mela/Crouton)** this round — acquisition utility, not parity feature; revisit later.

---

*Refresh sources: [Recime App Store](https://apps.apple.com/us/app/recime-recipes-meal-planner/id1593779280), [Recime Google Play](https://play.google.com/store/apps/details?id=com.recime.app), [Recime help / pricing](https://recime.app/help/en/articles/11630592-how-much-does-the-recime-subscription-cost), [Recime TOS](https://www.recime.app/terms-and-conditions), [Recime privacy policy](https://www.recime.app/privacy-policy), [Recipe Saving on ReciMe and Copyright](https://recime.app/help/en/articles/11596213-recipe-saving-on-recime-and-copyright), [Recipe Notes](https://recipenotes.app/free-recime-alternative), [Plan to Eat — Samsung Food review](https://www.plantoeat.com/blog/2026/01/samsung-food-review-pros-and-cons/), [Drizzle Lemons 2026 best apps](https://www.drizzlelemons.com/blog/best-recipe-apps-2026), [JustUseApp Recime aggregator](https://justuseapp.com/en/app/1593779280/recime-easy-tasty-recipes/reviews), [RecipeOne 2026 Recime review](https://www.recipeone.app/blog/recime-app-review), [Deglaze positioning](https://www.deglaze.app/blog/deglaze-vs-recime), [ReciMe Recipe Exporter Chrome extension](https://chromewebstore.google.com/detail/recime-recipe-exporter/nbmmcjlploegpicloeoknlgdblcbmoga), [CNBC Apple+Gemini Jan 12 2026](https://www.cnbc.com/2026/01/12/apple-google-ai-siri-gemini.html), [AppleInsider Apr 22 2026](https://appleinsider.com/articles/26/04/22/google-confirms-context-aware-siri-built-from-gemini-will-debut-in-2026).*

---

## Addendum — 2026-04-25 — April Refresh + Palateful Parity Audit + Recime Mass-Import Feasibility

> Refresh of the March investigation. Source addendum saved to git history. See PRD addendum (2026-04-25) and `_bmad-output/planning-artifacts/epics.md` 5-epic addendum (2026-04-25) for downstream artifacts.

### April 2026 Snapshot

- **Recime US price drop** to $39.99/yr in some cohorts (App Store IAP $9.99–$59.99). [Recime help](https://recime.app/help/en/articles/11630592-how-much-does-the-recime-subscription-cost). Lead positioning with **5 imports/week limit** + **public-by-default free tier** instead.
- **Recime Q1 2026 = rebrand cycle, no functional features** since March. Pantry / merge-duplicates / sort / public-recipes complaints remain open in 2026 reviews.
- **NEW Recime complaints (last 90 days):** v5.0 rebrand backlash, search-within-cookbook broken, "Pro users still see ads," subscription-cancellation friction (JustUseApp 4.1/100 safety score from 167K NLP'd reviews), Pinterest imports failing.
- **NEW competitor: Recipe Notes** ([recipenotes.app](https://recipenotes.app/free-recime-alternative)) — explicitly "Free ReciMe Alternative." Free, unlimited, family sharing, no ads. Occupies the same niche Palateful eyed. Defensibility shifts to "free **AND pantry-aware AND household-native AND Meals-capable**."
- **Other entrants:** Snapshot Recipes (AI-first, Apr 2026 #10 iOS Food & Drink), Deglaze (positions on speed vs Recime), Flavorish/RecipeOne/Preplo/Peel/Kich/Rejoy (2025-2026). Category crowding fast.
- **Apple+Gemini Siri** late 2026 demoed "what can I make with what's in my fridge." System-level pantry intelligence is a 12-24 month threat. Household + shared + pantry moats matter MORE now.

### Palateful Parity Scorecard (2026-04-25)

- **Must-Adopt: 5/5 done.** iOS share extension, Android share entrypoint, OCR import, meal-plan→shopping-list (`mcal-5`), smart-list dedup intentionally cut on 2026-04-20 with Meal-grouping as the answer.
- **Should-Adopt: 3.6/5.** Voice cook mode DONE; auto-detected timers IN-FLIGHT (`epic-cook-mode-timers` cmt-2..6); nutrition NOT PLANNED → addressed this round; live preview deferred; cross-app file migration deferred.
- **Differentiation moats Palateful has:** household collab + real-time sync, pantry foundation, Meals (multi-recipe compositions), recipe versioning + forking, MCP server, AI tool-calling agent.

### Recime Mass-Import Feasibility — VERDICT: RED → YELLOW pivot

- **All Recime recipes are private** for both free AND Pro users. Original "free recipes are public" premise FALSIFIED. "*recipes are treated as personal notes... not as publicly republished content*" ([Recime copyright article](https://recime.app/help/en/articles/11596213-recipe-saving-on-recime-and-copyright)).
- **Recime TOS section 2.2(c)/(d) hostile to a Palateful-hosted scraper.** "*shall not access the Services in order to build a similar or competitive website, product, or service*" ([Recime TOS](https://www.recime.app/terms-and-conditions)).
- **Recime privacy policy GDPR portability clause grants users export rights** — "*your personal information in a structured, commonly used, machine-readable format*" ([Recime privacy](https://www.recime.app/privacy-policy)).
- **Working precedent:** Third-party Chrome extension "ReciMe Recipe Exporter" by Jeff @ nealllc.com, last updated 2026-04-14, dumps to PDF using user's session cookie ([extension](https://chromewebstore.google.com/detail/recime-recipe-exporter/nbmmcjlploegpicloeoknlgdblcbmoga)).
- **Pivoted scope:** Palateful-branded Chrome extension that POSTs into our import endpoint instead of generating PDF. Sidesteps TOS scraper concern (user-side, not server-side; mirrors GDPR portability). Lawyer review before public Chrome Web Store launch but not an epic blocker. Full design in `epic-recime-mass-import.md`.

### Five Locked Epics for This Round

1. `epic-recime-positioning` (P0, ~1 week) — free-forever copy lock-in, web landing page, comparison table, in-app "why we're free."
2. `epic-social-video-import` (P0, ~3-4 weeks) — TikTok + Instagram + YouTube extraction via Whisper transcription + caption scraping + AI synthesis.
3. `epic-pantry-cook-with-what-you-have` (P0, ~2-3 weeks) — pantry write-side hooks + "what can I cook tonight?" ranking + pantry-coverage badges + use-it-up nudges.
4. `epic-recime-mass-import` (P1, ~1.5 weeks) — Palateful-branded Chrome extension MVP for one-click Recime library import.
5. `epic-nutrition-auto-calc` (P1, ~3-5 weeks) — USDA FoodData Central data load + auto-calculated macros per recipe + manual override.

### Five Positioning Hooks for "Palateful is Free"

1. "Recime: $39.99–$59.99/yr or 5 imports/week. Palateful: unlimited everything, $0."
2. "They charge $59.99/yr to merge two onions on a shopping list — and they still don't. We do it free, in a Meal."
3. "Your household isn't one person. Your recipe app shouldn't be either. Real shared cookbooks, shared pantries, shared lists — free."
4. "Paprika tracks pantry. Recime imports from TikTok. Samsung Food has shared lists. Palateful does all three — free, in one app."
5. "Even Recime Pro users see ads in 2026. Palateful: no ads, no paywall, no five-imports-a-week limit. Ever."
