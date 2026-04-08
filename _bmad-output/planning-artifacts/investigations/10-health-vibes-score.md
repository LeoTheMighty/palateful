# Investigation: Health / Holistic Vibes Score

## Executive Summary

Palateful has an opportunity to differentiate itself from every other kitchen management app by introducing a **"Vibes" system** -- a holistic, feeling-based way to categorize and reflect on meals that explicitly rejects calorie counting and clinical nutrition tracking. Instead of numbers and macros, users would see and interact with their food through the lens of how it *feels*: light and fresh, hearty and grounding, indulgent and comforting, energizing and vibrant.

This feature draws inspiration from Ayurvedic food philosophy (warming/cooling), Traditional Chinese Medicine food therapy (yin/yang balance), and the modern intuitive eating movement -- but translates those dense systems into a simple, approachable visual language that feels native to a cooking app, not a wellness clinic.

The existing codebase is well-positioned for this: recipes already have a free-form `tags` array, ingredients have `category` and `flavor_profile` fields, OpenAI is integrated for AI-powered analysis, and the meal calendar provides the temporal structure needed for weekly vibe summaries. The core feature can be built incrementally, starting with AI-assigned vibes on recipes and expanding into meal planning intelligence.

---

## Current State Analysis

### Recipe Data Model

The `Recipe` model (`libraries/utils/utils/models/recipe.py`) captures:

| Field | Type | Vibes Relevance |
|-------|------|-----------------|
| `name` | String | AI can infer vibe from recipe name |
| `description` | String | Rich text for vibe inference |
| `instructions` | Text | Cooking method signals (e.g., raw = light, braised = hearty) |
| `tags` | ARRAY(String) | **Could store vibes today** -- free-form, already displayed in UI |
| `ingredients` | Relationship | Ingredient composition is the strongest vibe signal |
| `prep_time` / `cook_time` | Integer | Quick meals often correlate with lighter vibes |
| `servings` | Integer | Large-batch cooking often correlates with hearty/comfort |
| `embedding` | Vector(384) | Semantic search -- could be extended to include vibe dimensions |

### Ingredient Data Model

The `Ingredient` model (`libraries/utils/utils/models/ingredient.py`) has fields that are directly useful:

- **`category`**: Already classifies ingredients as "produce", "dairy", "protein", "pantry", "spice" -- maps loosely to vibe inference (produce-heavy = lighter, protein + dairy heavy = heartier)
- **`flavor_profile`**: ARRAY(String) with values like "acidic", "umami" -- these map to vibe qualities (citrus/acidic = fresh; umami = hearty/comforting)

### Tags System

Recipes already support free-form tags (`ARRAY(String)`) with:
- Bulk tag operations (`BulkUpdateTags` endpoint at `POST /recipes/bulk/tags`)
- Tags displayed in recipe cards (up to 2 shown in `RecipeCard` widget)
- Tags used in recipe embedding generation for semantic search

This means vibes could ship as a specialized subset of tags initially, without any schema changes.

### Meal Calendar

The `MealEvent` model links recipes to specific dates with `meal_type` (breakfast/lunch/dinner/snack) and `scheduled_at`. This provides the temporal backbone for "weekly vibes" summaries. The calendar service (`MealCalendarService`) already supports date-range queries.

### AI Integration

The app has a mature AI pipeline:
- **OpenAI gpt-4o-mini** for chat and recipe suggestions via the agent loop
- **text-embedding-3-small** for recipe embeddings (384 dimensions)
- **SentenceTransformer** (`all-MiniLM-L6-v2`) for semantic search
- **Agent tool framework** (`BaseTool` / `ToolResult` pattern) that makes adding new AI tools straightforward
- **System prompt** already references dietary preferences and meal planning

### What Does NOT Exist

- No nutrition data, calorie counts, or macro tracking -- **this is a feature, not a gap**
- No recipe categorization beyond free-form tags
- No meal pattern analysis or weekly summaries
- No concept of food "feeling" or energy quality
- No personalized recipe recommendations based on balance/variety

---

## Research Findings

### Holistic Food Categorization Traditions

#### Ayurvedic Approach (Indian)

Ayurveda classifies food along several axes:

| Axis | Qualities | Relevance to Vibes |
|------|-----------|---------------------|
| **Thermal** | Warming / Cooling | Maps to "Cozy & Warming" vs "Light & Fresh" |
| **Dosha** | Vata (grounding), Pitta (cooling), Kapha (light) | Too clinical for Palateful's audience |
| **Guna** | Heavy (guru) / Light (laghu) | Maps directly to "Hearty" vs "Light" |
| **Rasa** (taste) | Sweet, Sour, Bitter, Pungent, Salty, Astringent | Useful for AI classification signals |

**What to borrow**: The warming/cooling axis and the heavy/light axis are intuitive and universally understood. The dosha system is too specialized.

#### TCM Food Therapy (Chinese)

Traditional Chinese Medicine classifies all foods as:
- **Hot / Warm / Neutral / Cool / Cold** (thermal nature)
- **Five Flavors**: Sweet, Sour, Bitter, Pungent, Salty
- **Yin / Yang** balance

Specific ingredient mappings from TCM research:
- **Warming/Yang**: ginger, garlic, cinnamon, lamb, chicken, chili, coffee, onion, basil
- **Cooling/Yin**: cucumber, watermelon, lettuce, tofu, mung bean, yogurt, celery, banana
- **Neutral**: rice, potato, carrot, beef, pork, corn, sweet potato

**What to borrow**: TCM has the most comprehensive ingredient-level thermal mapping, which can directly feed the AI classification engine.

#### Intuitive Eating Movement (Modern Western)

Apps in this space (AteMate, Munch, Eating Buddy, Shutterbite) focus on:
- **Photo-based food journaling** without calorie counts
- **Mood and energy tracking** before and after meals
- **Pattern recognition** over time ("you tend to feel sluggish after heavy lunches")
- **Hunger/fullness cues** rather than portion control
- **Non-judgmental language** -- no "good food" vs "bad food"

**What to borrow**: The non-judgmental framing is critical. Vibes should never imply "this is unhealthy." A carb-load vibe is celebrated before a marathon, not shamed.

#### Color-Coded Scoring (Noom, Yuka, OptUP)

Several apps use traffic-light or gradient color systems:
- **Noom**: Green / Yellow / Orange based on caloric density
- **Yuka**: Excellent / Good / Mediocre / Poor with color coding
- **OptUP** (Kroger): Green / Light Green / Yellow / Red

**Anti-pattern to avoid**: These systems create implicit hierarchies ("green = good, red = bad"). Palateful's vibes should feel like a spectrum of variety, not a report card.

---

## Proposed "Vibes" System Design

### Vibe Categories

After analyzing the traditions above and filtering for what feels native to a modern cooking app, here are the proposed vibe categories:

| Vibe | Description | Color | Visual | Example Recipes |
|------|-------------|-------|--------|-----------------|
| **Light & Fresh** | Salads, raw preparations, citrus-forward, produce-heavy | Soft green `#A8D8A8` | Leaf / sprout | Greek salad, ceviche, smoothie bowl, poke |
| **Hearty & Filling** | Substantial meals that stick with you, protein-rich, satisfying | Warm amber `#D4A853` | Bowl / stew pot | Beef stew, lasagna, pot roast, chili |
| **Comfort** | Warm, familiar, emotionally satisfying, nostalgic | Soft terracotta `#CB8B73` | Blanket / mug | Mac and cheese, chicken soup, grilled cheese, mashed potatoes |
| **Energizing** | Nutrient-dense, vibrant, makes you feel ready to go | Bright sage `#8FA882` | Lightning / sunrise | Acai bowl, grain bowl, stir fry, overnight oats |
| **Carb-Load** | Pasta-forward, bread-heavy, fuel meals, pre-activity | Golden wheat `#C8A96E` | Wheat / pasta | Spaghetti, pizza, garlic bread, pancakes |
| **Indulgent** | Rich, decadent, celebratory, treat meals | Deep plum `#8B6B8B` | Sparkle / star | Chocolate cake, creme brulee, bacon cheeseburger, truffle pasta |
| **Warming** | Spiced, cozy, perfect for cold days, soups | Deep cinnamon `#A0522D` | Flame / warm cup | Curry, hot chocolate, mulled wine, ramen |

#### Design Principles for Vibe Categories

1. **No hierarchy** -- "Indulgent" is not worse than "Light & Fresh." A well-lived week has variety.
2. **Overlap is fine** -- A recipe can be both "Comfort" and "Hearty." Primary vibe + optional secondary.
3. **Seasonal relevance** -- "Warming" vibes naturally surface in winter; "Light & Fresh" in summer.
4. **Cultural neutrality** -- Categories work across cuisines. Japanese ramen is "Warming" just like Italian minestrone.
5. **Emotional resonance** -- Each category should make you *feel* something when you see it.

### Assignment Mechanism

#### Layer 1: AI Auto-Detection (Primary)

When a recipe is created or imported, the existing OpenAI integration can classify it automatically. This extends the current `generate_recipe_embedding` pattern:

**Input signals for AI classification:**
- Recipe name and description
- Ingredient list (with categories and flavor profiles from the Ingredient model)
- Cooking method (inferred from instructions -- baking, frying, raw, braising, etc.)
- Prep/cook time (quick meals tend lighter; long cooks tend heartier)
- Serving size
- Existing tags

**Proposed prompt pattern:**
```
Given this recipe, assign 1-2 vibes from this list:
[light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming]

Recipe: {name}
Description: {description}
Ingredients: {ingredient_list_with_categories}
Cooking method: {extracted_from_instructions}
Total time: {prep + cook} minutes

Respond with JSON: {"primary_vibe": "...", "secondary_vibe": "..." or null, "confidence": 0.0-1.0}
```

This can run as part of the existing recipe creation flow, piggybacking on the embedding generation step. Cost is minimal -- a single gpt-4o-mini call per recipe creation.

#### Layer 2: User Override (Secondary)

Users should always be able to:
- **Change the AI-assigned vibe** -- "This isn't comfort food to me, it's energizing"
- **Add a secondary vibe** -- "This is both hearty AND comfort"
- **Remove vibes entirely** -- if they don't want vibes on a recipe

This respects that vibes are subjective. Your grandmother's soup might be "Comfort" to you but "Light & Fresh" to someone else.

#### Layer 3: Community/Household Signal (Future)

In shared recipe books, vibes assigned by multiple household members could blend:
- If 3 out of 4 household members tag a recipe as "Comfort," that becomes the default
- Individual overrides still apply per-user

### Display & Visualization

#### Recipe Card (Home Screen)

The existing `RecipeCard` widget already displays meal type badges and tags. The vibe would appear as a colored pill/badge:

```
+---------------------------+
|  [recipe image]           |
|                           |
|  [Comfort] [Hearty]       |   <-- Vibe badges (colored pills)
|  Grandma's Beef Stew      |
|  tomato, beef, potato...  |
|  30m            x3        |
+---------------------------+
```

The vibe badge replaces the existing tag display position, using the vibe-specific color as the badge background with warm-toned text. This integrates naturally with the existing warm cream/chocolate/hazelnut design language.

#### Recipe Detail Screen

On the detail screen, the vibe appears prominently near the recipe title:

```
[Recipe Image - full width]

Grandma's Beef Stew
[Comfort] [Hearty]              <-- Colored vibe pills

"The kind of meal that makes the
whole house smell amazing"       <-- AI-generated vibe description (optional future)

Prep: 20m  |  Cook: 2h  |  Serves: 6
```

#### Vibe Icons

Each vibe gets a simple, warm-toned icon that matches the app's design language. These should feel hand-drawn or organic, not clinical:

| Vibe | Icon Concept |
|------|-------------|
| Light & Fresh | Small leaf or dewdrop |
| Hearty & Filling | A steaming bowl |
| Comfort | A cozy mug or soft swirl |
| Energizing | A small sunrise or spark |
| Carb-Load | A wheat stalk or bread slice |
| Indulgent | A small sparkle or star |
| Warming | A gentle flame or steam curl |

### Meal Planning Integration

#### "Vibe Balance" View on Calendar

When viewing the weekly calendar, a subtle horizontal bar or strip shows the vibe distribution for the week:

```
Mon   Tue   Wed   Thu   Fri   Sat   Sun
[L&F] [H]   [C]   [E]   [--]  [I]   [W]
  ______________________________________
  | [green][amber][terr][sage]  [plum][cinn] |   <-- Weekly vibe strip
  |________________________________________|

  "Mostly balanced -- your week has good variety"
```

This is NOT a score. It is a reflection. The language is always observational, never prescriptive:
- "Your week is running hearty -- craving something light?"
- "Nice variety this week!"
- "Three comfort meals in a row -- sounds cozy"

#### "I'm in the mood for..." Filter

Add a vibe filter to the recipe browsing and search experience:

```
[All] [Light & Fresh] [Hearty] [Comfort] [Energizing] [Carb-Load] [Indulgent] [Warming]
```

This works alongside the existing `MealFilterBar` (breakfast/lunch/dinner/snack). The implementation pattern is identical -- a horizontal scrolling list of filter chips.

#### Vibe-Aware Suggestions

When the AI chat assistant suggests recipes (via the existing `SuggestRecipeTool` or `SearchRecipesTool`), it can factor in the week's vibe balance:

> "You've had three hearty meals this week. How about something light and fresh tonight? Here are some options from your collection..."

This surfaces naturally through the system prompt enhancement, not a separate feature.

### Weekly Vibes Summary

A lightweight, delightful weekly summary that appears on the home screen or calendar:

```
+-------------------------------------------+
|  Your Week in Vibes                       |
|                                           |
|  Mon  Tue  Wed  Thu  Fri  Sat  Sun       |
|  [L]  [H]  [C]  [E]  [C]  [I]  [W]     |
|                                           |
|  Mostly cozy with a fresh start           |
|  and an indulgent Saturday                |
|                                           |
|  Most common: Comfort (3 meals)           |
|  New this week: Tried "Warming" for       |
|  the first time!                          |
+-------------------------------------------+
```

The summary text is AI-generated (one gpt-4o-mini call per week, very low cost) or template-based:
- Template: Pick from pre-written summaries based on vibe distribution
- AI: Generate a 1-2 sentence personality-filled summary

Design tone: Like a friend commenting on your week, not a nutritionist grading you.

### Shared Recipe Books & Households

In shared contexts:
- Each recipe has a **consensus vibe** (the vibe most members have assigned, or the AI default if no one has changed it)
- Individual users can have **personal vibe overrides** that only affect their own view
- Weekly summaries are per-user (based on what *they* ate, not what the household ate)
- Shared meal events inherit the recipe's vibe, visible to all participants

---

## Anti-Patterns to Avoid

### 1. Do NOT Create a Score or Grade

No numbers. No percentages. No "your vibe score is 7.2." The moment you quantify vibes, you've created a diet metric. Vibes are qualitative descriptions, not measurements.

### 2. Do NOT Imply a Hierarchy

"Indulgent" is not worse than "Energizing." "Carb-Load" is not a failure. Language must be consistently neutral-to-positive. Bad: "You had too many indulgent meals." Good: "Lots of indulgent choices this week -- sounds like a celebration!"

### 3. Do NOT Recommend "Balance" Prescriptively

The app should never say "you should eat more light meals." It can observe ("running hearty this week") and offer ("want something lighter?"), but never prescribe. The user's body and preferences are the authority.

### 4. Do NOT Make Vibes Mandatory

Vibes should be opt-in at the engagement level. They appear on recipes automatically (AI-assigned), but the user should never feel forced to interact with them. No onboarding gates, no required selections.

### 5. Do NOT Track or Store Historical "Vibe Scores"

Do not build analytics dashboards or historical trend tracking. This crosses from "fun reflection" into "health monitoring" territory. The weekly summary is ephemeral -- it reflects the current week and fades.

### 6. Do NOT Conflate Vibes with Nutrition

Vibes describe how food *feels*, not how food *measures*. A salad can be "Hearty" if it is big and filling. A steak can be "Light" if it is a small, simply prepared portion. The AI should consider the whole recipe context, not just ingredient "healthiness."

---

## AI Integration Opportunities

### Using the Existing Stack

| Capability | Current Use | Vibes Extension |
|------------|-------------|-----------------|
| gpt-4o-mini chat | Recipe suggestions, cooking assistant | Vibe assignment, weekly summaries, vibe-aware suggestions |
| text-embedding-3-small | Recipe semantic search embeddings | Could include vibe signals in embedding text |
| SentenceTransformer | Ingredient search | N/A |
| Agent tool framework | SearchRecipes, AddNote, SuggestRecipe | New `GetRecipeVibes`, `GetWeeklyVibesSummary` tools |

### New AI Tool: `assign_recipe_vibes`

A lightweight function (not a full agent tool) called during recipe creation/import:

```python
def assign_recipe_vibes(
    recipe_name: str,
    description: str | None,
    ingredient_names: list[str],
    ingredient_categories: list[str],
    instructions: str | None,
    prep_time: int | None,
    cook_time: int | None,
) -> dict:
    """Returns {"primary_vibe": "comfort", "secondary_vibe": "hearty", "confidence": 0.92}"""
```

### New Agent Tool: `GetWeeklyVibesSummary`

Extends the agent tool registry for the chat assistant:

```python
class GetWeeklyVibesTool(BaseTool):
    """Summarize the user's meal vibes for the current or specified week."""
```

This lets users ask the chat assistant: "What did my week look like vibe-wise?" or "I've been eating heavy, suggest something light."

### Embedding Enhancement

The existing `generate_recipe_embedding` function already concatenates name + description + tags. Adding vibe to this string improves semantic search relevance:

```python
input_text = f"{recipe_name}. {description or ''}. Tags: {', '.join(tags or [])}. Vibe: {primary_vibe}"
```

---

## Technical Considerations

### Storage Options

**Option A: Use existing `tags` array (Minimal change)**
- Store vibes as prefixed tags: `"vibe:comfort"`, `"vibe:hearty"`
- Pro: Zero schema changes, works with existing tag UI and bulk operations
- Con: Mixes vibes with user tags, harder to query efficiently

**Option B: Add `primary_vibe` and `secondary_vibe` columns to Recipe (Recommended)**
- Two new String columns on the `recipes` table
- Pro: Clean querying, explicit filtering, type safety
- Con: Requires migration

**Option C: Separate `recipe_vibes` table**
- Pro: Supports per-user vibe overrides, historical tracking
- Con: Over-engineered for initial launch, joins complexity

**Recommendation**: Start with **Option B** for the recipe-level vibe assignment, with a future path to Option C if per-user overrides become important.

### Migration

```sql
ALTER TABLE recipes ADD COLUMN primary_vibe VARCHAR(20);
ALTER TABLE recipes ADD COLUMN secondary_vibe VARCHAR(20);
-- Optional: constraint to valid enum values
-- ALTER TABLE recipes ADD CONSTRAINT chk_primary_vibe
--   CHECK (primary_vibe IN ('light_fresh', 'hearty', 'comfort', 'energizing', 'carb_load', 'indulgent', 'warming'));
```

### API Changes

- `RecipeResponse` and `RecipeListItem` schemas: Add `primary_vibe` and `secondary_vibe` fields
- `RecipeCreate` and `RecipeUpdate` schemas: Add optional vibe fields
- New endpoint: `GET /recipes/vibes/summary?start_date=...&end_date=...` for weekly summaries
- Modify `CreateRecipe` endpoint to call vibe assignment after recipe creation
- Modify recipe search to support vibe filtering

### Flutter Changes

- New `VibeChip` widget (colored pill with icon)
- `RecipeCard` widget: Add vibe chips below image
- `RecipeDetailScreen`: Add vibe display near title
- `MealFilterBar`: Add vibe filter option (or separate `VibeFilterBar`)
- New `WeeklyVibesSummary` widget for home screen / calendar
- `MealEvent` model: Inherit vibe from linked recipe

### Backfill Strategy

For existing recipes that predate the vibes feature:
1. Run a one-time batch job that calls gpt-4o-mini for each recipe
2. Estimated cost: ~$0.01 per 100 recipes (extremely cheap with gpt-4o-mini)
3. Can be run as a migration script or background worker task

---

## Recommendations (Prioritized)

### Phase 1: Foundation (1-2 sprints)

1. **Add `primary_vibe` / `secondary_vibe` to Recipe model** -- DB migration, schema updates
2. **Build AI vibe assignment function** -- Called during recipe creation/import
3. **Display vibes on recipe cards and detail screens** -- `VibeChip` widget
4. **Backfill existing recipes** -- One-time batch job
5. **Add vibe filter to recipe browsing** -- New filter bar or extend existing

**Value**: Users immediately see vibes on all their recipes. Browsing by vibe is available.

### Phase 2: Calendar Integration (1 sprint)

6. **Weekly vibes strip on calendar view** -- Show vibe colors for each day's meals
7. **Weekly vibes summary card** -- Template-based or AI-generated summary on home screen
8. **"I'm in the mood for..." meal planning** -- When creating a meal event, suggest recipes by vibe

**Value**: Vibes become part of the meal planning workflow. Users get delightful weekly reflections.

### Phase 3: AI Enhancement (1 sprint)

9. **Vibe-aware chat suggestions** -- Update system prompt and search tool to consider weekly vibe balance
10. **`GetWeeklyVibesSummary` agent tool** -- Let users ask about their week in chat
11. **Enhanced recipe embeddings** -- Include vibe in embedding text for better semantic search

**Value**: The AI assistant becomes vibe-aware, making suggestions feel more holistic and personalized.

### Phase 4: Social & Personalization (Future)

12. **Per-user vibe overrides** on shared recipes
13. **"Desired vibe" for meal planning** -- "I want a light week"
14. **Seasonal vibe suggestions** -- Surface warming recipes in winter, fresh in summer
15. **Vibe-based recipe discovery** -- "Show me comfort food from other recipe books"

---

## Estimated Complexity

| Phase | Effort | AI Cost | Risk |
|-------|--------|---------|------|
| Phase 1: Foundation | 2-3 sprints | ~$0.10 backfill + ~$0.001/recipe ongoing | Low -- extends existing patterns |
| Phase 2: Calendar | 1-2 sprints | ~$0.01/week for summaries | Low -- uses existing calendar infra |
| Phase 3: AI Enhancement | 1 sprint | Negligible (prompt changes) | Low -- extends existing agent tools |
| Phase 4: Social | 2+ sprints | Negligible | Medium -- per-user overrides add data model complexity |

**Total for MVP (Phase 1 + 2)**: 3-5 sprints, minimal AI cost, no new infrastructure needed.

The vibes system is primarily a **product and design challenge**, not a technical one. The codebase already has every building block needed: tags, AI integration, embeddings, calendar, and a warm visual design language that is perfect for organic, feeling-based categorization.
