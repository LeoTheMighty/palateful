# Palateful AI/OCR Evaluation Suite

Ad-hoc evaluation suite for testing Palateful's AI and OCR features against configurable test datasets with reproducible metrics.

## Quick Start

```bash
# Install dependencies
npx nx run eval:install

# Copy and configure environment
cp .env.eval.example .env.eval
# Edit .env.eval with your API keys

# Run all evaluations
npx nx run eval:run

# Run specific suite
npx nx run eval:run-ocr
npx nx run eval:run-recipe
npx nx run eval:run-matching

# Generate HTML report
npx nx run eval:report -- --format html --open
```

## Features

- **Direct Production Code Testing**: Imports actual prompts and functions from `utils` library
- **Easy Q/A Pairs**: YAML-based test cases with expected outputs
- **Configurable Metrics**: Character accuracy, BLEU scores, field accuracy, and more
- **Mock/Cache Mode**: Fast iteration without GPU or API costs
- **Multiple Reporters**: Console, JSON, and HTML dashboard outputs

## Evaluation Suites

### OCR (`npx nx run eval:run-ocr`)

Tests image-to-text extraction using the HunyuanOCR model.

| Metric | Description |
|--------|-------------|
| `character_accuracy` | Percentage of characters correctly extracted |
| `word_accuracy` | Percentage of words matching expected output |
| `levenshtein_distance` | Edit distance from expected text |
| `bleu_score` | N-gram overlap score |

### Recipe Extraction (`npx nx run eval:run-recipe`)

Tests HTML-to-recipe conversion using JSON-LD and AI extractors.

| Metric | Description |
|--------|-------------|
| `field_accuracy` | Percentage of recipe fields correctly extracted |
| `ingredient_count_accuracy` | Accuracy of ingredient list extraction |
| `instruction_similarity` | Text similarity of instructions |
| `cost_cents` | AI API cost tracking |
| `latency_ms` | Response time |

### Ingredient Matching (`npx nx run eval:run-matching`)

Tests ingredient text matching to database ingredients.

| Metric | Description |
|--------|-------------|
| `exact_match_rate` | Percentage of exact ID matches |
| `fuzzy_match_rate` | Percentage of fuzzy matches above threshold |
| `false_positive_rate` | Incorrect match rate |
| `confidence_calibration` | Confidence score accuracy |

## Configuration

### Environment Variables (`.env.eval`)

```bash
# API Keys
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...

# Evaluation modes
EVAL_OCR_MODE=local        # local | batch | mock
EVAL_MOCK_AI=false         # Use cached responses
EVAL_CACHE_RESPONSES=true  # Save responses for mock mode
EVAL_PARALLEL_WORKERS=4    # Parallel execution
```

### Metrics Configuration (`eval.config.yaml`)

```yaml
thresholds:
  ocr_character_accuracy: 0.95  # Pass/fail threshold
  recipe_field_accuracy: 0.90
  ingredient_match_rate: 0.85
```

## Adding Test Cases

### Manual Method

1. Add input files to the appropriate `datasets/` subdirectory
2. Add expected output files to `expected/` subdirectory
3. Update the manifest file

### Using CLI

```bash
# Add OCR test case
npx nx run eval:add-case -- --suite ocr --input path/to/image.jpg --expected path/to/expected.md --tags handwritten,recipe

# Add recipe extraction test case
npx nx run eval:add-case -- --suite recipe_extraction --input path/to/page.html --expected path/to/expected.json
```

## Dataset Structure

```
datasets/
├── ocr/
│   ├── manifest.yaml        # Test case index
│   ├── images/              # Input images
│   ├── expected/            # Expected markdown outputs
│   └── cache/               # Cached OCR responses
├── recipe_extraction/
│   ├── manifest.yaml
│   ├── html/                # Input HTML files
│   ├── expected/            # Expected JSON outputs
│   └── cache/               # Cached extraction responses
└── ingredient_matching/
    └── cases.yaml           # Input → expected match pairs
```

## Running Evaluations

```bash
# Run all suites
npx nx run eval:run

# Run with tag filter
npx nx run eval:run -- --suite ocr --tags handwritten --verbose

# Compare with baseline
npx nx run eval:run -- --compare results/baseline.json

# Save to specific output
npx nx run eval:run -- --output results/my_run.json
```

## Generating Reports

```bash
# HTML dashboard (opens in browser)
npx nx run eval:report -- --format html --open

# JSON output
npx nx run eval:report -- --format json --output results/report.json

# Console output
npx nx run eval:report -- --format console
```

## Mock Mode

For fast iteration without GPU or API costs:

```bash
# First run: Cache responses
EVAL_CACHE_RESPONSES=true npx nx run eval:run

# Subsequent runs: Use cached responses
EVAL_MOCK_AI=true npx nx run eval:run
```

Cache files are stored in `datasets/*/cache/` and keyed by input content hash.

## CI Integration

Exit codes:
- `0`: All suites passed thresholds
- `1`: One or more suites failed thresholds

```yaml
# Example GitHub Actions
- name: Run AI Evaluations
  run: npx nx run eval:run
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Development

```bash
# Lint
npx nx run eval:lint

# Run tests
npx nx run eval:test

# Generate lock file
npx nx run eval:lock
```
