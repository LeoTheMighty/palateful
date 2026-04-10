# Story 13.5: Eval Framework & Fixtures

## Status: Complete

## What Was Done

### 1. Fixture Directory Structure
Created `services/eval/fixtures/` with four subdirectories for test inputs and ground truth:

```
fixtures/
  text/            # Plain text inputs (e.g. OCR output)
  images/          # Image inputs (photos of recipes) — empty with .gitkeep
  urls/            # URL test configs — empty with .gitkeep
  expected/        # Ground truth JSON files
  README.md        # How to add fixtures
```

Each subdirectory contains a `.gitkeep` to preserve the directory in git.

### 2. Scoring Module
**File:** `services/eval/src/scoring.py`

Implements `score_extraction(extracted, expected)` returning six dimensions:

| Metric | Description | Weight |
|---|---|---|
| `ingredients_precision` | Fraction of extracted ingredients that match expected (fuzzy name match, threshold 0.8) | 0.20 |
| `ingredients_recall` | Fraction of expected ingredients found in extracted | 0.20 |
| `amounts_accuracy` | For matched ingredients, checks quantity + unit agreement (with unit normalisation) | 0.15 |
| `steps_completeness` | Fuzzy sentence-level matching of instruction steps | 0.25 |
| `metadata_accuracy` | Title (fuzzy), prep_time (+/-5min), cook_time (+/-5min), servings (+/-1) | 0.20 |
| `overall_f1` | Weighted average of all above scores | — |

Includes helpers for unit normalisation (singular/abbreviation mapping), fuzzy name matching via `difflib.SequenceMatcher`, and quantity comparison with tolerance.

### 3. Strategies Module
**File:** `services/eval/src/strategies.py`

Registry of extraction strategies:

| Key | Name | Status | Input Types |
|---|---|---|---|
| `text_extractor` | GPT-4o-mini Text | Implemented | text |
| `vision_extractor` | GPT-4o-mini Vision | Stub (NotImplementedError) | image |
| `ocr_then_text` | HunyuanOCR + GPT-4o-mini | Stub (NotImplementedError) | image |

The `text_extractor` strategy calls the production `extract_recipe_from_text()` function from `libraries/utils`. The other two are stubs for future implementation.

Provides `get_strategy_function(name)` and `list_strategies()` helpers.

### 4. Fixture Runner
**File:** `services/eval/src/fixture_runner.py`

Two public functions:

- **`run_eval(fixtures_dir, strategy)`** — Discovers input+expected pairs by filename convention, runs the specified strategy, scores results, and prints a rich summary table.
- **`run_comparison(fixtures_dir, strategies)`** — Runs multiple strategies on the same fixtures and prints a side-by-side comparison table.

Fixture matching convention: `text/potato_quiche.txt` matches `expected/potato_quiche.json` by stem name.

### 5. CLI Integration
**File:** `services/eval/src/main.py` (modified)

Added `run-fixtures` CLI command with options:
- `--strategy` / `-s`: Extraction strategy (default: `text_extractor`)
- `--fixtures-dir` / `-d`: Custom fixtures directory path
- `--compare` / `-c`: Comma-separated strategies for comparison mode
- `--output` / `-o`: Save results as JSON

### 6. NX Target
**File:** `services/eval/project.json` (modified)

Added `run-fixtures` target:
```
npx nx run eval:run-fixtures
npx nx run eval:run-fixtures -- --strategy text_extractor
npx nx run eval:run-fixtures -- --compare text_extractor,ocr_then_text
```

### 7. Example Fixture: Potato Quiche
- **Input:** `fixtures/text/potato_quiche.txt` — Clean text with recipe title, description, times, ingredients list, and numbered instructions.
- **Expected:** `fixtures/expected/potato_quiche.json` — Ground truth JSON with 11 ingredients (each with text, quantity, unit, name), metadata, and instructions.

### 8. Tests
Three new test files with 55 new tests (56 total including existing smoke test):

- `tests/test_scoring.py` — Unit tests for all scoring dimensions, helpers, and the main `score_extraction` function.
- `tests/test_strategies.py` — Registry tests, `get_strategy_function`, stub behaviour verification.
- `tests/test_fixture_runner.py` — Fixture discovery, aggregation, edge cases.

All tests pass. Lint clean.

## Files Changed
- `services/eval/src/scoring.py` (new)
- `services/eval/src/strategies.py` (new)
- `services/eval/src/fixture_runner.py` (new)
- `services/eval/src/main.py` (modified — added `run-fixtures` command)
- `services/eval/project.json` (modified — added `run-fixtures` target)
- `services/eval/fixtures/` (new directory tree with README)
- `services/eval/fixtures/text/potato_quiche.txt` (new fixture)
- `services/eval/fixtures/expected/potato_quiche.json` (new fixture)
- `services/eval/tests/test_scoring.py` (new)
- `services/eval/tests/test_strategies.py` (new)
- `services/eval/tests/test_fixture_runner.py` (new)
- `_bmad-output/implementation-artifacts/13-5-eval-framework-and-fixtures.md` (this file)
