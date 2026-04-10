# Eval Fixtures

This directory contains test fixtures for evaluating recipe extraction strategies.

## Directory Structure

```
fixtures/
  text/            # Plain text inputs (e.g. OCR output)
  images/          # Image inputs (photos of recipes)
  urls/            # URL test configs (JSON with url field)
  expected/        # Ground truth JSON files
```

## Naming Convention

Fixtures are matched by filename stem. For example:

- `text/potato_quiche.txt` matches `expected/potato_quiche.json`
- `images/banana_bread.jpg` matches `expected/banana_bread.json`
- `urls/allrecipes_pasta.json` matches `expected/allrecipes_pasta.json`

## Adding a New Fixture

1. Place the input file in the appropriate subdirectory (`text/`, `images/`, or `urls/`).
2. Create a matching expected JSON file in `expected/` with the same stem name.
3. The expected JSON should follow the standard recipe extraction schema:

```json
{
  "name": "Recipe Name",
  "description": "Brief description",
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "servings": 4,
  "ingredients": [
    {
      "text": "2 cups all-purpose flour",
      "quantity": 2,
      "unit": "cups",
      "name": "all-purpose flour"
    }
  ],
  "instructions": "Step-by-step instructions as a single string."
}
```

## Running Evals

```bash
# Run text extraction eval against all text fixtures
npx nx run eval:run-fixtures

# Run with a specific strategy
npx nx run eval:run-fixtures -- --strategy text_extractor

# Compare multiple strategies
npx nx run eval:run-fixtures -- --compare text_extractor,ocr_then_text
```

## URL Fixture Format

URL fixtures are JSON files with the following structure:

```json
{
  "url": "https://example.com/recipe",
  "description": "Optional description of what this tests"
}
```
