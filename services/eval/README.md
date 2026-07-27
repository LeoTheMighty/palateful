# Palateful AI/OCR Evaluation Suite

Ad-hoc evaluation suite for testing Palateful's AI and OCR features against configurable test datasets with reproducible metrics.

## Quick Start

```bash
# Install dependencies
npx nx run eval:install

# Copy and configure environment
cp .env.eval.example .env.eval
# Edit .env.eval with your API keys

# Run all default evaluations (vision_extraction is opt-in — see below)
npx nx run eval:run

# Run specific suite
npx nx run eval:run-ocr
npx nx run eval:run-recipe
npx nx run eval:run-matching

# Opt-in suite: every case is a live gpt-4o-mini vision call
npx nx run eval:run-vision

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
| `recipe_count_accuracy` | Fraction of cases where extractor returned the right *number* of recipes (FR88 multi-recipe fan-out). 1.0 per exact match / 0.0 otherwise. Gated at 0.80 on `multi_recipe`-tagged cases. |
| `ingredient_count_accuracy` | Accuracy of ingredient list extraction |
| `instruction_similarity` | Text similarity of instructions |
| `cost_cents` | AI API cost tracking |
| `latency_ms` | Response time |

Multi-recipe expected files use `{"recipes": [recipe_a, recipe_b, ...]}`. Single-recipe expected files keep the legacy bare-recipe shape; the evaluator wraps both transparently, pair-wise aligns expected-vs-actual in source order, and grades accordingly.

**Manifest input keys.** A case names its input with either:

| Key | Extractor (`extractor:`) | Runs offline? |
|---|---|---|
| `html:` | `json_ld`, `ai`, `auto` | `json_ld`/`auto` yes, `ai` no |
| `text:` | `text` (`extract_recipe_from_text`) | no — live gpt-4o-mini |

Paths may contain `../`, which is how the committed fan-out cases point at
`fixtures/text/*.txt` and share one expected JSON with their image twin in
the vision suite. Extractors with no offline path (`ai`, `text`) are
**skipped** under `EVAL_MOCK_AI` when the cache is cold rather than scored
0.0 — a suite where every case was skipped is reported as passing, because
nothing was measured. Errored cases are not skipped, so a genuinely broken
suite still goes red.

### Vision Extraction (`npx nx run eval:run-vision`)

Tests **image**-to-recipe conversion — `extract_recipe_from_image`
(gpt-4o-mini vision), the path behind photo import. It is the vision twin
of the recipe-extraction suite: `VisionExtractionEvaluator` subclasses
`RecipeExtractionEvaluator`, so it computes the *same* metrics through the
*same* order-based alignment. Only the input (a PNG instead of HTML) and
the extractor call differ.

```bash
# Opt-in: not part of the default `run` (every case is a live vision call).
npx nx run eval:run-vision

# Just the fan-out cases.
npx nx run eval:run-vision --tags multi_recipe

# Discover the fixtures without spending anything (cold cache = all skipped).
EVAL_MOCK_AI=true npx nx run eval:run-vision
```

| Metric | Description |
|--------|-------------|
| `recipe_count_accuracy` | **Hard gate, 0.80.** Fraction of cases where the vision extractor returned the right *number* of recipes. 1.0 per exact match / 0.0 otherwise. |
| `multi_recipe_count_accuracy` | Same number, emitted **only** on `multi_recipe`-tagged cases, and gated separately at 0.80. Single-recipe photos score ~1.0 for free, so grading them together would let a fan-out regression hide behind the average. |
| `field_accuracy` | Per-recipe field match rate. **Reported, not gated** — a first baseline is being collected before a regression bar is set. Also drives per-case pass/fail. |
| `ingredient_count_accuracy`, `instruction_similarity`, `timer_extraction_f1` | Identical to the text suite; reported per case and averaged into the suite summary. |
| `unit_enum_compliance` | Identical to the text suite, but reported as a **dict** (compliance + non-canonical token counts). The runner only averages scalars, so there is no `unit_enum_compliance_avg` — the baseline pins it per case. |

What it measures, in one line: *given a photo of one or more recipes, does
the extractor emit the right number of recipes, with the right fields on
each?*

Cost and safety:

- `vision_extraction` is excluded from the default suite list (`run` with
  no `--suite`). Ask for it explicitly.
- Under `EVAL_MOCK_AI=true`, a case with no cached response is **skipped**
  rather than billed, and an all-skipped run passes the gate (a no-op is
  not a regression).
- A failed extraction ("no recipe found") is graded `0.0`, not dropped as
  an error — a miss must stay in the average. It is **not** cached: a run
  made without a valid `OPENAI_API_KEY` fails every case, and caching those
  zeros would make each later `EVAL_MOCK_AI=true` re-grade replay a
  fabricated 0.0 that looks exactly like a genuine model miss.

Baseline capture:

`baselines/vision_extraction_baseline.json` is the `field_accuracy`
regression reference. It ships with NULL placeholders — the first live run
populates it. Do not hand-transcribe the console table; capture it:

```bash
# The one live run (bills ~5 gpt-4o-mini vision calls). The key can also
# live in services/eval/.env.eval, which the target loads automatically.
OPENAI_API_KEY=<key> npx nx run eval:run-vision \
    --output results/vision-baseline.json

# Rewrite the baseline file + print the PR-pasteable markdown block.
npx nx run eval:capture-vision-baseline \
    --results results/vision-baseline.json --markdown
```

The capture script never calls OpenAI (it only reads the run's JSON), and
it refuses an all-skipped mock run — an empty baseline would read as
"measured zero" to the future hardening pass that turns
`thresholds.field_accuracy` from soft into a hard gate.

Reading the baseline — the soft metrics have ceilings below 1.0:

The image fixtures reuse the text suite's expected JSON verbatim (that
shared ground truth is what lets an image and its text twin be compared).
Two consequences cap what a *perfect, prompt-obeying* extraction can score.
Neither is a model regression; both are pinned by
`tests/test_vision_live_path_rehearsal.py` so the numbers here can't rot.

| Skew | Effect | Why |
|---|---|---|
| Unit tokens | `field_accuracy` ceiling ≈ **0.75–0.88**, not 1.0 | Ground truth spells units `cups` / `tablespoons` / `teaspoon`; the extractor prompt (`unit_prompt.py`) asks for `cup` / `tbsp` / `tsp`. Ingredient dicts compare exactly, so an obedient model loses the whole `ingredients` field — one of the 4–8 graded keys per recipe. |
| Missing instructions | `instruction_similarity` = **0.0** on the three `multi_recipe` cases | Those fixtures render Directions in the PNG but carry no `instructions` key, and the metric scores 0.0 when actual is non-empty and expected is empty. |

Both are properties of the *fixtures*, not of this suite, and fixing them
means editing shared text-suite ground truth — deliberately out of scope
here (the story requires the text suite's fixtures and results to be
unchanged). `recipe_count_accuracy`, the only hard-gated metric, is
unaffected by either: it compares recipe counts, not fields.

For the same reason `expected_timers` is excluded from the field-accuracy
denominator (`_NON_FIELD_KEYS` in `recipe_extraction_evaluator.py`) — it is
a grading annotation consumed by `compute_timer_f1`, not a field any
extractor emits, and counting it capped `field_accuracy` at (n-1)/n on
every timer-annotated fixture in both suites.

Fixtures live in the shared tree (`fixtures/images/` + `fixtures/expected/`)
and are registered in `datasets/vision_extraction/manifest.yaml`. Because an
image fixture is a render of its text twin, both grade against one expected
JSON. To add one, follow the generator procedure in
[`fixtures/README.md`](fixtures/README.md): write the recipe text under
`fixtures/text/`, add a `LAYOUTS` entry, run
`poetry run python scripts/generate_image_fixtures.py`, add the expected
JSON, then register the case in the vision manifest with
`single_recipe`/`multi_recipe` + `image` tags.

Five offline test files cover the chain without spending a cent —
`tests/test_vision_fixtures.py` (dataset consistency),
`tests/test_vision_extraction_evaluator.py` (evaluator + gate units),
`tests/test_vision_suite_end_to_end.py` (the real `EvalRunner` over the
committed manifest, served from a seeded cache in a tmp dataset dir),
`tests/test_vision_live_path_rehearsal.py` (the *live* path: real PNG ->
real `extract_recipe_from_image` -> real `ExtractedRecipe` -> metrics, with
only the OpenAI SDK client stubbed), and
`tests/test_vision_baseline_capture.py` (baseline capture). Adding a case
to the manifest is picked up automatically by the end-to-end tests.

The rehearsal file is the one that de-risks the paid run: the other three
grade payloads that are perfectly shaped by construction, so a mismatch
between the production extractor's output and the fixtures' ground truth
would only have surfaced *after* the money was spent.

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
  field_inference_accuracy_min: 0.60  # efi-8 soft gate
  hallucination_rate_max: 0.15        # efi-8 soft gate
```

### Field inference metrics (efi-8, soft gate)

Two post-ship calibration metrics for the
`EXTRACTOR_INFER_MISSING_FIELDS` pipeline:

- `field_inference_accuracy` — for every (fixture × inferable-field)
  pair where the extractor marked the field in `inferred_fields` AND
  ground truth has a value, score how close the inferred value landed
  to truth. Numeric fields use ±20% tolerance (servings also has a ±1
  floor). Enum-ish fields (cuisine, category, vibes) require exact
  case-insensitive match. Description uses Levenshtein similarity on
  the first 200 chars (pass ≥ 0.6, raw ratio otherwise).
- `hallucination_rate` — anti-metric. For every (fixture ×
  inferable-field) pair where GT has a value AND the extractor marked
  it as inferred, count a hallucination (the model guessed when the
  source had the answer). Lower is better. Rate =
  `hallucinations / extractable_pairs`.

Both metrics are **soft-gate in v1** — reported in the results payload,
never CI-blocking. Baseline at `baselines/field_inference_baseline.json`.
Gate tightening is a follow-up story once real traffic accumulates in
`error_logs(service="audit", error_type="InferredFieldCorrected")` and
we can tune from correction data.

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
├── vision_extraction/
│   ├── manifest.yaml        # Points at ../../fixtures/{images,expected}
│   └── cache/               # Cached vision responses
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

Two things to know before trusting a mock run:

- **Cache state is an invisible input.** `EVAL_MOCK_AI=true` only skips
  AI-only cases when the cache is *cold*; with entries present the same
  command grades them instead. Check `datasets/<suite>/cache/` before
  reading a result as "the suite passed without spending".
- **Only successful extractions are cached** (see the vision suite's
  cost-and-safety notes above for why) — so a keyless run leaves the cache
  as it found it.

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
# Install deps into the service venv (first run, or after a lock change)
npx nx run eval:install

# Lint (covers src/, scripts/ and tests/ — not src/ alone)
npx nx run eval:lint

# Run tests (no API calls; writes coverage/ and reports/ like every other service)
npx nx run eval:test

# Generate lock file
npx nx run eval:lock
```
