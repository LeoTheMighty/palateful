# Recipe Extraction Eval Suite

How to add test data, run evals, and compare extraction strategies.

## Quick Start

```bash
# Run evals with text extractor (default)
npx nx run eval:run-fixtures

# Run eval gate (CI mode — exits 1 if below threshold)
npx nx run eval:eval-gate

# Run eval tests
npx nx run eval:test
```

## Directory Structure

```
services/eval/
  fixtures/
    text/             # Plain text recipe inputs (.txt)
    images/           # Recipe images (.jpg, .png)
    urls/             # URL configs (.json)
    expected/         # Ground truth JSONs (one per fixture)
  src/
    scoring.py        # Scoring functions (precision, recall, F1)
    strategies.py     # Extraction strategy registry
    fixture_runner.py # Eval runner + comparison
    gate.py           # CI eval gate with thresholds
  PROMPTS.md          # Prompt documentation and best practices
```

## Adding a Fixture

Every fixture is a **pair**: an input file + a matching expected JSON.

### Step 1: Create the input file

**For text recipes** (copy-pasted, OCR output, etc.):
```
services/eval/fixtures/text/my_recipe.txt
```
Just paste the raw recipe text. Can include OCR artifacts, messy formatting, etc.

**For images** (photos of cookbooks, screenshots, handwritten):
```
services/eval/fixtures/images/my_recipe.jpg
```
Any standard image format (JPG, PNG). For OCR-then-text comparison, also add a sidecar:
```
services/eval/fixtures/images/my_recipe.ocr.txt
```
This contains the raw OCR text output for that image (run HunyuanOCR or type it out).

**For URLs:**
```
services/eval/fixtures/urls/my_recipe.json
```
```json
{"url": "https://example.com/recipe"}
```

### Step 2: Create the ground truth

```
services/eval/fixtures/expected/my_recipe.json
```

**The filename must match** (minus the extension). `text/my_recipe.txt` pairs with `expected/my_recipe.json`.

Ground truth format:
```json
{
  "name": "My Recipe Title",
  "description": "A brief description of the recipe",
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "servings": 4,
  "ingredients": [
    {
      "name": "all-purpose flour",
      "quantity": 2,
      "unit": "cups",
      "text": "2 cups all-purpose flour",
      "notes": null,
      "is_optional": false
    },
    {
      "name": "salt",
      "quantity": 1,
      "unit": "teaspoon",
      "text": "1 tsp salt",
      "notes": null,
      "is_optional": false
    }
  ],
  "instructions": "Step 1: Preheat oven to 350F.\nStep 2: Mix dry ingredients.\nStep 3: ...",
  "tags": ["baking", "dessert"],
  "primary_vibe": "comfort",
  "secondary_vibe": null
}
```

**Tips for ground truth:**
- `name` is required, everything else is optional but scored
- `ingredients[].name` should be the canonical ingredient name (e.g., "all-purpose flour" not "flour")
- `quantity` can be a number (2) or string ("2-3") — the scorer is flexible
- `unit` should be the full word ("cups" not "c"), but the scorer normalizes common abbreviations
- `instructions` can be a single string or you can omit it if you only want to test ingredients
- `tags` and vibes are optional bonus points

### Step 3: Verify

```bash
# Run eval to see your new fixture scored
npx nx run eval:run-fixtures
```

## Scoring Dimensions

| Metric | What it measures |
|--------|-----------------|
| `ingredients_precision` | % of extracted ingredients that are correct |
| `ingredients_recall` | % of expected ingredients that were found |
| `amounts_accuracy` | % of matched ingredients with correct quantity + unit |
| `steps_completeness` | % of expected step content captured |
| `metadata_accuracy` | Title, prep time, cook time, servings correctness |
| `overall_f1` | Weighted average of all dimensions |

The scorer uses fuzzy matching (>80% similarity) for ingredient names, so minor variations are OK.

## Comparing Strategies

Three extraction strategies are available:

| Strategy | Command | What it does | Best for |
|----------|---------|-------------|----------|
| `text_extractor` | Default | GPT-4o-mini parses text → JSON | Text, OCR output |
| `vision_extractor` | `--strategy vision_extractor` | GPT-4o-mini vision: image → JSON | Photos (no GPU needed) |
| `ocr_then_text` | `--strategy ocr_then_text` | HunyuanOCR text → GPT-4o-mini | Photos (GPU pipeline) |

To compare strategies on the same fixtures, use the comparison runner in Python:
```python
from src.fixture_runner import run_comparison
results = run_comparison("fixtures", ["text_extractor", "vision_extractor"])
```

## Eval Gate (CI)

The eval gate checks aggregate F1 against thresholds:

| Input type | Threshold |
|-----------|-----------|
| Text | 80% |
| Image | 70% |
| URL | 85% |

```bash
# Fails CI if below threshold
npx nx run eval:eval-gate
```

## Adding a New Strategy

1. Create your extractor function in `libraries/utils/utils/services/recipe_extractors/`
2. Register it in `services/eval/src/strategies.py`:
   ```python
   STRATEGIES["my_strategy"] = {
       "name": "My New Strategy",
       "input_types": ["text"],  # or ["image"] or both
       "function": "run_my_strategy",
   }
   ```
3. Implement `run_my_strategy(input_path: str) -> dict` that returns a recipe dict
4. Run comparison against existing strategies to see if it's better

## Real-World Test Data

The best fixtures come from real recipes you've imported. To add your own:

1. **From a photo**: Take a photo of a recipe, save to `fixtures/images/`
2. **From a URL**: Save the page text to `fixtures/text/` (or add URL config to `fixtures/urls/`)
3. **Create ground truth**: Manually type out the expected JSON — this is the most important part
4. **Run evals**: See how each strategy scores against your ground truth

The more fixtures you add, the more confident you can be that prompt changes improve (not regress) quality.
