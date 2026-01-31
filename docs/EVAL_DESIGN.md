# Palateful AI/OCR Evaluation Suite - Design Document

## 1. Overview

The evaluation suite is an ad-hoc testing framework for Palateful's AI and OCR features. It provides:

- **Reproducible evaluations** against configurable test datasets
- **Direct production code testing** without code duplication
- **Configurable metrics and thresholds** for pass/fail determination
- **Multiple output formats** for reporting and CI integration

### Goals

1. Catch regressions when AI prompts or model parameters change
2. Benchmark different extraction strategies (JSON-LD vs AI)
3. Tune confidence thresholds for ingredient matching
4. Track costs and latency across evaluation runs

### Non-Goals

- Real-time monitoring (use observability tools instead)
- Load testing (use dedicated tools)
- Unit testing of business logic (use pytest)

## 2. Architecture

### Service Structure

```
services/eval/
├── src/
│   ├── main.py           # CLI entry point (click-based)
│   ├── config.py         # Configuration loader
│   ├── runner.py         # Evaluation orchestration
│   ├── evaluators/       # Suite-specific evaluators
│   ├── metrics/          # Metric calculation modules
│   └── reporters/        # Output formatters
├── datasets/             # Test data and manifests
└── results/              # Generated results (gitignored)
```

### Data Flow

```
┌─────────────┐     ┌───────────┐     ┌────────────┐
│   Datasets  │────▶│  Runner   │────▶│ Reporters  │
│  (YAML/files)│     │           │     │            │
└─────────────┘     └─────┬─────┘     └────────────┘
                          │
                    ┌─────▼─────┐
                    │ Evaluators │
                    │            │
                    │ - OCR      │
                    │ - Recipe   │
                    │ - Matching │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │ Production │
                    │   Code     │
                    │            │
                    │ - utils/   │
                    │ - ocr/     │
                    └────────────┘
```

### Production Code Integration

The eval service imports production code directly:

```python
# From utils library
from utils.services.recipe_extractors.ai_extractor import AIExtractor
from utils.services.recipe_extractors.json_ld import JsonLdExtractor

# From OCR service
from services.ocr.src.model import run_ocr
```

This ensures evaluations test the actual code paths used in production.

## 3. Evaluation Suites

### 3.1 OCR Evaluation

**Purpose**: Test image-to-text extraction quality

**Input**: Image files (JPG, PNG)
**Output**: Markdown text
**Production Code**: `services/ocr/src/model.py::run_ocr()`

**Metrics**:
- `character_accuracy`: 1 - (levenshtein_distance / expected_length)
- `word_accuracy`: |actual_words ∩ expected_words| / |expected_words|
- `bleu_score`: N-gram overlap (NLTK implementation)
- `levenshtein_distance`: Edit distance

**Threshold**: 95% character accuracy to pass

### 3.2 Recipe Extraction Evaluation

**Purpose**: Test HTML-to-recipe conversion

**Input**: HTML files
**Output**: Structured recipe JSON
**Production Code**:
- `utils/.../json_ld.py::JsonLdExtractor`
- `utils/.../ai_extractor.py::AIExtractor`

**Metrics**:
- `field_accuracy`: |correct_fields| / |expected_fields|
- `ingredient_count_accuracy`: min(actual, expected) / expected
- `instruction_similarity`: Normalized Levenshtein on instructions
- `cost_cents`: API cost tracking
- `latency_ms`: Response time

**Threshold**: 90% field accuracy to pass

### 3.3 Ingredient Matching Evaluation

**Purpose**: Test text-to-ingredient-ID matching

**Input**: Ingredient text strings
**Output**: Matched ingredient ID and confidence
**Production Code**: `utils/.../match_ingredients_task.py`

**Metrics**:
- `exact_match_rate`: Percentage of exact ID matches
- `fuzzy_match_rate`: Matches above confidence threshold
- `false_positive_rate`: Incorrect non-null matches
- `confidence_calibration`: Correlation between confidence and correctness

**Threshold**: 85% match rate to pass

## 4. Dataset Format

### YAML Manifests

Each suite uses a `manifest.yaml` file:

```yaml
cases:
  - id: unique-case-id
    image: images/file.jpg  # or html: html/file.html
    expected: expected/file.md  # or expected/file.json
    tags: [category, type]
    metadata:
      source: "description"
      url: "https://..."

config:
  timeout_seconds: 60
  skip_tags: []
```

### Ingredient Matching Format

Uses a simpler `cases.yaml`:

```yaml
cases:
  - id: case-id
    input: "2 cups flour"
    expected_id: "uuid-of-flour"
    expected_name: "all-purpose flour"
    expected_match_type: exact  # or fuzzy, none
    min_confidence: 0.85
    tags: [exact-match]
```

## 5. Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API key for AI extraction | Required |
| `DATABASE_URL` | PostgreSQL connection | Required for matching |
| `EVAL_OCR_MODE` | local/batch/mock | local |
| `EVAL_MOCK_AI` | Use cached AI responses | false |
| `EVAL_CACHE_RESPONSES` | Save responses to cache | true |
| `EVAL_PARALLEL_WORKERS` | Parallel execution | 4 |

### Metrics Configuration

`eval.config.yaml` defines:
- Which metrics to calculate per suite
- Pass/fail thresholds

## 6. Running Evaluations

### CLI Commands

```bash
# Run all suites
npx nx run eval:run

# Run specific suite with filters
npx nx run eval:run -- --suite ocr --tags handwritten --verbose

# Compare with baseline
npx nx run eval:run -- --compare results/baseline.json

# Generate reports
npx nx run eval:report -- --format html --open
```

### CI Integration

```yaml
# GitHub Actions example
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx nx run eval:install
      - run: npx nx run eval:run
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Exit code 1 indicates threshold failures.

## 7. Adding Test Cases

### Interactive CLI

```bash
npx nx run eval:add-case -- \
  --suite ocr \
  --input ~/Downloads/recipe-photo.jpg \
  --expected ~/Downloads/expected-text.md \
  --tags handwritten,recipe-card
```

### Manual Process

1. Copy input file to `datasets/{suite}/images/` or `html/`
2. Copy expected output to `datasets/{suite}/expected/`
3. Add entry to `manifest.yaml`

### Generating Expected Outputs

For new test cases without expected outputs:
1. Run evaluation (will pass with "no expected output" note)
2. Review actual output
3. If correct, save as expected output

## 8. Interpreting Results

### Console Output

```
┌─────────────────────────────────┐
│ ocr                      PASSED │
├─────────────────────────────────┤
│ Total Cases: 10                 │
│ Passed: 9                       │
│ Failed: 1                       │
│ Duration: 45.2s                 │
└─────────────────────────────────┘

Metric              Avg      Min      Max
character_accuracy  0.9612   0.8901   0.9923
word_accuracy       0.9234   0.8567   0.9756
```

### HTML Report

Interactive dashboard with:
- Suite-level summary cards
- Per-case results table
- Metric visualizations
- Failure details

### JSON Output

Machine-readable format for programmatic analysis and baseline comparisons.

## 9. Extending the Suite

### Adding a New Evaluator

1. Create `src/evaluators/{name}_evaluator.py`
2. Extend `BaseEvaluator` class
3. Implement `load_cases()` and `evaluate()`
4. Register in `src/evaluators/__init__.py`
5. Add to runner's suite list

### Adding Custom Metrics

1. Add metric function to appropriate `src/metrics/` module
2. Call from evaluator's `evaluate()` method
3. Add to `eval.config.yaml` metrics list

### Adding a New Reporter

1. Create `src/reporters/{name}_reporter.py`
2. Implement `save()` and/or `render()` methods
3. Register in `src/reporters/__init__.py`
4. Add CLI option in `main.py`

## 10. Performance Considerations

### Parallel Execution

- Evaluations run in parallel by default (`EVAL_PARALLEL_WORKERS=4`)
- OCR model is loaded once and reused
- Database connections are pooled

### Caching Strategy

- Responses cached by input content hash
- Cache enables fast mock-mode iterations
- Cache invalidated when input changes

### Memory Management

- OCR model unloaded after suite completion
- Large results streamed to disk
- Parallel workers limited to prevent OOM

## 11. Troubleshooting

### Common Issues

**"No cases found for suite"**
- Check manifest.yaml syntax
- Verify file paths exist
- Check tag filters aren't excluding all cases

**"Database connection failed"**
- Ensure PostgreSQL is running: `docker compose up -d`
- Verify DATABASE_URL in .env.eval

**"OCR model loading failed"**
- Check CUDA/MPS availability
- Try `EVAL_OCR_MODE=mock` for CPU-only testing

### Debug Mode

```bash
EVAL_VERBOSE=true npx nx run eval:run -- --suite ocr
```

Enables detailed logging of each evaluation step.
