# Big Rocks - Major Focus Areas

These are the key areas that need deep thought and careful implementation. Each one is a significant undertaking that will shape the core experience of Palateful.

---

## 1. Ingredient Seeding Service

**Goal:** Build a comprehensive ingredient database covering virtually every ingredient imaginable.

**Why it matters:** The foundation of recipe matching, substitutions, pantry tracking, and smart suggestions all depend on having a rich, well-structured ingredient dataset.

**Approach ideas:**
- Web scraping from multiple sources (grocery stores, recipe sites, food databases)
- Categorization by type, cuisine, dietary flags, seasonality
- Include aliases (e.g., "cilantro" = "coriander leaves")
- Nutrition data where available

**Potential references:**
- **USDA FoodData Central** - Free API with 300k+ foods, nutrition data included
- **Open Food Facts** - Open-source database, community-driven, barcode scanning
- **Spoonacular** - Commercial API but has ingredient parsing/matching
- **TheMealDB / Edamam** - Recipe APIs that could inform ingredient lists

**Example structure:**
```
Ingredient:
  canonical_name: "chicken breast"
  aliases: ["chicken boob", "boneless chicken"]
  category: "protein/poultry"
  subcategory: "chicken"
  dietary_flags: ["gluten-free", "dairy-free", "keto"]
  seasonality: null
  common_units: ["lb", "oz", "piece"]
  avg_price_per_unit: 4.99
  nutrition_per_100g: { calories: 165, protein: 31, ... }
```

**This is a standalone project** - Worth building a separate scraper/generator that outputs seed files.

---

## 2. Import/Export from External Sources

> **Design Document:** See `docs/RECIPE_IMPORT_SYSTEM.md` for complete implementation details.

**Goal:** Let users bring in recipes from CSV, spreadsheets, URLs, PDFs, and other sources.

**Key Design Decisions (January 2025):**
- **Worker-based pipeline**: Async Celery tasks for reliability and scalability
- **Cost optimization**: Tiered extraction (JSON-LD → site scrapers → AI fallback)
- **Auto-approve + review flow**: High-confidence matches auto-created, flagged items need user review
- **Ingredient matching**: Cached lookups → pg_trgm fuzzy → semantic search → AI
- **Images**: Download thumbnails to S3 for reliability
- **Notifications**: Push notifications when review needed or import complete

**Architecture:**
```
Upload → ParseSourceTask → ExtractRecipeTask → MatchIngredientsTask
                                                      │
                                    ┌─────────────────┴─────────────────┐
                                    ▼                                   ▼
                             Auto-approve                        Flag for Review
                             (high conf)                          (low conf)
                                    │                                   │
                                    └──────────┬────────────────────────┘
                                               ▼
                                       CreateRecipeTask
```

**Data Models:** ImportJob, ImportItem, IngredientMatch (for learning cache)

**Site-Specific Scrapers:** AllRecipes, Food Network, Epicurious, Serious Eats, NYT Cooking, Budget Bytes, Bon Appetit

---

## 3. AI Suggestion Agent

**Goal:** Proactive AI that suggests recipes, meal plans, and tips—without needing a chat conversation.

**Key insight:** This isn't a chatbot. It's an agent that runs in the background and surfaces suggestions.

**How it works:**
```
SuggestionAgent:
  triggers:
    - Daily (morning meal suggestion)
    - Pantry updated (what can you make?)
    - Upcoming event (prep suggestions)
    - Ingredient expiring (use it up!)

  tools:
    - search_recipes(filters)
    - check_pantry()
    - get_calendar_events()
    - get_user_preferences()

  output:
    - Push notification
    - Card on home screen
    - Badge on recipe
```

**Example suggestions:**
- "You have chicken thighs expiring tomorrow. Here are 3 quick recipes."
- "It's Sunday—want to meal prep for the week?"
- "Based on your pantry, you can make Pasta Carbonara tonight."

**Architecture:** Background job that runs periodically + event-driven triggers.

---

## 4. Main Recipe Screen (Home)

**Goal:** The heart of the app. Clean, beautiful, functional. Icon-driven, minimal text buttons.

**This is the app's front door** - What you see when you open Palateful.

### Layout concept:

```
┌─────────────────────────────────────────┐
│  [Search icon]          [Filter icon]   │
├─────────────────────────────────────────┤
│  Meal: [🌅 Bfast] [☀️ Lunch] [🌙 Dinner] [🍰 Dessert]  │
├─────────────────────────────────────────┤
│  Sort: [⭐ Best] [🆕 New] [🔥 Popular] [⏱️ Quick]     │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┐  ┌─────────┐              │
│  │ [photo] │  │ [photo] │              │
│  │ Title   │  │ Title   │              │
│  │ 🏷️ tags  │  │ 🏷️ tags  │              │
│  │ 🥕 3 ing │  │ 🥕 5 ing │              │
│  │ ⏱️ 25min │  │ ⏱️ 45min │              │
│  │ 🍳 x4    │  │ 🍳 x12   │   ← times made│
│  └─────────┘  └─────────┘              │
│                                         │
│  ┌─────────┐  ┌─────────┐              │
│  │  ...    │  │  ...    │              │
│                                         │
└─────────────────────────────────────────┘
          [  ➕  ]  ← Floating add button
```

### Recipe card shows:
- Photo (prominent)
- Title
- Tags/categories (small pills)
- First 2-3 ingredients preview
- Total time
- Times cooked (your history)
- Meal type indicator

### Sorting options (icon-based):
- ⭐ Best (your favorites/ratings)
- 🆕 Newest (recently added)
- 🔥 Popular (public recipes, if social features)
- ⏱️ Quickest (by total time)
- 🎲 Surprise me (random)

### Filtering by meal:
- 🌅 Breakfast
- ☀️ Lunch
- 🌙 Dinner
- 🍰 Dessert
- 🍿 Snack

**Add Recipe button:** Floating action button, bottom right.

---

## 5. Minimal Click Philosophy

**Goal:** Main flows should be frictionless. Every tap must earn its place.

### Core flows to optimize:

**A. View Recipe → Cook Mode**
```
Current: Tap recipe → Scroll → Find "Start Cooking" → Tap
Target:  Tap recipe → Swipe up or tap 🍳 icon → Cooking
         OR long-press recipe card → instant cook mode
```

**B. Add Recipe**
```
Options presented immediately:
  [📷 Photo]  [📁 Files]  [✍️ Manual]

Photo flow:
  Tap 📷 → Camera opens → Snap → AI parses → Review → Save
  (3 taps to complete)

Manual flow (Recipe Wizard):
  Step 1: Name + Photo (optional)
  Step 2: Ingredients (smart autocomplete)
  Step 3: Instructions (numbered, drag to reorder)
  Step 4: Details (time, servings, tags)
  [Save]

  Progress bar at top, can skip around
```

**C. Calendar/Events** *(stub for now)*
```
Placeholder card on home: "Plan your week →"
Opens to: "Coming soon! Meal planning calendar."
```

**D. Notifications** *(stub for now)*
```
Bell icon in header, badge count
Opens to: "Coming soon! Get reminders for meal prep."
```

### Design principles:
- Icons > words for repeated actions
- Swipe gestures for common flows
- Long-press for power-user shortcuts
- Smart defaults (don't ask if you can guess)
- Undo > confirmation dialogs

---

## 6. Do Recipe Mode (Cooking Mode)

**Goal:** The best possible experience while actively cooking. Hands are messy, attention is split.

### Problems to solve:
- Hate scrolling back to ingredients
- Lose track of which step you're on
- Hard to use with wet/dirty hands
- Need timers integrated

### Layout concept:

```
┌─────────────────────────────────────────┐
│  ← Back    "Chicken Parmesan"    [⏱️]   │
├─────────────────────────────────────────┤
│  INGREDIENTS (always visible strip)     │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐        │
│  │ 🍗 ││ 🧀 ││ 🍅 ││ 🧄 ││ → ││        │
│  │2 lb││1 c ││ can││3 cl││    ││        │
│  └────┘└────┘└────┘└────┘└────┘        │
│  ↑ Horizontal scroll, tap to expand     │
├─────────────────────────────────────────┤
│                                         │
│   Step 2 of 6                           │
│   ━━━━━━━━━━○───────────  ← progress    │
│                                         │
│   "Heat oil in a large skillet over     │
│    medium-high heat. Season chicken     │
│    with salt and pepper."               │
│                                         │
│   [⏱️ Set 5min timer]  ← inline timer   │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│   [ ← Prev ]           [ Next → ]       │
│                                         │
│   ────────────────────────────────      │
│   1  2  ●  4  5  6   ← tap to jump      │
│                                         │
└─────────────────────────────────────────┘
```

### Key features:

**Ingredient strip (top, always visible):**
- Horizontal scroll of ingredient "chips"
- Shows quantity + icon/emoji
- Tap to expand full details
- Check off as you use them

**Step navigation:**
- Big prev/next buttons (easy to tap with elbow)
- Progress bar showing where you are
- Number row at bottom to jump to any step
- Swipe left/right to navigate

**Progress tracking:**
- Steps you've completed stay checked
- Can go back without losing progress
- "Mark all as done up to here" gesture (long-press step number)

**Timers:**
- Detect time mentions in instructions
- Inline "Set timer" button
- Multiple concurrent timers supported
- Notification when timer done

**Voice control (future):**
- "Next step" / "Previous step"
- "Read ingredients"
- "Set timer 10 minutes"

**Screen behavior:**
- Keep screen awake while in cook mode
- Large text option
- High contrast for kitchen lighting

---

## Priority Order (suggested)

1. **Main Recipe Screen** - It's what users see first
2. **Do Recipe Mode** - Core cooking experience
3. **Minimal Click UX** - Refine the flows
4. **Ingredient Seeding** - Foundation for everything else
5. **AI Suggestion Agent** - Delight feature
6. **Import/Export** - Power user feature (covered by OCR work)

---

*Last updated: January 2025*
