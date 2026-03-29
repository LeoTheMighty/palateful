# Story Vibes.1: Backend — Vibe Columns, Embedded AI Assignment, Backfill

Status: complete

## Story

As a developer,
I want recipes to have `primary_vibe` and `secondary_vibe` fields that are automatically assigned by AI during the existing recipe extraction flow at zero additional cost,
so that every recipe has vibes without adding API calls or latency.

## Acceptance Criteria

1. `recipes` table has `primary_vibe VARCHAR(20)` and `secondary_vibe VARCHAR(20)` nullable columns
2. Valid vibe values: `light_fresh`, `hearty`, `comfort`, `energizing`, `carb_load`, `indulgent`, `warming`
3. Vibe assignment is embedded in the **existing** `TextExtractor` and `AIExtractor` prompts — NOT a separate API call
4. When a recipe is created via manual wizard (not import), vibes are assigned via a lightweight prompt addition to the embedding generation step
5. Backfill script assigns vibes to all existing recipes in batch (using GPT-4o-mini batch API for 50% cost savings)
6. Import pipeline automatically produces vibes as part of recipe extraction
7. Zero additional OpenAI API calls for vibe assignment during normal recipe creation/import

## Tasks / Subtasks

- [x] Task 1: Database migration (AC: #1, #2)
  - [x] Create migration adding `primary_vibe` and `secondary_vibe` VARCHAR(20) columns to `recipes` table
  - [x] Both nullable (existing recipes won't have vibes until backfill)
  - [x] No enum constraint for flexibility — validate in application layer

- [x] Task 2: Update Recipe model (AC: #1)
  - [x] Add `primary_vibe` and `secondary_vibe` to `libraries/utils/utils/models/recipe.py`
  - [x] Add to Pydantic schemas: `RecipeResponse`, `RecipeListItem`, `RecipeCreate`, `RecipeUpdate`

- [x] Task 3: Embed vibe assignment in TextExtractor (AC: #3, #6)
  - [x] Modify `libraries/utils/utils/services/recipe_extractors/text_extractor.py`
  - [x] Add to the existing system/user prompt:
    ```
    Also assign 1-2 vibes from: [light_fresh, hearty, comfort, energizing, carb_load, indulgent, warming]
    Include in your JSON response: "primary_vibe": "...", "secondary_vibe": "..." or null
    ```
  - [x] Parse vibe fields from the AI response alongside existing recipe fields
  - [x] This adds ~20 tokens to the prompt and ~10 tokens to the response — negligible cost

- [x] Task 4: Embed vibe assignment in AIExtractor (AC: #3, #6)
  - [x] Modify `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
  - [x] Same prompt addition as TextExtractor
  - [x] Parse vibe fields from response

- [x] Task 5: Embed vibe assignment in JsonLdExtractor (AC: #3, #6)
  - [x] For JSON-LD extractions (no AI call), assign vibes in a lightweight post-processing step
  - [x] Option A: Derive vibes from recipe category/keywords in the JSON-LD data (heuristic, free)
  - [x] Option B: Skip vibes for JSON-LD and assign during the MatchIngredients step or embedding generation
  - [x] Recommendation: Option B — piggyback on the embedding generation call which already sends recipe data to OpenAI

- [x] Task 6: Vibe assignment during manual recipe creation (AC: #4)
  - [x] In the `generate_recipe_embedding` function (or wherever embeddings are created):
  - [x] Add vibe fields to the prompt that generates the embedding text
  - [x] Or: after recipe creation, run a single combined prompt that generates embedding text AND vibes
  - [x] Ensure this doesn't add an extra API call — embed in existing flow

- [x] Task 7: Store vibes on ImportItem and Recipe (AC: #6)
  - [x] When extraction produces vibes, store on the ImportItem's `parsed_recipe` JSON
  - [x] When `CreateRecipeTask` creates the Recipe record, copy vibes from parsed_recipe to recipe columns

- [x] Task 8: Backfill script (AC: #5)
  - [x] Create a management command / script that:
    - Queries all recipes where `primary_vibe IS NULL`
    - Batches them (50 at a time)
    - For each recipe: compose text from name + ingredients + description
    - Send to GPT-4o-mini with vibe-only prompt (lightweight, ~$0.001 per recipe)
    - Update `primary_vibe` and `secondary_vibe` columns
  - [x] Consider using OpenAI Batch API for 50% cost reduction on backfill
  - [x] Estimated cost for 100 recipes: ~$0.05–0.10

## Dev Notes

- **The key insight is zero additional API calls.** Every recipe already goes through AI extraction (TextExtractor, AIExtractor) or embedding generation. We're adding ~30 tokens to existing prompts.
- For JSON-LD recipes (which don't use AI extraction), vibes are assigned during the embedding generation step — which IS an AI call that already happens
- The valid vibe values should be defined as a constant in a shared location (e.g., `libraries/utils/utils/constants.py`)
- Backfill can run as a one-time Celery task or management command
- The prompt addition is literally 2 extra lines in existing prompts — minimal risk of disrupting current extraction quality

### References

- [Investigation: 10-health-vibes-score.md]
- [Epic: epic-vibes.md]
- Existing extractors: `libraries/utils/utils/services/recipe_extractors/`
- Embedding generation: `services/api/src/api/v1/search/generate_recipe_embedding.py`
